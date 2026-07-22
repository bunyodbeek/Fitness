from __future__ import annotations

from apps.models.workouts import Program


# Questionnaire goal value  →  short code  →  Program.Goal.
_GOAL_SHORT = {
    "fat_loss": "FL",
    "lose_weight": "FL",
    "muscle_gain": "MG",
    "gain_muscle": "MG",
    "build_body": "MG",
    "recomposition": "RC",
    "get_shape": "RC",
}

_GOAL_MAP = {
    "FL": Program.Goal.FAT_LOSS,
    "MG": Program.Goal.MUSCLE_GAIN,
    "RC": Program.Goal.RECOMPOSITION,
}


def _profile_goal(user_profile):
    """Map the profile's questionnaire goal to a ``Program.Goal`` (or None)."""
    value = (getattr(user_profile, "fitness_goal", "") or "").strip().lower()
    return _GOAL_MAP.get(_GOAL_SHORT.get(value, ""))


def _profile_level(user_profile) -> str:
    """Collapse experience to the two program levels: beginner / advanced."""
    value = (getattr(user_profile, "experience_level", "") or "").strip().lower()
    if value == "beginner":
        return Program.Level.BEGINNER
    if value in {"intermediate", "advanced"}:
        return Program.Level.ADVANCED
    return ""


def _ordered(qs):
    # Free programs first (is_premium False < True), then oldest id — deterministic.
    return qs.order_by("is_premium", "id")


def _recommend_home(goal) -> Program | None:
    """Home tavsiyasi: "home" rejimidagi ADVANCED programmalardan tanlanadi
    (individual bo'lishi shart emas). Avval foydalanuvchi maqsadiga mos keladigani,
    bo'lmasa istalgan advanced home programma."""
    base = Program.objects.filter(
        is_active=True,
        type=Program.ProgramType.ADMIN,
        workout_type="home",
        level=Program.Level.ADVANCED,
        is_one_time=False,
    )
    if goal:
        match = _ordered(base.filter(goal=goal)).first()
        if match:
            return match
    return _ordered(base).first()


def _recommend_gym(goal, level, workout_type) -> Program | None:
    """Gym tavsiyasi FAQAT individual (tavsiya) programmalar ichidan beriladi.

    Moslik bosqichma-bosqich yumshaydi, shunda foydalanuvchi savolnomani qayta
    to'ldirib MAQSADINI o'zgartirsa, tavsiya ham o'zgaradi (aniq goal+level
    programma bo'lmasa ham). Tartib: goal+level → goal → level → istalgani."""
    base = Program.objects.filter(
        is_active=True,
        type=Program.ProgramType.ADMIN,
        is_individual=True,
        is_one_time=False,
    )
    # Tanlangan rejim talab qilingan bo'lsa — faqat shu rejim ichidan (aks holda
    # boshqa rejim programmasi qaytib, detail havolasi 404 berishi mumkin).
    if workout_type in {"gym", "home"}:
        base = base.filter(workout_type=workout_type)

    # 1) Aniq: maqsad + daraja.
    if goal and level:
        match = _ordered(base.filter(goal=goal, level=level)).first()
        if match:
            return match
    # 2) Faqat maqsad bo'yicha — maqsad o'zgarsa tavsiya doim o'zgarishini
    #    ta'minlaydi (aynan shu daraja uchun programma bo'lmasa ham).
    if goal:
        match = _ordered(base.filter(goal=goal)).first()
        if match:
            return match
    # 3) Faqat daraja bo'yicha.
    if level:
        match = _ordered(base.filter(level=level)).first()
        if match:
            return match
    # 4) Istalgan individual programma (rejim bo'yicha).
    return _ordered(base).first()


def get_recommended_program(user_profile, workout_type: str | None = None) -> Program | None:
    """Foydalanuvchi profiliga mos eng yaxshi tavsiya programmasini qaytaradi.

    Gym: admin qo'shgan individual (tavsiya) programmalardan.
    Home: "home" rejimidagi ADVANCED programmalardan.
    """
    if not user_profile:
        return None

    goal = _profile_goal(user_profile)
    level = _profile_level(user_profile)

    if workout_type == "home":
        return _recommend_home(goal)

    return _recommend_gym(goal, level, workout_type)
