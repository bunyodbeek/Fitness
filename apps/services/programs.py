from django.db import transaction

from apps.models import Exercise, Plan, Program, Week, Workout, WorkoutExercise
from apps.models.workouts import ProgressionSetting, HomeProgressionSetting
from apps.utils.tokens import generate_share_token
from apps.workouts.recommendation import get_recommended_program

try:
    from apps.models import UserProgram
except ImportError:
    UserProgram = None


# Hafta raqami → ProgressionSetting field nomlari (sets / reps o'sishi).
# Vazn/vaqt endi bu yerdan emas, mashqning o'z maydonlaridan hisoblanadi.
WEEK_FIELD_MAP = {
    2: ("set_w2", "rep_w2"),
    3: ("set_w3", "rep_w3"),
    4: ("set_w4", "rep_w4"),
    5: ("set_w5", "rep_w5"),
    6: ("set_w6", "rep_w6"),
}


def _weight_week_index(week_number: int, max_weeks: int) -> int:
    """Return the week whose weight a given week should mirror.

    Week 6 is a deload week: its weight matches week 4 (``start + 3*increment``)
    instead of continuing the progression. Only applies to full 6-week plans —
    4-week plans have no deload week. Every other week uses its own number.
    """
    if max_weeks == 6 and week_number == 6:
        return 4
    return week_number


def _gym_progression_source(exercise: Exercise, difficulty: str):
    """Resolve the per-week progression driver for a GYM exercise.

    ``difficulty`` is the target plan's ``Plan.difficulty`` (beginner/advanced).
    Returns ``(mode, start, increment)`` where ``mode`` is ``"time"`` or
    ``"weight"``. Both the start value and the weekly increment are difficulty-
    specific. The advanced side falls back to the beginner value when empty, and
    a missing increment falls back to 0 (weight/time stays flat), so legacy
    exercises keep working unchanged.
    """
    advanced = difficulty == Plan.Difficulty.ADVANCED

    if exercise.exercise_type == Exercise.ExerciseType.TIME_BASED:
        if advanced and exercise.start_time_advanced is not None:
            increment = exercise.weekly_time_increment_advanced
            if increment is None:
                increment = exercise.weekly_time_increment_beginner
            return "time", exercise.start_time_advanced, (increment or 0)
        return "time", (exercise.start_time_beginner or 0), (exercise.weekly_time_increment_beginner or 0)

    # reps_based (yoki hali tanlanmagan) → vaznga asoslangan.
    if advanced and exercise.start_weight_advanced is not None:
        increment = exercise.weekly_weight_increment_advanced
        if increment is None:
            increment = exercise.weekly_weight_increment_beginner
        return "weight", exercise.start_weight_advanced, (increment or 0)
    return "weight", (exercise.start_weight_beginner or 0), (exercise.weekly_weight_increment_beginner or 0)


class ProgramGenerationService:

    @staticmethod
    def ensure_plan_weeks(plan):
        """Plan yaratilganda haftalarni avtomatik yaratish."""
        max_weeks = 4 if getattr(plan, "is_4_week", False) else 6
        for i in range(1, max_weeks + 1):
            Week.objects.get_or_create(plan=plan, week_number=i)

    @staticmethod
    def generate_progression_from_week_one(instance: WorkoutExercise):
        plan = instance.workout.week.plan
        config: ProgressionSetting = plan.progression_config

        # Sets/reps o'sishi progression rule'dan olinadi.
        if not config:
            return

        base_sets = int(instance.sets or 0)
        base_reps = int(instance.reps or 0)

        # Vazn/vaqt mashqning katalog maydonlaridan + PLANNING difficulty'sidan
        # hisoblanadi: N-hafta = start + (N - 1) * weekly_increment.
        mode, start_value, increment = _gym_progression_source(
            instance.exercise, plan.difficulty,
        )

        max_weeks = 4 if getattr(plan, "is_4_week", False) else 6

        def week_value(week_num: int):
            eff_week = _weight_week_index(week_num, max_weeks)
            value = start_value + (eff_week - 1) * increment
            if mode == "time":
                return None, int(round(value))
            return round(value, 2), None

        # 1-hafta (seed) — darajaga mos boshlang'ich qiymatni o'rnatamiz, lekin
        # admin qo'lda tahrirlagan (manual) qiymatga tegmaymiz.
        if not instance.is_weight_manual:
            w1_weight, w1_seconds = week_value(1)
            WorkoutExercise.objects.filter(pk=instance.pk).update(
                recommended_weight=w1_weight if w1_weight is not None else 0,
                duration_seconds=w1_seconds,
            )

        for week_num in range(2, max_weeks + 1):
            set_field, rep_field = WEEK_FIELD_MAP[week_num]

            set_increment = getattr(config, set_field)
            rep_increment = getattr(config, rep_field)

            new_sets = max(0, base_sets + int(set_increment))
            new_reps = max(6, base_reps + int(rep_increment))

            new_weight, new_seconds = week_value(week_num)

            target_week = Week.objects.filter(plan=plan, week_number=week_num).first()
            if not target_week:
                continue

            target_workout, _ = Workout.objects.get_or_create(
                week=target_week,
                day_number=instance.workout.day_number,
                defaults={
                    "title":    instance.workout.title,
                    "title_uz": instance.workout.title_uz,
                    "title_ru": instance.workout.title_ru,
                },
            )

            # Preserve a hand-edited weight/time on the target row if present.
            existing = WorkoutExercise.objects.filter(
                workout=target_workout, exercise=instance.exercise,
            ).first()
            if existing and existing.is_weight_manual:
                weight_val, seconds_val = existing.recommended_weight, existing.duration_seconds
            else:
                weight_val = new_weight if new_weight is not None else 0
                seconds_val = new_seconds

            WorkoutExercise.objects.update_or_create(
                workout=target_workout,
                exercise=instance.exercise,
                defaults={
                    "sets":               new_sets,
                    "reps":               new_reps,
                    "recommended_weight": weight_val,
                    "duration_seconds":   seconds_val,
                    "order":              instance.order,
                    "minutes":            instance.minutes,
                    "source_week_one":    instance,
                },
            )

    @staticmethod
    def regenerate_all_from_week_one(plan):
        """Admin dan butun planni qayta hisoblash."""
        week_one = Week.objects.filter(plan=plan, week_number=1).first()
        if not week_one:
            return 0

        seeds = WorkoutExercise.objects.filter(
            workout__week=week_one,
            workout__apply_to_all_weeks=True,
            source_week_one__isnull=True,
        ).select_related("workout", "exercise")

        count = 0
        for seed in seeds:
            if plan.program.workout_type == "home":
                ProgramGenerationService.generate_home_progression_from_week_one(seed)
            else:
                ProgramGenerationService.generate_progression_from_week_one(seed)
            count += 1
        return count

    @staticmethod
    def recompute_plan_weights(plan) -> int:
        """Recompute the stored weekly weight/time of every AUTO (non-manual)
        WorkoutExercise in a GYM plan from the exercise fields + plan.difficulty.

        Only weight/time change — sets/reps/structure are untouched, and rows
        flagged ``is_weight_manual`` are skipped. Used when the plan's difficulty
        changes and after a copy-by-link import. Home plans are a no-op (their
        per-week values are minutes/rounds, not difficulty-driven weights).
        """
        if plan.program.workout_type != "gym":
            return 0

        rows = (
            WorkoutExercise.objects
            .filter(workout__week__plan=plan, is_weight_manual=False)
            .select_related("exercise", "workout__week")
        )
        max_weeks = 4 if getattr(plan, "is_4_week", False) else 6

        count = 0
        for we in rows:
            week_number = we.workout.week.week_number
            mode, start, increment = _gym_progression_source(we.exercise, plan.difficulty)
            eff_week = _weight_week_index(week_number, max_weeks)
            value = start + (eff_week - 1) * increment
            if mode == "time":
                WorkoutExercise.objects.filter(pk=we.pk).update(
                    recommended_weight=0, duration_seconds=int(round(value)),
                )
            else:
                WorkoutExercise.objects.filter(pk=we.pk).update(
                    recommended_weight=round(value, 2), duration_seconds=None,
                )
            count += 1
        return count

    @staticmethod
    def generate_home_progression_from_week_one(instance: WorkoutExercise):
        plan = instance.workout.week.plan
        # Prefer the rule the admin picked for this plan; fall back to the first.
        setting = plan.home_progression_config or HomeProgressionSetting.objects.first()

        if not setting:
            setting = HomeProgressionSetting.objects.create(key="default")

        base_minutes = float(instance.minutes or 0)
        base_rounds = int(instance.workout.rounds or 1)

        cumulative_seconds = 0
        cumulative_rounds = 0

        max_weeks = 4 if getattr(plan, "is_4_week", False) else 6

        week_increments = {
            2: (getattr(setting, "duration_w2", 0) or 0, getattr(setting, "round_w2", 0) or 0),
            3: (getattr(setting, "duration_w3", 0) or 0, getattr(setting, "round_w3", 0) or 0),
            4: (getattr(setting, "duration_w4", 0) or 0, getattr(setting, "round_w4", 0) or 0),
            5: (getattr(setting, "duration_w2", 0) or 0, getattr(setting, "round_w2", 0) or 0),
            6: (getattr(setting, "duration_w3", 0) or 0, getattr(setting, "round_w3", 0) or 0),
        }

        for week_num in range(2, max_weeks + 1):
            d_inc, r_inc = week_increments.get(week_num, (0, 0))
            cumulative_seconds += d_inc
            cumulative_rounds += r_inc

            new_minutes = base_minutes + (cumulative_seconds / 60)
            new_rounds = max(1, base_rounds + cumulative_rounds)

            target_week = Week.objects.filter(plan=plan, week_number=week_num).first()
            if not target_week:
                continue

            target_workout, created = Workout.objects.get_or_create(
                week=target_week,
                day_number=instance.workout.day_number,
                defaults={
                    "title":    instance.workout.title,
                    "title_uz": instance.workout.title_uz,
                    "title_ru": instance.workout.title_ru,
                    "rounds":   new_rounds,
                },
            )

            if not created:
                target_workout.rounds = new_rounds
                target_workout.save(update_fields=["rounds"])

            WorkoutExercise.objects.update_or_create(
                workout=target_workout,
                exercise=instance.exercise,
                defaults={
                    "minutes":         new_minutes,
                    "sets":            instance.sets,
                    "reps":            instance.reps,
                    "order":           instance.order,
                    "source_week_one": instance,
                },
            )

    @staticmethod
    def ensure_home_plan_integrity(plan: Plan):
        """
        Ensure Home plans have workouts/exercises for all expected weeks.
        Repairs existing broken plans by generating weeks 2..N from week-1 seeds.
        """
        if plan.program.workout_type != "home":
            return

        ProgramGenerationService.ensure_plan_weeks(plan)

        week_one = Week.objects.filter(plan=plan, week_number=1).first()
        if not week_one:
            return

        seeds = WorkoutExercise.objects.filter(
            workout__week=week_one,
            source_week_one__isnull=True,
        ).select_related("workout", "exercise")

        if not seeds.exists():
            return

        for seed in seeds:
            ProgramGenerationService.generate_home_progression_from_week_one(seed)

    # ── Admin "copy plan by link" (panel-only) ────────────────────────────────

    @staticmethod
    def get_or_create_plan_share_token(plan: Plan) -> str:
        """Lazily mint/persist an admin-only share token for a single Plan.

        Reuses ``generate_share_token`` but lives on ``Plan.share_token`` — kept
        entirely separate from the user-facing ``Program.share_token`` flow.
        """
        if plan.share_token:
            return plan.share_token

        for _ in range(10):
            token = generate_share_token()
            if not Plan.objects.filter(share_token=token).exists():
                plan.share_token = token
                plan.save(update_fields=["share_token"])
                return token
        plan.share_token = generate_share_token()
        plan.save(update_fields=["share_token"])
        return plan.share_token

    @staticmethod
    @transaction.atomic
    def copy_plan_structure_into(target_plan: Plan, source_plan: Plan) -> int:
        """Copy the source plan's FULL structure — every week, day/workout and
        exercise with its set/rep values — into ``target_plan``, then fill in the
        weekly weights/times from the TARGET plan's own difficulty.

        Every week is copied verbatim (not seed+regenerate) so any hand-edited
        per-week set/rep differences in the source are reproduced exactly. Days
        are appended after any existing week-1 days, with the same offset applied
        to every week so day alignment across weeks is preserved.

        Deliberately NOT copied: weights/times (derived from the target
        difficulty), the source's difficulty / progression rule, and the manual
        override flags (imported rows all start as auto). Uses ``bulk_create`` so
        the week-1 post_save generation signal does NOT fire — the explicit copy
        is authoritative. Returns the number of week-1 days imported.
        """
        ProgramGenerationService.ensure_plan_weeks(target_plan)

        target_weeks = {w.week_number: w for w in target_plan.weeks.all()}
        tw1 = target_weeks.get(1)
        last_day = tw1.workouts.order_by("-day_number").first() if tw1 else None
        day_offset = last_day.day_number if last_day else 0

        source_weeks = (
            source_plan.weeks
            .order_by("week_number")
            .prefetch_related("workouts__workout_exercises")
        )

        week1_days = 0
        for source_week in source_weeks:
            target_week = target_weeks.get(source_week.week_number)
            if target_week is None:
                target_week = Week.objects.create(
                    plan=target_plan, week_number=source_week.week_number,
                )
                target_weeks[source_week.week_number] = target_week

            for source_wo in source_week.workouts.all():
                target_wo = Workout.objects.create(
                    week=target_week,
                    day_number=source_wo.day_number + day_offset,
                    title=source_wo.title,
                    title_uz=source_wo.title_uz,
                    title_ru=source_wo.title_ru,
                    description=source_wo.description,
                    description_uz=source_wo.description_uz,
                    description_ru=source_wo.description_ru,
                    rounds=source_wo.rounds,
                    apply_to_all_weeks=source_wo.apply_to_all_weeks,
                )
                if source_week.week_number == 1:
                    week1_days += 1

                WorkoutExercise.objects.bulk_create([
                    WorkoutExercise(
                        workout=target_wo,
                        exercise=we.exercise,
                        sets=we.sets,
                        reps=we.reps,
                        minutes=we.minutes,
                        order=we.order,
                        source_week_one=None,
                        is_weight_manual=False,
                    )
                    for we in source_wo.workout_exercises.all()
                ])

        # Fill every copied row's weight/time from the TARGET plan's difficulty.
        ProgramGenerationService.recompute_plan_weights(target_plan)
        return week1_days


# ─────────────────────────────────────────────
# UserProgramService
# ─────────────────────────────────────────────

class UserProgramService:

    @staticmethod
    @transaction.atomic
    def assign_auto_program_once(profile):
        if UserProgram is None:
            return None

        already_assigned = UserProgram.objects.filter(
            user=profile, assigned_once=True
        ).exists()
        if already_assigned:
            return UserProgram.objects.filter(user=profile, is_active=True).first()

        matched_program = (
            get_recommended_program(profile)
            or Program.objects.filter(type=Program.ProgramType.ADMIN, is_active=True).first()
        )

        if not matched_program:
            return None

        UserProgram.objects.filter(user=profile, is_active=True).update(is_active=False)
        return UserProgram.objects.create(
            user=profile,
            program=matched_program,
            is_active=True,
            assigned_once=True,
        )

    @staticmethod
    @transaction.atomic
    def clone_program(source_program: Program, new_owner) -> Program:
        """
        Deep-copy source_program and all its Plans/Weeks/Workouts/WorkoutExercises
        for new_owner.  Used by the share-link import flow.
        Global catalog objects (Exercise, ProgressionSetting) are referenced, not cloned.
        source_week_one links are intentionally left None so the copy is independent.
        """
        from django.db import IntegrityError

        cloned = Program.objects.create(
            name=source_program.name,
            name_uz=source_program.name_uz,
            name_ru=source_program.name_ru,
            description=source_program.description,
            description_uz=source_program.description_uz,
            description_ru=source_program.description_ru,
            type=Program.ProgramType.CUSTOM,
            created_by=new_owner,
            level=source_program.level,
            goal=source_program.goal,
            is_template=False,
            is_individual=False,
            image=source_program.image,
            is_active=True,
            is_premium=False,
            workout_type=source_program.workout_type,
            share_token=None,
        )

        source_plans = (
            source_program.plans
            .prefetch_related(
                "weeks__workouts__workout_exercises__exercise",
            )
            .order_by("order")
        )

        for source_plan in source_plans:
            plan = Plan.objects.create(
                program=cloned,
                name=source_plan.name,
                name_uz=source_plan.name_uz,
                name_ru=source_plan.name_ru,
                description=source_plan.description,
                description_uz=source_plan.description_uz,
                description_ru=source_plan.description_ru,
                order=source_plan.order,
                weeks_count=source_plan.weeks_count,
                is_premium=False,
                is_4_week=source_plan.is_4_week,
                progression_config=source_plan.progression_config,
            )
            ProgramGenerationService.ensure_plan_weeks(plan)

            week_map: dict[int, Week] = {
                w.week_number: w for w in plan.weeks.all()
            }

            for source_week in source_plan.weeks.order_by("week_number"):
                target_week = week_map.get(source_week.week_number)
                if not target_week:
                    continue

                for source_workout in source_week.workouts.order_by("day_number", "id"):
                    target_workout = Workout.objects.create(
                        week=target_week,
                        day_number=source_workout.day_number,
                        title=source_workout.title,
                        title_uz=source_workout.title_uz,
                        title_ru=source_workout.title_ru,
                        description=source_workout.description,
                        description_uz=source_workout.description_uz,
                        description_ru=source_workout.description_ru,
                        rounds=source_workout.rounds,
                        apply_to_all_weeks=source_workout.apply_to_all_weeks,
                    )

                    exercises = list(
                        source_workout.workout_exercises.order_by("order", "id")
                    )
                    WorkoutExercise.objects.bulk_create([
                        WorkoutExercise(
                            workout=target_workout,
                            exercise=we.exercise,
                            sets=we.sets,
                            reps=we.reps,
                            recommended_weight=we.recommended_weight,
                            order=we.order,
                            minutes=we.minutes,
                            source_week_one=None,
                        )
                        for we in exercises
                    ])

        return cloned

    @staticmethod
    def get_or_create_share_token(program: Program) -> str:
        """Lazily create and persist a share token for the given program."""
        from django.db import IntegrityError

        if program.share_token:
            return program.share_token

        for _ in range(10):
            token = generate_share_token()
            if not Program.objects.filter(share_token=token).exists():
                program.share_token = token
                program.save(update_fields=["share_token"])
                return token
        # Fallback: let DB uniqueness constraint catch a collision (very unlikely)
        program.share_token = generate_share_token()
        program.save(update_fields=["share_token"])
        return program.share_token

    @staticmethod
    @transaction.atomic
    def clone_program_for_user(*, source_program: Program, user_profile, name: str | None = None):
        cloned = Program.objects.create(
            name=name or f"{source_program.name} (Custom)",
            type=Program.ProgramType.CUSTOM,
            created_by=user_profile,
            level=source_program.level,
            goal=source_program.goal,
            is_template=False,
            description=source_program.description,
            image=source_program.image,
            is_active=True,
            is_premium=False,
            workout_type=source_program.workout_type,
        )

        for source_plan in source_program.plans.all():
            plan = Plan.objects.create(
                program=cloned,
                name=source_plan.name,
                order=source_plan.order,
                weeks_count=source_plan.weeks_count,
                is_4_week=source_plan.is_4_week,
                progression_config=source_plan.progression_config,
            )
            ProgramGenerationService.ensure_plan_weeks(plan)

            for source_week in source_plan.weeks.all():
                target_week = plan.weeks.get(week_number=source_week.week_number)
                for source_workout in source_week.workouts.all():
                    target_workout = Workout.objects.create(
                        week=target_week,
                        day_number=source_workout.day_number,
                        title=source_workout.title,
                        description=source_workout.description,
                        rounds=source_workout.rounds,
                    )
                    for source_exercise in source_workout.workout_exercises.all():
                        WorkoutExercise.objects.create(
                            workout=target_workout,
                            exercise=source_exercise.exercise,
                            sets=source_exercise.sets,
                            reps=source_exercise.reps,
                            minutes=source_exercise.minutes,
                            recommended_weight=source_exercise.recommended_weight,
                            order=source_exercise.order,
                        )

            ProgramGenerationService.ensure_home_plan_integrity(plan)
        return cloned