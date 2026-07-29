"""Til tanlovi profilda saqlanishi (apps/utils/user_language.py).

Bot xabarlari cron va webhook'dan ketadi — u yerda sessiya ham, cookie ham
yo'q. Shuning uchun til tanlanadigan HAR BIR joy uni profilga yozishi shart,
aks holda foydalanuvchi ilovada rus tilini tanlab, botdan o'zbekcha xabar
olaveradi.
"""

from unittest.mock import patch

from django.test import TestCase
from django.utils import translation

from apps.models import User, UserProfile
from apps.utils.user_language import (
	language_of, normalize, remember_language, user_locale,
)


class NormalizeTests(TestCase):

	def test_accepts_supported_codes(self):
		for code in ("uz", "ru", "en"):
			self.assertEqual(normalize(code), code)

	def test_trims_regional_suffixes(self):
		# Telegram `language_code` va brauzer `Accept-Language` shunday keladi.
		self.assertEqual(normalize("en-US"), "en")
		self.assertEqual(normalize("RU"), "ru")

	def test_rejects_unknown_and_empty(self):
		for code in ("de", "", None, "xx"):
			self.assertIsNone(normalize(code))


class RememberLanguageTests(TestCase):

	def setUp(self):
		self.user = User.objects.create_user(username="u", password="x")
		self.profile = UserProfile.objects.create(user=self.user, name="U")

	def test_saves_a_new_choice(self):
		self.assertTrue(remember_language(self.profile, "ru"))
		self.profile.refresh_from_db()
		self.assertEqual(self.profile.language, "ru")

	def test_ignores_an_unchanged_choice(self):
		self.assertFalse(remember_language(self.profile, self.profile.language))

	def test_never_raises_on_bad_input(self):
		"""Til almashtirish foydalanuvchi kutayotgan amal — u yiqilmasligi kerak."""
		self.assertFalse(remember_language(None, "ru"))
		self.assertFalse(remember_language(self.profile, "de"))
		self.assertFalse(remember_language(self.profile, None))

	def test_locale_context_uses_the_profile_language(self):
		remember_language(self.profile, "ru")
		with user_locale(self.profile):
			self.assertEqual(translation.get_language(), "ru")

	def test_locale_falls_back_when_language_is_missing(self):
		self.assertEqual(language_of(None), "uz")


class LanguageIsPersistedFromEverywhereTests(TestCase):

	def setUp(self):
		self.user = User.objects.create_user(username="picker", password="x")
		self.profile = UserProfile.objects.create(
			user=self.user, name="Picker", telegram_id=987654,
		)
		self.client.force_login(self.user)

	def test_app_language_api_persists_the_choice(self):
		response = self.client.post(
			"/uz/api/language/select/",
			data={"language": "ru"}, content_type="application/json",
		)
		self.assertEqual(response.status_code, 200)
		self.profile.refresh_from_db()
		self.assertEqual(self.profile.language, "ru")

	def test_settings_language_switch_persists_the_choice(self):
		response = self.client.post("/uz/change/language/", {"language": "en"})
		self.assertEqual(response.status_code, 302)
		self.profile.refresh_from_db()
		self.assertEqual(self.profile.language, "en")

	def test_invalid_code_leaves_the_profile_alone(self):
		before = self.profile.language
		self.client.post(
			"/uz/api/language/select/",
			data={"language": "de"}, content_type="application/json",
		)
		self.profile.refresh_from_db()
		self.assertEqual(self.profile.language, before)

	def test_bot_language_button_persists_the_choice(self):
		from apps.bot import bot_view

		call = type("Call", (), {
			"id": "1",
			"data": "lang:ru",
			"from_user": type("U", (), {"id": 987654, "first_name": "Picker"})(),
			"message": type("M", (), {
				"chat": type("C", (), {"id": 987654})(),
				"message_id": 1,
			})(),
		})()

		with patch.object(bot_view, "bot"), \
		     patch.object(bot_view, "_send_motivation_message"):
			bot_view.handle_language_selection(call)

		self.profile.refresh_from_db()
		self.assertEqual(self.profile.language, "ru")

	def test_bot_language_button_survives_a_missing_profile(self):
		"""Til odatda ro'yxatdan o'tishdan OLDIN tanlanadi — profil hali yo'q."""
		from apps.bot import bot_view

		call = type("Call", (), {
			"id": "1",
			"data": "lang:ru",
			"from_user": type("U", (), {"id": 111222333, "first_name": "Ghost"})(),
			"message": type("M", (), {
				"chat": type("C", (), {"id": 111222333})(),
				"message_id": 1,
			})(),
		})()

		with patch.object(bot_view, "bot"), \
		     patch.object(bot_view, "_send_motivation_message") as motivation:
			bot_view.handle_language_selection(call)

		motivation.assert_called_once()
