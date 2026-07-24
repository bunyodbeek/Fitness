"""Mashg'ulot yakuni endpointlari Telegram webview'idan CSRF token'siz ham
ishlashini tekshiradi (cross-origin webview'da CSRF cookie ishonchsiz).

`enforce_csrf_checks=True` — CsrfViewMiddleware'ni jonli simulyatsiya qiladi;
exemptsiz bu POST 403 (CSRF) qaytarardi.
"""

from django.test import Client, TestCase
from django.urls import reverse

from apps.models.exercises import Exercise
from apps.models.users import User, UserProfile
from apps.models.workouts import (
    Plan, Program, Week, Workout, WorkoutExercise, WorkoutProgress, WorkoutType,
)


class HomeCompleteCsrfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="csrf_user")
        self.profile = UserProfile.objects.create(user=self.user, weight=70)
        program = Program.objects.create(
            type=Program.ProgramType.ADMIN, workout_type=WorkoutType.HOME,
            is_active=True, name="H",
        )
        plan = Plan.objects.create(program=program, name="pl", order=1, weeks_count=6)
        week = Week.objects.create(plan=plan, week_number=1)  # 1-hafta = bepul preview
        self.workout = Workout.objects.create(week=week, day_number=1, rounds=2)
        ex = Exercise.objects.create(name="E", calory=50, duration=2)
        WorkoutExercise.objects.create(workout=self.workout, exercise=ex, minutes=30, order=1)

    def test_home_complete_post_without_csrf_token_is_not_403(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        url = reverse("home_workout_complete", args=[self.workout.pk])
        # CSRF token YO'Q — webview holatini taqlid qiladi.
        resp = client.post(url, {"total_duration": 600})

        self.assertNotEqual(resp.status_code, 403)
        self.assertEqual(resp.status_code, 200)
        # Kaloriya server tomonda hisoblanib, tarix yozuvi yaratilgan bo'lishi kerak.
        progress = WorkoutProgress.objects.filter(user=self.profile, workout=self.workout).first()
        self.assertIsNotNone(progress)
        self.assertGreater(progress.total_calories, 0)
