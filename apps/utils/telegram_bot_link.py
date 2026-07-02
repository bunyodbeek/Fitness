"""Telegram bot deep-link (t.me) ni aniqlash.

Brauzerdan (masalan, shredzville.com) kirgan, Telegram konteksti bo'lmagan userda
telegram_id yo'q — mini app questionnaire sahifasi unga foydasiz. Shuning uchun
profilsiz/anonim userni bot'ning o'ziga yo'naltiramiz; u yerdan mini app ochilib
telegram_id olinadi.

Tartib:
  1. settings.TELEGRAM_BOT_URL / TELEGRAM_BOT_USERNAME (env orqali sozlangan bo'lsa)
  2. bot.get_me() — token'dan username olib t.me linkini quramiz (natija keshlanadi)
  3. so'nggi chora — settings.TELEGRAM_BOT_REDIRECT_URL
"""

from __future__ import annotations

from django.conf import settings

_cached_link: str | None = None


def _from_settings() -> str:
    url = (getattr(settings, "TELEGRAM_BOT_URL", "") or "").strip()
    if url:
        return url
    username = (getattr(settings, "TELEGRAM_BOT_USERNAME", "") or "").strip().lstrip("@")
    if username:
        return f"https://t.me/{username}"
    return ""


def _from_get_me() -> str:
    try:
        from apps.bot.bot import bot

        me = bot.get_me()
        username = (getattr(me, "username", "") or "").lstrip("@")
        if username:
            return f"https://t.me/{username}"
    except Exception:
        pass
    return ""


def get_bot_deeplink() -> str:
    """Bot'ning t.me linkini qaytaradi (natijani keshlaydi)."""
    global _cached_link
    if _cached_link:
        return _cached_link

    link = _from_settings() or _from_get_me()
    if not link:
        # So'nggi chora — sozlamadagi qiymat (questionnaire bo'lishi mumkin).
        link = getattr(settings, "TELEGRAM_BOT_REDIRECT_URL", "") or ""

    # get_me() muvaffaqiyatsiz bo'lib, questionnaire'ga tushib qolsak keshlamaymiz,
    # keyingi so'rovda qayta urinib ko'rish uchun.
    if link and "miniapp/questionnaire" not in link:
        _cached_link = link
    return link