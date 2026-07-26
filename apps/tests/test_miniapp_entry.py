"""`/app/` — til prefiksisiz Mini App kirish nuqtasi.

Chat ro'yxatidagi OPEN tugmasi va menu button shu manzilga ishora qiladi, shuning
uchun u tilni har ochilishda qayta aniqlashi shart: ilovadagi tanlov botdagi
`?lang=` dan ustun bo'lishi kerak — aks holda til almashtirish "yopishmaydi".
"""

from django.conf import settings
from django.test import TestCase


class MiniAppEntryTests(TestCase):
    URL = "/app/"

    def test_default_language_when_nothing_stored(self):
        resp = self.client.get(self.URL)

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], f"/{settings.LANGUAGE_CODE}/miniapp/questionnaire/")

    def test_bot_lang_param_used_and_persisted(self):
        resp = self.client.get(self.URL, {"lang": "ru"})

        self.assertEqual(resp["Location"], "/ru/miniapp/questionnaire/")
        self.assertEqual(resp.cookies[settings.LANGUAGE_COOKIE_NAME].value, "ru")

    def test_stored_preference_beats_bot_lang_param(self):
        # Ilovada tanlangan til (cookie) — botdagi eski `?lang=` uni bekor qilmasin.
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz"

        resp = self.client.get(self.URL, {"lang": "ru"})

        self.assertEqual(resp["Location"], "/uz/miniapp/questionnaire/")
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, resp.cookies)

    def test_other_query_params_are_forwarded(self):
        resp = self.client.get(self.URL, {"lang": "en", "edit": "1"})

        self.assertEqual(resp["Location"], "/en/miniapp/questionnaire/?edit=1")

    def test_unsupported_lang_falls_back(self):
        resp = self.client.get(self.URL, {"lang": "zz"})

        self.assertEqual(resp["Location"], f"/{settings.LANGUAGE_CODE}/miniapp/questionnaire/")
