"""Tavsiya (recommended program) tanlash mezoni testlari.

Asosiy tuzatish: tavsiya foydalanuvchi tanlagan haftalik mashg'ulot kunlari soniga
(``workout_days_per_week``) mos kelishi kerak — ilgari u e'tiborga olinmay, doim
eng eski (masalan 2 kunlik) programma tanlanardi.
"""

from django.test import TestCase

from apps.models.users import User, UserProfile
from apps.models.workouts import Plan, Program, Week, Workout, WorkoutType
from apps.workouts.recommendation import get_recommended_program


def _make_individual_program(*, goal, level, days, name, workout_type=WorkoutType.GYM,
                             is_premium=False, is_individual=True):
    """1-haftasida ``days`` ta kun (workout) bo'lgan admin programma yaratadi."""
    program = Program.objects.create(
        type=Program.ProgramType.ADMIN,
        is_individual=is_individual,
        is_one_time=False,
        is_active=True,
        workout_type=workout_type,
        goal=goal,
        level=level,
        is_premium=is_premium,
        name=name,
    )
    plan = Plan.objects.create(program=program, name=f"{name}-plan", order=1, weeks_count=6)
    week = Week.objects.create(plan=plan, week_number=1)
    for d in range(days):
        Workout.objects.create(week=week, day_number=d + 1, rounds=1)
    return program


def _make_profile(*, goal="build_body", experience="beginner", days=4):
    user = User.objects.create(username=f"u{User.objects.count()}")
    return UserProfile.objects.create(
        user=user,
        fitness_goal=goal,
        experience_level=experience,
        workout_days_per_week=days,
    )


class GymDaysMatchingTests(TestCase):
    def test_picks_program_matching_selected_days(self):
        # build_body -> MUSCLE_GAIN, beginner -> BEGINNER. Ikkita mos programma,
        # faqat kunlar soni farq qiladi.
        two_day = _make_individual_program(
            goal=Program.Goal.MUSCLE_GAIN, level=Program.Level.BEGINNER, days=2, name="2day",
        )
        four_day = _make_individual_program(
            goal=Program.Goal.MUSCLE_GAIN, level=Program.Level.BEGINNER, days=4, name="4day",
        )

        profile = _make_profile(days=4)
        picked = get_recommended_program(profile)
        self.assertEqual(picked, four_day)

        # Kunlarni o'zgartirsa — tavsiya ham o'zgaradi (eski xatoning aynan aksi).
        profile.workout_days_per_week = 2
        profile.save(update_fields=["workout_days_per_week"])
        self.assertEqual(get_recommended_program(profile), two_day)

    def test_no_exact_match_falls_back_to_closest_days(self):
        three = _make_individual_program(
            goal=Program.Goal.MUSCLE_GAIN, level=Program.Level.BEGINNER, days=3, name="3day",
        )
        _make_individual_program(
            goal=Program.Goal.MUSCLE_GAIN, level=Program.Level.BEGINNER, days=6, name="6day",
        )
        profile = _make_profile(days=4)  # 3 (farq 1) vs 6 (farq 2) -> 3 kunlik
        self.assertEqual(get_recommended_program(profile), three)

    def test_days_matching_within_goal_and_level_tier(self):
        # Boshqa maqsaddagi 4-kunlik programma tanlanmasligi kerak — avval maqsad+daraja.
        _make_individual_program(
            goal=Program.Goal.FAT_LOSS, level=Program.Level.BEGINNER, days=4, name="fl4",
        )
        mg_three = _make_individual_program(
            goal=Program.Goal.MUSCLE_GAIN, level=Program.Level.BEGINNER, days=3, name="mg3",
        )
        profile = _make_profile(goal="build_body", days=4)  # MG
        # MG tier'ida faqat 3-kunlik bor -> u tanlanadi (FL4 emas).
        self.assertEqual(get_recommended_program(profile), mg_three)

    def test_missing_days_returns_deterministic_first(self):
        first = _make_individual_program(
            goal=Program.Goal.MUSCLE_GAIN, level=Program.Level.BEGINNER, days=2, name="a",
        )
        _make_individual_program(
            goal=Program.Goal.MUSCLE_GAIN, level=Program.Level.BEGINNER, days=5, name="b",
        )
        profile = _make_profile(days=None)
        # Kunlar yo'q -> (is_premium, id) tartibidagi birinchi.
        self.assertEqual(get_recommended_program(profile), first)


class HomeDaysMatchingTests(TestCase):
    def test_home_recommendation_matches_days(self):
        two = _make_individual_program(
            goal=Program.Goal.MUSCLE_GAIN, level=Program.Level.ADVANCED, days=2,
            name="h2", workout_type=WorkoutType.HOME, is_individual=False,
        )
        five = _make_individual_program(
            goal=Program.Goal.MUSCLE_GAIN, level=Program.Level.ADVANCED, days=5,
            name="h5", workout_type=WorkoutType.HOME, is_individual=False,
        )
        profile = _make_profile(days=5)
        self.assertEqual(get_recommended_program(profile, workout_type="home"), five)

        profile.workout_days_per_week = 2
        profile.save(update_fields=["workout_days_per_week"])
        self.assertEqual(get_recommended_program(profile, workout_type="home"), two)
