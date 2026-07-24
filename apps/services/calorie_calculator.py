"""Kaloriya hisoblash — YAGONA manba (single source of truth).

Ikki mashg'ulot turi, ikki formula:

* GYM  — setlar/takrorlar (sets/reps) asosida.
* HOME — raundlar/vaqt (rounds/time) asosida.

Bu modul ikki qatlamdan iborat:

1. **Toza formula funksiyalari** (`calculate_gym`, `calculate_home`) — Django
   modellariga bog'liq EMAS, faqat raqamlar bilan ishlaydi. Barcha birliklar aniq
   belgilangan (vaqt — SEKUND, WorkoutTimer — sekund). Testlar shu qatlamni tekshiradi.
2. **Model adapterlari** (`calories_for_gym_workout`, `calories_for_home_workout`) —
   `Workout` + `UserProfile` dan formula kirishlarini yig'adi va model birliklarini
   to'g'ri konvertatsiya qiladi.

Formula mos yozuvlar (reference) 70 kg odam uchun kalibrlangan; foydalanuvchi vazniga
`UserWeight / 70` koeffitsienti orqali moslashtiriladi.

Kirish maydonlari (admin panelidagi mavjud maydonlardan o'qiladi, o'zgartirilmaydi):
  * Exercise1repCal  -> ``Exercise.calory``   (1 takror uchun kaloriya)
  * Exercise1repTime -> ``Exercise.duration`` (1 takror davomiyligi, SEKUND)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("apps.calorie")

# Formula konstantalari.
REFERENCE_WEIGHT_KG = 70.0   # formulalar kalibrlangan mos yozuvlar vazni
DEFAULT_WEIGHT_KG = 70.0     # vazn yo'q bo'lsa zaxira qiymat
_REST_MET = 1.3              # dam olish (rest) davridagi MET
_OXYGEN_FACTOR = 3.5         # ml/kg/min kislorod iste'moli koeffitsienti
_REST_DIVISOR = 200.0        # rest formulasi maxraji


# ---------------------------------------------------------------------------
# Kirish / natija strukturalari
# ---------------------------------------------------------------------------

@dataclass
class GymExerciseInput:
    rep_cal: float       # Exercise1repCal — 1 takror uchun kaloriya
    rep_time_sec: float  # Exercise1repTime — 1 takror davomiyligi (sekund)
    sets: int
    reps: int


@dataclass
class HomeExerciseInput:
    rep_cal: float             # Exercise1repCal
    rep_time_sec: float        # Exercise1repTime (sekund)
    time_in_round_sec: float   # TimePer1ExerciseInRound (sekund)


@dataclass
class CalorieResult:
    total_calories: int          # ko'rsatish uchun butun songa yaxlitlangan kkal
    total_calories_raw: float    # yaxlitlashdan oldingi qiymat (debug/test uchun)
    exercise_calories: float     # Total_Exercise_Cal
    rest_calories: float         # Rest_Cal
    timer_minutes: int           # yuqoriga yaxlitlangan daqiqa
    weight_kg: float             # ishlatilgan vazn (zaxira bo'lishi mumkin)
    is_estimated: bool           # vazn zaxira (70 kg) bilan hisoblangan bo'lsa True
    skipped_exercises: int = 0   # xavfsiz o'tkazib yuborilgan mashqlar soni (masalan repTime=0)


# ---------------------------------------------------------------------------
# Yordamchi funksiyalar
# ---------------------------------------------------------------------------

def ceil_minutes(timer_seconds) -> int:
    """WorkoutTimer (sekund) ni DOIM yuqoriga to'liq daqiqaga yaxlitlaydi.

    Masalan 54:13 (3253s) -> 55 daqiqa. Manfiy/bo'sh -> 0.
    """
    try:
        seconds = float(timer_seconds)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(seconds) or seconds <= 0:
        return 0
    return math.ceil(seconds / 60.0)


def resolve_weight(weight) -> tuple[float, bool]:
    """Foydalanuvchi vaznini aniqlaydi.

    Yo'q / 0 / yaroqsiz -> (70 kg, is_estimated=True). Aks holda (vazn, False).
    """
    try:
        w = float(weight)
    except (TypeError, ValueError):
        w = 0.0
    if not math.isfinite(w) or w <= 0:
        return DEFAULT_WEIGHT_KG, True
    return w, False


def _round_kcal(value: float) -> int:
    """Yakuniy kaloriyani butun songa yaxlitlaydi (ko'rsatish uchun)."""
    if not math.isfinite(value) or value <= 0:
        return 0
    return int(round(value))


def _rest_calories(rest_minutes: float, weight_kg: float) -> float:
    """Vaqtga asoslangan dam olish kaloriyasi (ikkala formulada ham bir xil ko'rinish).

    Rest_Cal = daqiqa * 1.3 * 3.5 * UserWeight / 200
    """
    rest_minutes = max(0.0, rest_minutes)  # hech qachon manfiy bo'lmaydi
    return rest_minutes * _REST_MET * _OXYGEN_FACTOR * weight_kg / _REST_DIVISOR


# ---------------------------------------------------------------------------
# Toza formula funksiyalari
# ---------------------------------------------------------------------------

def calculate_gym(
    exercises: List[GymExerciseInput],
    timer_seconds,
    weight,
) -> CalorieResult:
    """GYM mashg'uloti uchun umumiy kaloriya.

    Har bir mashq uchun:
      Exercise_Cal = (Exercise1repCal / 100) * Exercise1repTime * Sets * Reps * (UserWeight / 70)
    Total_Exercise_Cal = Σ Exercise_Cal
    Rest_Cal = WorkoutTimer(min) * 1.3 * 3.5 * UserWeight / 200
    Total_Calories = Total_Exercise_Cal + Rest_Cal
    """
    weight_kg, is_estimated = resolve_weight(weight)
    minutes = ceil_minutes(timer_seconds)
    weight_factor = weight_kg / REFERENCE_WEIGHT_KG

    total_exercise_cal = 0.0
    for ex in exercises:
        rep_cal = _safe_num(ex.rep_cal)
        rep_time = _safe_num(ex.rep_time_sec)
        sets = _safe_num(ex.sets)
        reps = _safe_num(ex.reps)
        total_exercise_cal += (rep_cal / 100.0) * rep_time * sets * reps * weight_factor

    rest_cal = _rest_calories(minutes, weight_kg)
    total = total_exercise_cal + rest_cal

    return CalorieResult(
        total_calories=_round_kcal(total),
        total_calories_raw=total,
        exercise_calories=total_exercise_cal,
        rest_calories=rest_cal,
        timer_minutes=minutes,
        weight_kg=weight_kg,
        is_estimated=is_estimated,
    )


def calculate_home(
    exercises: List[HomeExerciseInput],
    rounds,
    timer_seconds,
    weight,
    time_per_round_sec: Optional[float] = None,
) -> CalorieResult:
    """HOME mashg'uloti uchun umumiy kaloriya.

    Har bir mashq uchun (barcha vaqtlar SEKUNDda, konvertatsiya YO'Q):
      Exercise_Cal = (Exercise1repCal / 100 / Exercise1repTime) * (UserWeight / 70)
                     * (Rounds * TimePer1ExerciseInRound)

    Rest_Cal — faqat mashq QILINMAGAN vaqt. TimePerRound SEKUNDda, shuning uchun
    mashq vaqtini daqiqaga o'tkazamiz:
      ActiveTime(min) = (Rounds * TimePerRound) / 60
      Rest_Cal = max(0, WorkoutTimer(min) - ActiveTime(min)) * 1.3 * 3.5 * UserWeight / 200

    ``time_per_round_sec`` (bir raunddagi umumiy mashq vaqti, sekund) berilmasa —
    mashqlarning ``time_in_round_sec`` yig'indisidan olinadi (dam olish vaqtisiz).
    """
    weight_kg, is_estimated = resolve_weight(weight)
    minutes = ceil_minutes(timer_seconds)
    weight_factor = weight_kg / REFERENCE_WEIGHT_KG
    rounds = _safe_num(rounds)

    total_exercise_cal = 0.0
    skipped = 0
    for ex in exercises:
        rep_time = _safe_num(ex.rep_time_sec)
        # HOME formulasi Exercise1repTime ga BO'LADI — 0/yo'q bo'lsa nol bo'lishga
        # bo'linishni oldini olib, mashqni xavfsiz o'tkazib yuboramiz va ogohlantirish yozamiz.
        if rep_time <= 0:
            skipped += 1
            logger.warning(
                "HOME kaloriya: Exercise1repTime=0/yo'q — mashq o'tkazib yuborildi "
                "(rep_cal=%s, time_in_round=%s).",
                ex.rep_cal, ex.time_in_round_sec,
            )
            continue
        rep_cal = _safe_num(ex.rep_cal)
        time_in_round = _safe_num(ex.time_in_round_sec)
        total_exercise_cal += (
            (rep_cal / 100.0 / rep_time) * weight_factor * (rounds * time_in_round)
        )

    if time_per_round_sec is None:
        time_per_round_sec = sum(_safe_num(ex.time_in_round_sec) for ex in exercises)

    active_minutes = (rounds * _safe_num(time_per_round_sec)) / 60.0
    rest_minutes = max(0.0, minutes - active_minutes)  # manfiy bo'lsa 0 ga qisamiz
    rest_cal = _rest_calories(rest_minutes, weight_kg)
    total = total_exercise_cal + rest_cal

    return CalorieResult(
        total_calories=_round_kcal(total),
        total_calories_raw=total,
        exercise_calories=total_exercise_cal,
        rest_calories=rest_cal,
        timer_minutes=minutes,
        weight_kg=weight_kg,
        is_estimated=is_estimated,
        skipped_exercises=skipped,
    )


def _safe_num(value, default: float = 0.0) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return n if math.isfinite(n) else default


# ---------------------------------------------------------------------------
# Model adapterlari — Workout/UserProfile dan formula kirishlarini yig'adi.
# ---------------------------------------------------------------------------

def calories_for_gym_workout(workout, timer_seconds, profile) -> CalorieResult:
    """GYM ``Workout`` yakunlanganda kaloriyani hisoblaydi.

    Sets/reps ``WorkoutExercise`` dan, rep_cal/rep_time esa bog'langan
    ``Exercise`` maydonlaridan (``calory`` / ``duration``) olinadi.
    """
    exercises = []
    for wex in workout.workout_exercises.select_related("exercise").all():
        ex = wex.exercise
        exercises.append(GymExerciseInput(
            rep_cal=getattr(ex, "calory", 0) or 0,
            rep_time_sec=getattr(ex, "duration", 0) or 0,
            sets=wex.sets or 0,
            reps=wex.reps or 0,
        ))
    weight = getattr(profile, "weight", None)
    return calculate_gym(exercises, timer_seconds, weight)


def calories_for_home_workout(workout, timer_seconds, profile) -> CalorieResult:
    """HOME ``Workout`` yakunlanganda kaloriyani hisoblaydi.

    Raundlar va bir raunddagi mashq vaqti (sekund) jonli sessiya pleyeri bilan bir xil
    tarzda — ``calculate_home_week_exercise`` orqali hafta progressiyasiga moslab olinadi.
    ``WorkoutExercise.minutes`` maydoni HOME uchun SEKUNDda saqlanadi (pleyer uni
    ``base_duration_seconds`` sifatida ishlatadi), shuning uchun konvertatsiya shart emas.
    """
    from apps.models.workouts import HomeProgressionSetting
    from apps.utils.home_progression import calculate_home_week_exercise

    setting = HomeProgressionSetting.objects.first()
    week_number = getattr(getattr(workout, "week", None), "week_number", 1) or 1

    exercises = []
    rounds = workout.rounds or 1
    for wex in workout.workout_exercises.select_related("exercise").all():
        ex = wex.exercise
        base_seconds = int(wex.minutes or 0)
        if setting is not None:
            calc = calculate_home_week_exercise(workout.rounds, base_seconds, week_number, setting)
            rounds = calc["rounds"]
            time_in_round = calc["duration_seconds"]
        else:
            # Progressiya sozlamasi yo'q — bazaviy qiymatlardan foydalanamiz.
            time_in_round = base_seconds
        exercises.append(HomeExerciseInput(
            rep_cal=getattr(ex, "calory", 0) or 0,
            rep_time_sec=getattr(ex, "duration", 0) or 0,
            time_in_round_sec=time_in_round,
        ))

    weight = getattr(profile, "weight", None)
    return calculate_home(exercises, rounds, timer_seconds, weight)
