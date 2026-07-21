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

    goal_map = {
        "FL": Program.Goal.FAT_LOSS,
        "MG": Program.Goal.MUSCLE_GAIN,
        "RC": Program.Goal.RECOMPOSITION,
    }

    # ── Home rejimi: tavsiya "home" rejimidagi ADVANCED (murakkab) programmalardan
    # tanlanadi — individual (tavsiya) bo'lishi shart emas. Avval foydalanuvchi
    # maqsadiga mos keladigani, bo'lmasa istalgan advanced home programma. ──
    if workout_type == "home":
        home_qs = Program.objects.filter(
            is_active=True,
            type=Program.ProgramType.ADMIN,
            workout_type="home",
            level=Program.Level.ADVANCED,
            is_one_time=False,
        )
        goal = goal_map.get(_goal_short(getattr(user_profile, "fitness_goal", "")))
        if goal:
            match = home_qs.filter(goal=goal).order_by("is_premium", "id").first()
            if match:
                return match
        return home_qs.order_by("is_premium", "id").first()

    key = f"{_goal_short(getattr(user_profile, 'fitness_goal', ''))}{_gender_token(getattr(user_profile, 'gender', ''))}{_level_token(getattr(user_profile, 'experience_level', ''))}"
    if not key:
        return None

    key_goal = key[:2]
    key_gender = "male" if "Male" in key else "female"
    key_level = "beginner" if key.endswith("Beginner") else "advanced"

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
        # Tanlangan rejim talab qilingan bo'lsa — FAQAT shu rejim ichidan qaytaramiz.
        # Aks holda boshqa rejim programmasi qaytib, detail havolasi 404 berishi mumkin.
        return fallback_qs.filter(workout_type=workout_type).first()
    return fallback_qs.first()
