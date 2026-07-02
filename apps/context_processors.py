from apps.utils.telegram_bot_link import get_bot_deeplink


def telegram_bot_url(request):
    """Telegram bot deep-link (t.me) ni barcha shablonlarga uzatadi.

    Telegram konteksti bo'lmagan (brauzer) userlarni bot'ga yo'naltirish uchun
    ishlatiladi — masalan animation/questionnaire sahifalarida.
    """
    return {"telegram_bot_url": get_bot_deeplink()}
