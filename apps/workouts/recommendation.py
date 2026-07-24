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


def _profile_days(user_profile):
    """Foydalanuvchi tanlagan haftalik mashg'ulot kunlari soni (yoki None)."""
    value = getattr(user_profile, "workout_days_per_week", None)
    try:
        days = int(value)
    except (TypeError, ValueError):
        return None
    return days if days > 0 else None


def _program_days_per_week(program) -> int | None:
    """Programmaning haftalik kunlar soni = uning BIRINCHI planidagi 1-haftaning
    mashg'ulotlari (kunlari) soni. ``Plan.days_per_week`` bilan bir xil mantiq,
    lekin prefetch qilingan bog'lanishlardan foydalanadi (qo'shimcha so'rovsiz)."""
    plan = min(program.plans.all(), key=lambda p: (p.order, p.id), default=None)
    if not plan:
        return None
    for week in plan.weeks.all():
        if week.week_number == 1:
            count = len(week.workouts.all())
            return count or None
    return None


def _ordered(qs):
    # Free programs first (is_premium False < True), then oldest id — deterministic.
    return qs.order_by("is_premium", "id")


def _pick(qs, desired_days) -> Program | None:
    """Nomzodlar ichidan eng mosini tanlaydi.

    Avval foydalanuvchi tanlagan kunlar soniga AYNAN mos keladigani (``is_premium``,
    ``id`` tartibida birinchisi); bo'lmasa kunlar soni bo'yicha eng yaqini. Kunlar
    talab qilinmagan (None) bo'lsa — oddiy tartibdagi birinchisi.
    """
    candidates = list(_ordered(qs).prefetch_related("plans__weeks__workouts"))
    if not candidates:
        return None
    if not desired_days:
        return candidates[0]

    # Nomzodlar allaqachon (is_premium, id) bo'yicha tartiblangan, shuning uchun
    # `min` teng farqlarda birinchi (eng afzal) nomzodni saqlaydi. Kunlari
    # aniqlanmagan programmalar oxiriga suriladi.
    def distance(program):
        days = _program_days_per_week(program)
        if days is None:
            return (1, 0)          # kunlari noma'lum — eng oxirida
        return (0, abs(days - desired_days))

    return min(candidates, key=distance)


def _recommend_home(goal, desired_days) -> Program | None:
    """Home tavsiyasi: "home" rejimidagi ADVANCED programmalardan tanlanadi
    (individual bo'lishi shart emas). Avval foydalanuvchi maqsadiga mos keladigani,
    bo'lmasa istalgan advanced home programma — har bosqichda kunlar soniga qarab
    eng mosi tanlanadi."""
    base = Program.objects.filter(
        is_active=True,
        type=Program.ProgramType.ADMIN,
        workout_type="home",
        level=Program.Level.ADVANCED,
        is_one_time=False,
    )
    if goal:
        match = _pick(base.filter(goal=goal), desired_days)
        if match:
            return match
    return _pick(base, desired_days)


def _recommend_gym(goal, level, workout_type, desired_days) -> Program | None:
    """Gym tavsiyasi FAQAT individual (tavsiya) programmalar ichidan beriladi.

    Moslik bosqichma-bosqich yumshaydi, shunda foydalanuvchi savolnomani qayta
    to'ldirib MAQSADINI o'zgartirsa, tavsiya ham o'zgaradi (aniq goal+level
    programma bo'lmasa ham). Tartib: goal+level → goal → level → istalgani.
    Har bir bosqichda foydalanuvchi tanlagan haftalik kunlar soniga eng mos
    keladigan programma tanlanadi (aynan mos, bo'lmasa eng yaqini)."""
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
        match = _pick(base.filter(goal=goal, level=level), desired_days)
        if match:
            return match
    # 2) Faqat maqsad bo'yicha — maqsad o'zgarsa tavsiya doim o'zgarishini
    #    ta'minlaydi (aynan shu daraja uchun programma bo'lmasa ham).
    if goal:
        match = _pick(base.filter(goal=goal), desired_days)
        if match:
            return match
    # 3) Faqat daraja bo'yicha.
    if level:
        match = _pick(base.filter(level=level), desired_days)
        if match:
            return match
    # 4) Istalgan individual programma (rejim bo'yicha).
    return _pick(base, desired_days)


def get_recommended_program(user_profile, workout_type: str | None = None) -> Program | None:
    """Foydalanuvchi profiliga mos eng yaxshi tavsiya programmasini qaytaradi.

    Tanlash mezoni: maqsad (goal) + daraja (experience) + haftalik mashg'ulot
    kunlari soni (workout_days_per_week). Vazn (weight) programma tanlashda emas,
    mashqlarning ishchi og'irliklarini hisoblashda ishlatiladi (training_calculator).

    Gym: admin qo'shgan individual (tavsiya) programmalardan.
    Home: "home" rejimidagi ADVANCED programmalardan.
    """
    if not user_profile:
        return None

    goal = _profile_goal(user_profile)
    level = _profile_level(user_profile)
    desired_days = _profile_days(user_profile)

    if workout_type == "home":
        return _recommend_home(goal, desired_days)

    return _recommend_gym(goal, level, workout_type, desired_days)
