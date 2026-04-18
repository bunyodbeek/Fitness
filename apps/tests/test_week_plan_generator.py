import unittest

from apps.services.week_plan_generator import generate_week_plan, generate_weeks, roundup_to_2_5


class DummyProfile:
    sets_increment = 1
    reps_increment = 2
    weight_mult_main = 1.05
    weight_threshold = 40
    weight_mult_alt = 1.1


class WeekPlanGeneratorTests(unittest.TestCase):
    def test_roundup_to_2_5(self):
        self.assertEqual(roundup_to_2_5(20.01), 22.5)
        self.assertEqual(roundup_to_2_5(22.5), 22.5)

    def test_generate_week_plan_count_and_progression(self):
        plans = generate_week_plan(3, 8, 20, DummyProfile(), weeks_count=6)
        self.assertEqual(len(plans), 6)
        self.assertEqual(plans[0]['sets'], 3)
        self.assertEqual(plans[0]['reps'], 8)
        self.assertEqual(plans[0]['weight'], 20)

        self.assertGreaterEqual(plans[1]['sets'], plans[0]['sets'])
        self.assertGreaterEqual(plans[1]['reps'], 6)
        self.assertGreater(plans[1]['weight'], plans[0]['weight'])

    def test_generate_week_plan_respects_custom_week_count(self):
        plans = generate_week_plan(4, 10, 30, DummyProfile(), weeks_count=3)
        self.assertEqual([p['week_number'] for p in plans], [1, 2, 3])

    def test_generate_weeks_uses_template_rules(self):
        class Template:
            w2_weight_multiplier = 1.05
            w3_weight_multiplier = 1.1
            w4_weight_multiplier = 1.15
            w5_weight_multiplier = 1.2
            deload_weight_multiplier = 0.9
            set_increment_w2 = 1
            set_increment_w3 = 1
            set_increment_w4 = 0
            set_increment_w5 = 0
            set_increment_w6 = -1
            rep_increment_w2 = 0
            rep_increment_w3 = 1
            rep_increment_w4 = 1
            rep_increment_w5 = 0
            rep_increment_w6 = -2

        weeks = generate_weeks(3, 8, 40, Template())
        self.assertEqual(len(weeks), 6)
        self.assertEqual(weeks[0], {'week_number': 1, 'sets': 3, 'reps': 8, 'weight': 40.0})
        self.assertEqual(weeks[1]['sets'], 4)
        self.assertEqual(weeks[5]['reps'], 6)
        self.assertEqual(weeks[5]['weight'], 37.5)


if __name__ == '__main__':
    unittest.main()
