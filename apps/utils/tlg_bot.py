import logging

from apps.bot.bot import bot

logger = logging.getLogger("apps.telegram_bot")


def bot_send_message(_id: str | int, msg: str) -> bool:
    """Foydalanuvchiga bot orqali xabar yuboradi.

    Xabar yuborish HECH QACHON so'rovni buzmasligi kerak: agar Telegram vaqtincha
    ishlamasa, foydalanuvchi botni bloklagan bo'lsa yoki token noto'g'ri bo'lsa —
    xatoni log qilamiz va ``False`` qaytaramiz (masalan, ro'yxatdan o'tish
    muvaffaqiyatli tugagach xabar yuborilmasa ham 500 bermaydi).
    """
    try:
        bot.send_message(_id, msg)
        return True
    except Exception:
        logger.warning("bot_send_message muvaffaqiyatsiz (id=%s)", _id, exc_info=True)
        return False
