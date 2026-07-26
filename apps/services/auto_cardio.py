import threading
from contextlib import contextmanager

from django.db import transaction

_local = threading.local()


def tombstone_suppressed() -> bool:
    return getattr(_local, "depth", 0) > 0


@contextmanager
def suppress_cardio_tombstone():
    _local.depth = getattr(_local, "depth", 0) + 1
    try:
        yield
    finally:
        _local.depth -= 1


def program_cardio_config(program):
    if not program or not program.auto_cardio_enabled:
        return None
    exercise = program.auto_cardio_exercise
    if not exercise:
        return None
    return {
        "exercise": exercise,
        "sets": max(int(program.auto_cardio_sets or 1), 1),
        "duration_seconds": max(int(program.auto_cardio_duration_seconds or 0), 1),
    }


def ensure_day_cardio(workout, config=None):
    from apps.models.workouts import WorkoutExercise

    if workout.cardio_removed:
        return False

    program = workout.week.plan.program
    config = config or program_cardio_config(program)
    if not config:
        return False

    existing = WorkoutExercise.objects.filter(workout=workout, is_auto_cardio=True).first()
    if existing:
        if not existing.is_weight_manual:
            changed = False
            if existing.exercise_id != config["exercise"].id:
                existing.exercise = config["exercise"]
                changed = True
            if existing.sets != config["sets"]:
                existing.sets = config["sets"]
                changed = True
            if existing.duration_seconds != config["duration_seconds"]:
                existing.duration_seconds = config["duration_seconds"]
                changed = True
            if changed:
                with suppress_cardio_tombstone():
                    existing.save(update_fields=["exercise", "sets", "duration_seconds"])
        return False

    first_order = (
        WorkoutExercise.objects.filter(workout=workout)
        .exclude(is_auto_cardio=True)
        .order_by("order")
        .values_list("order", flat=True)
        .first()
    )
    order = (first_order - 1) if first_order is not None else 0

    with suppress_cardio_tombstone():
        WorkoutExercise.objects.create(
            workout=workout,
            exercise=config["exercise"],
            sets=config["sets"],
            reps=0,
            duration_seconds=config["duration_seconds"],
            is_auto_cardio=True,
            order=order,
        )
    return True


def ensure_plan_cardio(plan) -> int:
    from apps.models.workouts import Workout

    config = program_cardio_config(plan.program)
    if not config:
        return 0

    created = 0
    workouts = Workout.objects.filter(week__plan=plan).select_related("week__plan__program")
    with transaction.atomic():
        for workout in workouts:
            if ensure_day_cardio(workout, config):
                created += 1
    return created
