"""Til almashtirish Telegram webview'idan CSRF token'siz ham ishlashini tekshiradi.

Mini-app webview'ida `SameSite=None` CSRF cookie'si tashlab yuboriladi (ayniqsa
menu button orqali ochilgan yangi webview sessiyasida) — exemptsiz bu POST 403
"CSRF verification failed" sahifasini qaytarardi va til umuman o'zgarmasdi.
"""

from django.test import Client, TestCase
from django.urls import reverse

from apps.models.users import User, UserProfile


class ChangeLanguageCsrfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="lang_user")
        # telegram_id YO'Q — botga xabar yuborilmaydi (testda tashqi API chaqirilmasin).
        UserProfile.objects.create(user=self.user, weight=70)

    def test_change_language_post_without_csrf_token_is_not_403(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        resp = client.post(reverse("change_language"), {"language": "ru"})

        self.assertNotEqual(resp.status_code, 403)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/ru/", resp["Location"])
        self.assertEqual(client.session.get("django_language"), "ru")
