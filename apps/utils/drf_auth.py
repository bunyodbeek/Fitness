"""Telegram Mini App uchun DRF autentifikatsiya klasslari.

Ikki mexanizm birgalikda ishlaydi:

* ``CsrfExemptSessionAuthentication`` — Django sessiya cookie'si (asosiy, davomli).
  Telegram webview'i cross-origin bo'lgani uchun CSRF round-trip ishonchsiz, shuning
  uchun bu endpointlarda CSRF tekshiruvi o'tkazib yuboriladi (identifikatsiya
  imzolangan ``init_data`` / sessiya orqali isbotlanadi).
* ``TelegramTokenAuthentication`` — ``Authorization: Bearer <token>`` sarlavhasidagi
  sessiya tokeni (cookie tashlab yuborilgan holatlar uchun zaxira).
"""

from __future__ import annotations

from rest_framework.authentication import BaseAuthentication, SessionAuthentication

from apps.models import User
from apps.utils.session_token import read_session_token


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication without CSRF enforcement (Telegram webview uchun)."""

    def enforce_csrf(self, request):
        return  # intentionally skip CSRF for Telegram mini-app endpoints


class TelegramTokenAuthentication(BaseAuthentication):
    """`Authorization: Bearer <session-token>` orqali foydalanuvchini aniqlaydi."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        token = ""
        if header.startswith(self.keyword + " "):
            token = header[len(self.keyword) + 1:].strip()
        if not token:
            # Ba'zi klientlar Authorization sarlavhasini o'zgartirib yuboradi —
            # maxsus sarlavhani ham qabul qilamiz.
            token = request.META.get("HTTP_X_SESSION_TOKEN", "").strip()
        if not token:
            return None

        payload = read_session_token(token)
        if not payload:
            return None

        user = User.objects.filter(id=payload.get("uid")).first()
        if not user:
            return None
        return (user, None)
