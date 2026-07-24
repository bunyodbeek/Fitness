"""Kaloriya hisoblash formulasi testlari (apps/services/calorie_calculator.py).

Toza formula qatlamini tekshiradi — DB shart emas, shuning uchun SimpleTestCase.
Kamida bitta test qo'lda hisoblangan kutilgan qiymat bilan formulani spetsifikatsiyaga
aniq mosligini tasdiqlaydi.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.services.calorie_calculator import (
    GymExerciseInput,
    HomeExerciseInput,
    calculate_gym,
    calculate_home,
    calories_for_gym_workout,
    ceil_minutes,
    resolve_weight,
)


class CeilMinutesTests(SimpleTestCase):
    def test_rounds_up_to_next_whole_minute(self):
        # 54:13 -> 55 daqiqa (spetsifikatsiyadagi misol).
        self.assertEqual(ceil_minutes(54 * 60 + 13), 55)

    def test_exact_minute_not_rounded_up(self):
        self.assertEqual(ceil_minutes(54 * 60), 54)

    def test_one_second_over_rounds_up(self):
        self.assertEqual(ceil_minutes(54 * 60 + 1), 55)
        self.assertEqual(ceil_minutes(61), 2)
        self.assertEqual(ceil_minutes(60), 1)
        self.assertEqual(ceil_minutes(1), 1)

    def test_zero_and_negative_and_invalid(self):
        self.assertEqual(ceil_minutes(0), 0)
        self.assertEqual(ceil_minutes(-10), 0)
        self.assertEqual(ceil_minutes(None), 0)
        self.assertEqual(ceil_minutes("abc"), 0)


class ResolveWeightTests(SimpleTestCase):
    def test_missing_or_zero_falls_back_to_70_and_flags_estimated(self):
        for bad in (None, 0, 0.0, "", "abc", -5):
            weight, estimated = resolve_weight(bad)
            self.assertEqual(weight, 70.0)
            self.assertTrue(estimated)

    def test_valid_weight_used_as_is(self):
        weight, estimated = resolve_weight(82.5)
        self.assertEqual(weight, 82.5)
        self.assertFalse(estimated)


class GymFormulaTests(SimpleTestCase):
    def test_six_exercise_gym_hand_calculated(self):
        """6 mashqli GYM mashg'uloti — qo'lda hisoblangan kutilgan qiymat.

        weight = 70 (koeffitsient = 1, formulani ajratib ko'rsatadi):
          Exercise_Cal = (rep_cal/100) * rep_time * sets * reps
          1: 0.50*2*3*10 = 30.0
          2: 0.40*3*4*8  = 38.4
          3: 0.60*2*3*12 = 43.2
          4: 0.30*4*3*10 = 36.0
          5: 0.80*1*5*6  = 24.0
          6: 0.45*2*3*15 = 40.5
          Total_Exercise_Cal = 212.1
        Timer 54:13 -> 55 min:
          Rest_Cal = 55 * 1.3 * 3.5 * 70 / 200 = 87.5875
        Total = 212.1 + 87.5875 = 299.6875 -> 300 kkal
        """
        exercises = [
            GymExerciseInput(rep_cal=50, rep_time_sec=2, sets=3, reps=10),
            GymExerciseInput(rep_cal=40, rep_time_sec=3, sets=4, reps=8),
            GymExerciseInput(rep_cal=60, rep_time_sec=2, sets=3, reps=12),
            GymExerciseInput(rep_cal=30, rep_time_sec=4, sets=3, reps=10),
            GymExerciseInput(rep_cal=80, rep_time_sec=1, sets=5, reps=6),
            GymExerciseInput(rep_cal=45, rep_time_sec=2, sets=3, reps=15),
        ]
        result = calculate_gym(exercises, timer_seconds=54 * 60 + 13, weight=70)

        self.assertEqual(result.timer_minutes, 55)
        self.assertAlmostEqual(result.exercise_calories, 212.1, places=4)
        self.assertAlmostEqual(result.rest_calories, 87.5875, places=4)
        self.assertAlmostEqual(result.total_calories_raw, 299.6875, places=4)
        self.assertEqual(result.total_calories, 300)  # butun kkal
        self.assertFalse(result.is_estimated)

    def test_weight_factor_scales_exercise_calories(self):
        # weight 140 -> koeffitsient 2 -> mashq kaloriyasi ikki barobar.
        ex = [GymExerciseInput(rep_cal=100, rep_time_sec=1, sets=1, reps=1)]
        result = calculate_gym(ex, timer_seconds=0, weight=140)
        self.assertAlmostEqual(result.exercise_calories, 2.0, places=6)
        self.assertEqual(result.rest_calories, 0.0)
        self.assertEqual(result.total_calories, 2)

    def test_missing_weight_fallback_marks_estimated(self):
        ex = [GymExerciseInput(rep_cal=50, rep_time_sec=2, sets=3, reps=10)]
        result = calculate_gym(ex, timer_seconds=600, weight=None)
        self.assertEqual(result.weight_kg, 70.0)
        self.assertTrue(result.is_estimated)


class HomeFormulaTests(SimpleTestCase):
    def test_home_with_rounds_hand_calculated(self):
        """HOME mashg'uloti (raundlar) — qo'lda hisoblangan.

        weight = 70 (koeffitsient 1), rounds = 4:
          Exercise_Cal = (rep_cal/100/rep_time) * (rounds * time_in_round)
          1: (50/100/2) * (4*30) = 0.25 * 120 = 30.0
          2: (40/100/4) * (4*20) = 0.10 * 80  = 8.0
          3: (60/100/3) * (4*45) = 0.20 * 180 = 36.0
          Total_Exercise_Cal = 74.0
        TimePerRound = 30+20+45 = 95 s (dam olishsiz):
          ActiveTime(min) = (4 * 95) / 60 = 6.33333
        Timer 20:00 -> 20 min:
          rest_minutes = 20 - 6.33333 = 13.666667
          Rest_Cal = 13.666667 * 1.3 * 3.5 * 70 / 200 = 21.764167
        Total = 74.0 + 21.764167 = 95.764167 -> 96 kkal
        """
        exercises = [
            HomeExerciseInput(rep_cal=50, rep_time_sec=2, time_in_round_sec=30),
            HomeExerciseInput(rep_cal=40, rep_time_sec=4, time_in_round_sec=20),
            HomeExerciseInput(rep_cal=60, rep_time_sec=3, time_in_round_sec=45),
        ]
        result = calculate_home(exercises, rounds=4, timer_seconds=20 * 60, weight=70)

        self.assertEqual(result.timer_minutes, 20)
        self.assertAlmostEqual(result.exercise_calories, 74.0, places=4)
        self.assertAlmostEqual(result.rest_calories, 21.764167, places=4)
        self.assertAlmostEqual(result.total_calories_raw, 95.764167, places=4)
        self.assertEqual(result.total_calories, 96)

    def test_home_rest_uses_seconds_to_minutes_conversion(self):
        """TimePerRound SEKUNDda — daqiqaga o'tkazilishini alohida tekshiramiz.

        rounds=2, time_in_round=60s (bitta mashq), TimePerRound=60s.
        ActiveTime = (2*60)/60 = 2.0 min. Agar sekundni daqiqaga o'tkazmasak,
        ActiveTime noto'g'ri (120 min) bo'lib, rest manfiy -> 0 bo'lib qolardi.
        Timer 10 min -> rest_minutes = 10 - 2 = 8 min.
          Rest_Cal = 8 * 1.3 * 3.5 * 70 / 200 = 12.74
        """
        exercises = [HomeExerciseInput(rep_cal=0, rep_time_sec=5, time_in_round_sec=60)]
        result = calculate_home(exercises, rounds=2, timer_seconds=10 * 60, weight=70)
        # rep_cal=0 -> mashq kaloriyasi 0, faqat rest qoladi.
        self.assertAlmostEqual(result.exercise_calories, 0.0, places=6)
        self.assertAlmostEqual(result.rest_calories, 12.74, places=4)

    def test_home_negative_rest_is_clamped_to_zero(self):
        """(WorkoutTimer - ActiveTime) manfiy bo'lsa Rest_Cal 0 ga qisiladi."""
        exercises = [HomeExerciseInput(rep_cal=50, rep_time_sec=2, time_in_round_sec=100)]
        # rounds=10, TimePerRound=100s -> ActiveTime = 1000/60 = 16.67 min.
        # Timer 5 min -> 5 - 16.67 < 0 -> clamp 0.
        result = calculate_home(exercises, rounds=10, timer_seconds=5 * 60, weight=70)
        self.assertEqual(result.rest_calories, 0.0)
        self.assertGreater(result.exercise_calories, 0.0)
        self.assertEqual(result.total_calories, round(result.exercise_calories))

    def test_home_zero_rep_time_is_skipped_and_warned(self):
        """Exercise1repTime = 0 -> nolga bo'linishni oldini olib, mashqni o'tkazamiz + log."""
        exercises = [
            HomeExerciseInput(rep_cal=50, rep_time_sec=0, time_in_round_sec=30),   # o'tkaziladi
            HomeExerciseInput(rep_cal=60, rep_time_sec=3, time_in_round_sec=45),   # hisoblanadi
        ]
        with self.assertLogs("apps.calorie", level="WARNING") as cm:
            result = calculate_home(exercises, rounds=4, timer_seconds=20 * 60, weight=70)
        self.assertEqual(result.skipped_exercises, 1)
        self.assertTrue(any("o'tkazib yuborildi" in m for m in cm.output))
        # Faqat 3-mashqning ekvivalenti: (60/100/3)*(4*45) = 0.2*180 = 36.0
        self.assertAlmostEqual(result.exercise_calories, 36.0, places=4)

    def test_home_missing_weight_fallback(self):
        exercises = [HomeExerciseInput(rep_cal=50, rep_time_sec=2, time_in_round_sec=30)]
        result = calculate_home(exercises, rounds=3, timer_seconds=600, weight=0)
        self.assertEqual(result.weight_kg, 70.0)
        self.assertTrue(result.is_estimated)

    def test_home_explicit_time_per_round_overrides_sum(self):
        # time_per_round_sec berilsa, mashqlar yig'indisi o'rniga o'sha ishlatiladi.
        exercises = [HomeExerciseInput(rep_cal=0, rep_time_sec=5, time_in_round_sec=30)]
        result = calculate_home(
            exercises, rounds=2, timer_seconds=10 * 60, weight=70, time_per_round_sec=60,
        )
        # ActiveTime = (2*60)/60 = 2 min -> rest 8 min -> 12.74 (yuqoridagi kabi).
        self.assertAlmostEqual(result.rest_calories, 12.74, places=4)


class GymAdapterMappingTests(TestCase):
    """Model -> formula maydon mosligini (DB bilan) tekshiradi:
    Exercise.calory -> rep_cal, Exercise.duration -> rep_time, WorkoutExercise.sets/reps.
    """

    def test_gym_adapter_reads_existing_exercise_fields(self):
        from apps.models.exercises import Exercise
        from apps.models.workouts import (
            Program, Plan, Week, Workout, WorkoutExercise, WorkoutType,
        )

        program = Program.objects.create(name="T", workout_type=WorkoutType.GYM)
        plan = Plan.objects.create(program=program, name="P")
        week = Week.objects.create(plan=plan, week_number=1)
        workout = Workout.objects.create(week=week, day_number=1, rounds=1)

        # Exercise1repCal=50 (calory), Exercise1repTime=2s (duration).
        ex1 = Exercise.objects.create(name="E1", calory=50, duration=2)
        ex2 = Exercise.objects.create(name="E2", calory=40, duration=3)
        WorkoutExercise.objects.create(workout=workout, exercise=ex1, sets=3, reps=10, order=1)
        WorkoutExercise.objects.create(workout=workout, exercise=ex2, sets=4, reps=8, order=2)

        profile = SimpleNamespace(weight=70)
        result = calories_for_gym_workout(workout, timer_seconds=10 * 60, profile=profile)

        # Kutilgan: (50/100)*2*3*10 + (40/100)*3*4*8 = 30 + 38.4 = 68.4 mashq kaloriyasi.
        self.assertAlmostEqual(result.exercise_calories, 68.4, places=4)
        # Adapter natijasi toza formula bilan bir xil bo'lishi kerak.
        expected = calculate_gym(
            [
                GymExerciseInput(rep_cal=50, rep_time_sec=2, sets=3, reps=10),
                GymExerciseInput(rep_cal=40, rep_time_sec=3, sets=4, reps=8),
            ],
            timer_seconds=10 * 60,
            weight=70,
        )
        self.assertEqual(result.total_calories, expected.total_calories)
