import math

from django.db import transaction

from apps.models import Plan, Program, Week, Workout, WorkoutExercise
from apps.models.workouts import ProgressionSetting, HomeProgressionSetting
from apps.utils.tokens import generate_share_token
from apps.workouts.recommendation import get_recommended_program

try:
    from apps.models import UserProgram
except ImportError:
    UserProgram = None



def _roundup_to_2_5(value: float) -> float:
    return math.ceil(float(value) / 2.5) * 2.5


def _calc_weight(base_weight: float, multiplier: float,
                 small_threshold: float, small_boost: float) -> float:
    """
    Sheets formula:
    =ROUNDUP(MAX(base*mult, IF(base<threshold, base+boost, base+2.5))/2.5, 0)*2.5
    Agar natija <= base bo'lsa → base + 2.5
    """
    base_weight = float(base_weight or 0)
    opt1 = base_weight * float(multiplier)
    opt2 = (base_weight + float(small_boost)
            if base_weight < float(small_threshold)
            else base_weight + 2.5)
    result = _roundup_to_2_5(max(opt1, opt2))
    if result <= base_weight:
        result = base_weight + 2.5
    return result


# Hafta raqami → ProgressionSetting field nomlari
WEEK_FIELD_MAP = {
    2: ("w2_weight_mult", "set_w2", "rep_w2"),
    3: ("w3_weight_mult", "set_w3", "rep_w3"),
    4: ("w4_weight_mult", "set_w4", "rep_w4"),
    5: ("w5_weight_mult", "set_w5", "rep_w5"),
    6: ("w6_deload_mult", "set_w6", "rep_w6"),
}


class ProgramGenerationService:

    @staticmethod
    def ensure_plan_weeks(plan):
        """Plan yaratilganda haftalarni avtomatik yaratish."""
        max_weeks = 4 if getattr(plan, "is_4_week", False) else 6
        for i in range(1, max_weeks + 1):
            Week.objects.get_or_create(plan=plan, week_number=i)

    @staticmethod
    def generate_progression_from_week_one(instance: WorkoutExercise):
        print(f"DEBUG generate called: exercise_id={instance.id}, week={instance.workout.week.week_number}")

        plan = instance.workout.week.plan
        config: ProgressionSetting = plan.progression_config
        print(f"DEBUG config={config}, plan={plan}")

        if not config:
            print("DEBUG: config None, returning!")
            return

        base_sets   = int(instance.sets or 0)
        base_reps   = int(instance.reps or 0)
        base_weight = float(instance.recommended_weight or 0)

        max_weeks = 4 if getattr(plan, "is_4_week", False) else 6
        for week_num in range(2, max_weeks + 1):
            weight_field, set_field, rep_field = WEEK_FIELD_MAP[week_num]

            weight_mult   = getattr(config, weight_field)
            set_increment = getattr(config, set_field)
            rep_increment = getattr(config, rep_field)

            new_sets   = max(0, base_sets + int(set_increment))
            new_reps   = max(6, base_reps + int(rep_increment))
            new_weight = _calc_weight(
                base_weight, weight_mult,
                config.small_threshold, config.small_boost,
            )

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

            WorkoutExercise.objects.update_or_create(
                workout=target_workout,
                exercise=instance.exercise,
                defaults={
                    "sets":               new_sets,
                    "reps":               new_reps,
                    "recommended_weight": new_weight,
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