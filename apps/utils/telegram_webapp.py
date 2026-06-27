"""Telegram Mini App `initData` ni tekshirish va undan foydalanuvchini ajratish.

Frontend ba'zi holatlarda `initDataUnsafe.user.id` ni bera olmaydi (launch konteksti,
timing, qayta ochilish). Imzolangan `initData` esa ishonchli manba — uni bot token bilan
tekshirib, foydalanuvchini server tomonda ajratamiz.

Hujjat: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from django.conf import settings


def _check_signature(init_data: str, bot_token: str) -> bool:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return False

    data_check_string = "\n".join(
        f"{key}={pairs[key]}" for key in sorted(pairs.keys())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed_hash, received_hash)


def parse_init_data(init_data: str, *, max_age_seconds: int = 86400) -> dict | None:
    """Imzoni tekshirib, foydalanuvchi ma'lumotlarini qaytaradi.

    Yaroqsiz imzo / token yo'q / eskirgan bo'lsa — None.
    Qaytadi: {'telegram_id', 'first_name', 'last_name', 'username', 'photo_url'} yoki None.
    """
    if not init_data:
        return None

    bot_token = getattr(settings, "BOT_TOKEN", None) or getattr(
        settings, "TELEGRAM_BOT_TOKEN", None
    )
    if not bot_token:
        return None

    if not _check_signature(init_data, bot_token):
        return None

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))

    # auth_date eskirib qolmaganini tekshiramiz (replay'dan himoya).
    auth_date = pairs.get("auth_date")
    if auth_date and max_age_seconds > 0:
        try:
            if (time.time() - int(auth_date)) > max_age_seconds:
                return None
        except (TypeError, ValueError):
            return None

    user_raw = pairs.get("user")
    if not user_raw:
        return None

    try:
        user = json.loads(user_raw)
    except (TypeError, ValueError):
        return None

    telegram_id = user.get("id")
    if not telegram_id:
        return None

    return {
        "telegram_id": telegram_id,
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "username": user.get("username", ""),
        "photo_url": user.get("photo_url", ""),
    }