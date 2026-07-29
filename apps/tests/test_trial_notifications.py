"""Bepul sinov xabarlari: ro'yxatdan o'tish paytidagi xabar va 3/2/1 kunlik eslatmalar.

Eslatmalar cron orqali ketadi, shuning uchun asosiy xavf — takroriy yuborish
va noto'g'ri kunni ushlash. Testlar aynan shuni tekshiradi.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.models import Subscription, SubscriptionPlan, User, UserProfile
from apps.models.users import TRIAL_DAYS


def _sent_messages(mock):
    return [call.args[1] for call in mock.call_args_list]


class TrialReminderTests(TestCase):

    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            price_uzs=Decimal("100000"), price_usd=10,
            period=SubscriptionPlan.PeriodChoices.MONTHLY,
        )

    def _profile(self, *, days_left, name="U", telegram_id=None):
        """Sinovi ``days_left`` kundan keyin tugaydigan foydalanuvchi."""
        user = User.objects.create_user(username=f"u-{name}", password="x")
        profile = UserProfile.objects.create(
            user=user, name=name, telegram_id=telegram_id or abs(hash(name)) % 10 ** 9,
        )
        started = timezone.now() + timedelta(days=days_left) - timedelta(days=TRIAL_DAYS)
        UserProfile.objects.filter(pk=profile.pk).update(trial_started_at=started)
        profile.refresh_from_db()
        return profile

    def _run(self):
        with patch(
            "apps.management.commands.premium_notifications.send_notification",
            return_value=True,
        ) as mock:
            call_command("premium_notifications")
        return mock

    # ── to'g'ri kunni ushlash ──────────────────────────────────────────────
    def test_reminders_go_out_at_three_two_and_the_last_day(self):
        for days in (3, 2, 1):
            with self.subTest(days=days):
                UserProfile.objects.all().delete()
                self._profile(days_left=days, name=f"d{days}")
                mock = self._run()
                self.assertEqual(mock.call_count, 1)

    def test_no_reminder_on_other_days(self):
        for days in (7, 6, 5, 4):
            with self.subTest(days=days):
                UserProfile.objects.all().delete()
                self._profile(days_left=days, name=f"d{days}")
                self.assertEqual(self._run().call_count, 0)

    def test_last_day_message_differs_from_the_others(self):
        self._profile(days_left=1, name="last")
        body = _sent_messages(self._run())[0]
        self.assertIn("oxirgi kuni", body)

        UserProfile.objects.all().delete()
        self._profile(days_left=3, name="three")
        body = _sent_messages(self._run())[0]
        self.assertIn("3 kun", body)
        self.assertNotIn("oxirgi kuni", body)

    # ── til ────────────────────────────────────────────────────────────────
    def test_reminder_uses_the_language_saved_on_the_profile(self):
        expected = {
            "uz": "Bepul sinov muddatingiz",
            "ru": "Бесплатный период",
            "en": "Your free trial ends",
        }
        for code, needle in expected.items():
            with self.subTest(language=code):
                UserProfile.objects.all().delete()
                profile = self._profile(days_left=3, name=f"lang{code}")
                UserProfile.objects.filter(pk=profile.pk).update(language=code)

                body = _sent_messages(self._run())[0]

                self.assertIn(needle, body)

    def test_default_language_keeps_the_old_uzbek_behaviour(self):
        profile = self._profile(days_left=3, name="default")
        self.assertEqual(profile.language, "uz")
        self.assertIn("Bepul sinov", _sent_messages(self._run())[0])

    def test_message_carries_the_end_date(self):
        profile = self._profile(days_left=3, name="date")
        body = _sent_messages(self._run())[0]
        self.assertIn(profile.trial_ends_at.strftime("%d.%m.%Y"), body)

    # ── takrorlamaslik ─────────────────────────────────────────────────────
    def test_running_twice_in_a_day_sends_one_message(self):
        self._profile(days_left=3, name="twice")
        self.assertEqual(self._run().call_count, 1)
        self.assertEqual(self._run().call_count, 0)

    def test_each_stage_still_sends_once(self):
        """3 → 2 → 1: har bosqichda bittadan, jami uchta."""
        profile = self._profile(days_left=3, name="walk")
        total = self._run().call_count

        for days_left in (2, 1):
            started = timezone.now() + timedelta(days=days_left) - timedelta(days=TRIAL_DAYS)
            UserProfile.objects.filter(pk=profile.pk).update(trial_started_at=started)
            total += self._run().call_count

        self.assertEqual(total, 3)

    def test_a_blocked_user_is_not_retried_every_day(self):
        profile = self._profile(days_left=3, name="blocked")
        with patch(
            "apps.management.commands.premium_notifications.send_notification",
            return_value=False,
        ):
            call_command("premium_notifications")
        profile.refresh_from_db()
        self.assertEqual(profile.trial_reminder_sent_day, 3)
        self.assertEqual(self._run().call_count, 0)

    # ── kimga yubormaslik kerak ────────────────────────────────────────────
    def test_subscribers_get_no_trial_reminder(self):
        profile = self._profile(days_left=3, name="paid")
        Subscription.objects.create(user=profile, plan=self.plan)
        self.assertEqual(self._run().call_count, 0)

    def test_profile_without_a_telegram_id_is_skipped(self):
        profile = self._profile(days_left=3, name="notg")
        UserProfile.objects.filter(pk=profile.pk).update(telegram_id=None)
        self.assertEqual(self._run().call_count, 0)

    def test_expired_trial_gets_nothing(self):
        self._profile(days_left=-2, name="gone")
        self.assertEqual(self._run().call_count, 0)


class RegistrationMessageTests(TestCase):

    def _register(self, lang, telegram_id, mock_verify):
        mock_verify.return_value = ({
            "telegram_id": telegram_id, "first_name": "Aziz", "last_name": "",
            "username": "aziz", "photo_url": "",
        }, None)
        response = self.client.post(
            f"/{lang}/api/questionnaire/submit/",
            data={
                "init_data": "signed", "gender": "male", "experience": "beginner",
                "goal": "build_body", "days": 3, "weight": 70, "motivation": [],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return UserProfile.objects.get(telegram_id=telegram_id)

    @patch("apps.views.users.bot_send_message", return_value=True)
    @patch("apps.views.users.verify_init_data")
    def test_registration_message_announces_the_trial(self, mock_verify, mock_send):
        profile = self._register("uz", 555001, mock_verify)
        body = mock_send.call_args.args[1]

        self.assertIn(f"{TRIAL_DAYS} KUNLIK BEPUL SINOV", body)
        self.assertIn(profile.trial_ends_at.strftime("%d.%m.%Y"), body)
        self.assertIn("Premium obuna", body)
        # Bot HTML rejimida — Markdown yulduzchalari xabarda ko'rinib qolmasin.
        self.assertNotIn("**", body)

    @patch("apps.views.users.bot_send_message", return_value=True)
    @patch("apps.views.users.verify_init_data")
    def test_message_shows_no_internal_id_and_no_separators(self, mock_verify, mock_send):
        self._register("uz", 555004, mock_verify)
        body = mock_send.call_args.args[1]
        self.assertNotIn("ID", body)
        self.assertNotIn("━", body)

    @patch("apps.views.users.bot_send_message", return_value=True)
    @patch("apps.views.users.verify_init_data")
    def test_date_is_seven_days_out_even_for_an_older_user_row(self, mock_verify, mock_send):
        """Anketani tashlab ketib qaytgan odam ham to'liq 7 kun oladi.

        Ilgari anchor `User.date_joined` dan olinardi va bunday foydalanuvchi
        o'tib ketgan sanani ko'rardi (masalan bugun ro'yxatdan o'tib "24.06
        gacha" degan xabar)."""
        User.objects.create_user(username="telegram_555005", password="x")
        User.objects.filter(username="telegram_555005").update(
            date_joined=timezone.now() - timedelta(days=42),
        )

        profile = self._register("uz", 555005, mock_verify)
        body = mock_send.call_args.args[1]

        expected = (timezone.localtime() + timedelta(days=TRIAL_DAYS)).strftime("%d.%m.%Y")
        self.assertIn(expected, body)
        self.assertTrue(profile.is_in_trial)

    @patch("apps.views.users.bot_send_message", return_value=True)
    @patch("apps.views.users.verify_init_data")
    def test_registration_stores_the_language_and_uses_it(self, mock_verify, mock_send):
        """Anketa qaysi tilda to'ldirilgan bo'lsa, xabar ham o'sha tilda."""
        cases = {
            "ru": (555002, "БЕСПЛАТНЫЙ ПЕРИОД"),
            "en": (555003, "FREE TRIAL HAS STARTED"),
        }
        for lang, (telegram_id, needle) in cases.items():
            with self.subTest(language=lang):
                profile = self._register(lang, telegram_id, mock_verify)
                self.assertEqual(profile.language, lang)
                self.assertIn(needle, mock_send.call_args.args[1])
