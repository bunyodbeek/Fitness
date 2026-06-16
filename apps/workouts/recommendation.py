from __future__ import annotations

from apps.models.workouts import Program


def _goal_short(goal: str) -> str:
    value = (goal or "").strip().lower()
    mapping = {
        "fat_loss": "FL",
        "lose_weight": "FL",
        "muscle_gain": "MG",
        "gain_muscle": "MG",
        "build_body": "MG",
        "recomposition": "RC",
        "get_shape": "RC",
    }
    return mapping.get(value, "")


def _gender_token(gender: str) -> str:
    value = (gender or "").strip().lower()
    return "Male" if value == "male" else "Female" if value == "female" else ""


def _level_token(level: str) -> str:
    value = (level or "").strip().lower()
    if value == "beginner":
        return "Beginner"
    if value in {"intermediate", "advanced"}:
        return "Advanced"
    return ""


def get_recommended_program(user_profile, workout_type: str | None = None) -> Program | None:
    """
    Build KEY = {goal_short}{gender}{level} (e.g. FLMaleBeginner)
    and return the best matching active Program.
    """
    if not user_profile:
        return None

    key = f"{_goal_short(getattr(user_profile, 'fitness_goal', ''))}{_gender_token(getattr(user_profile, 'gender', ''))}{_level_token(getattr(user_profile, 'experience_level', ''))}"
    if not key:
        return None

    key_goal = key[:2]
    key_gender = "male" if "Male" in key else "female"
    key_level = "beginner" if key.endswith("Beginner") else "advanced"

    goal_map = {
        "FL": Program.Goal.FAT_LOSS,
        "MG": Program.Goal.MUSCLE_GAIN,
        "RC": Program.Goal.RECOMPOSITION,
    }

    base_filter = dict(
        is_active=True,
        type=Program.ProgramType.ADMIN,
        goal=goal_map.get(key_goal),
        level=key_level,
    )
    if workout_type in {"gym", "home"}:
        base_filter["workout_type"] = workout_type

    # Tavsiya FAQAT individual (tavsiya) programmalar ichidan beriladi.
    individual = Program.objects.filter(
        **base_filter, is_individual=True, is_one_time=False,
    ).order_by("is_premium", "id").first()
    if individual:
        return individual

    # Maqsad/daraja bo'yicha mos kelmasa — istalgan individual programma (workout_type bo'yicha).
    fallback_qs = Program.objects.filter(
        is_active=True, type=Program.ProgramType.ADMIN, is_individual=True, is_one_time=False,
    )
    if workout_type in {"gym", "home"}:
        fallback = fallback_qs.filter(workout_type=workout_type).first()
        if fallback:
            return fallback
    return fallback_qs.first()
