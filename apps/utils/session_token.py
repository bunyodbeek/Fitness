"""Telegram Mini App sessiya tokeni.

Django sessiyasi (cookie) — serverda render bo'ladigan sahifalar uchun asosiy,
ishonchli sessiya mexanizmi: u brauzer tomonidan har bir keyingi so'rovga
avtomatik biriktiriladi va to'liq sahifa navigatsiyasidan omon qoladi.

Biroq Telegram webview'i cross-origin (`web.telegram.org`) ichida ishlaydi va
`SameSite=None` cookie'lar ba'zi klientlarda tashlab yuboriladi. Shu sabab AJAX
so'rovlar uchun qo'shimcha, holatsiz (stateless) token ham beramiz: frontend uni
xotirada saqlab, har bir so'rovda `Authorization: Bearer <token>` sifatida yuboradi.

Token Django `signing` (HMAC) bilan imzolanadi — qo'shimcha kutubxona shart emas.
"""

from __future__ import annotations

from django.core import signing

_SALT = "telegram-miniapp-session"
# Token amal qilish muddati (Telegram sessiyasi uzoq bo'lgani ma'qul).
DEFAULT_MAX_AGE = 60 * 60 * 24 * 30  # 30 kun


def make_session_token(user_id: int, telegram_id) -> str:
    """Foydalanuvchi uchun imzolangan sessiya tokeni yaratadi."""
    return signing.dumps({"uid": user_id, "tid": telegram_id}, salt=_SALT)


def read_session_token(token: str, *, max_age: int = DEFAULT_MAX_AGE):
    """Tokenni tekshiradi; yaroqli bo'lsa payload dict, aks holda None qaytaradi."""
    if not token:
        return None
    try:
        return signing.loads(token, salt=_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
