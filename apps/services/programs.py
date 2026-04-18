import math

from django.db import transaction

from apps.models import Plan, Program, Week, Workout, WorkoutExercise
from apps.models.workouts import ProgressionSetting

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


# ─────────────────────────────────────────────
# ProgramGenerationService
# ─────────────────────────────────────────────

class ProgramGenerationService:

    @staticmethod
    def ensure_plan_weeks(plan):
        """Plan yaratilganda 1-6 haftalarni avtomatik yaratish."""
        for i in range(1, 7):
            Week.objects.get_or_create(plan=plan, week_number=i)

    @staticmethod
    def generate_progression_from_week_one(instance: WorkoutExercise):
        """
        1-haftadagi WorkoutExercise dan 2-6 haftalarni Sheets formula
        bo'yicha hisoblaydi va yaratadi / yangilaydi.
        """
        plan = instance.workout.week.plan
        config: ProgressionSetting = plan.progression_config

        if not config:
            return

        base_sets   = int(instance.sets or 0)
        base_reps   = int(instance.reps or 0)
        base_weight = float(instance.recommended_weight or 0)

        for week_num in range(2, 7):
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
            source_week_one__isnull=True,
        ).select_related("workout", "exercise")

        count = 0
        for seed in seeds:
            ProgramGenerationService.generate_progression_from_week_one(seed)
            count += 1
        return count


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
            Program.objects.filter(
                type=Program.ProgramType.ADMIN,
                level=profile.experience_level,
                goal=profile.fitness_goal,
                is_active=True,
            ).first()
            or Program.objects.filter(
                type=Program.ProgramType.ADMIN,
                is_active=True,
            ).first()
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
                weeks_count=6,
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
                            recommended_weight=source_exercise.recommended_weight,
                            order=source_exercise.order,
                        )
        return cloned