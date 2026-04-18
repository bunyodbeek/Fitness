import logging

from root.settings import BOT_TOKEN
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


async def send_telegram_notification_async(telegram_id: int, message: str):
    if not telegram_id:
        logger.warning("Telegram ID not provided")
        return False

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        return False

    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"Notification sent to {telegram_id}")
        return True
    except TelegramError as e:
        logger.error(f"Failed to send telegram notification: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending notification: {str(e)}")
        return False


def send_telegram_notification_sync(telegram_id: int, message: str):
    """
    Sync - Celery tasks uchun (sync version)

    Args:
        telegram_id: Foydalanuvchi telegram ID
        message: Yuborilishi kerak bo'lgan xabar

    Returns:
        bool: Muvaffaqiyatli yuborilsa True, aks holda False
    """
    import asyncio

    try:
        # Async funksiyani sync contextda ishga tushirish
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            send_telegram_notification_async(telegram_id, message)
        )
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error in sync notification: {str(e)}")
        return False


# ============================================
# CELERY TASKS UCHUN MAIN FUNCTION
# ============================================
def send_notification(telegram_id: int, message: str):
    """
    Bu funksiya payments/tasks.py dan chaqiriladi

    Usage:
        from bot.notifications import send_notification
        send_notification(user.telegram_id, "Your message")
    """
    return send_telegram_notification_sync(telegram_id, message)


# ============================================
# TELEGRAM BOT HANDLERS UCHUN (optional)
# ============================================
async def notify_payment_success(telegram_id: int, amount: float, end_date: str):
    """To'lov muvaffaqiyatli"""
    message = (
        "✅ <b>To'lov muvaffaqiyatli!</b>\n\n"
        f"💰 Summa: <b>{amount:,.0f} UZS</b>\n"
        f"📅 Premium tugash sanasi: <b>{end_date}</b>\n\n"
        "Rahmat! 🎉"
    )
    return await send_telegram_notification_async(telegram_id, message)


async def notify_payment_failed(telegram_id: int, attempt: int):
    """To'lov muvaffaqiyatsiz"""
    if attempt < 3:
        message = (
            "⚠️ <b>To'lov amalga oshmadi!</b>\n\n"
            f"🔄 Urinish: {attempt}/3\n"
            f"⏰ Keyingi urinish: 24 soatdan keyin\n\n"
            "Kartangizda yetarli mablag' borligini tekshiring."
        )
    else:
        message = (
            "❌ <b>Obuna bekor qilindi!</b>\n\n"
            "3 marta to'lov amalga oshmadi.\n"
            "Premium funksiyalar yopildi.\n\n"
            "Qayta obuna bo'lish: /start"
        )
    return await send_telegram_notification_async(telegram_id, message)


async def notify_subscription_expiring(telegram_id: int, days_left: int, end_date: str, auto_renew: bool):
    """Obuna tugashi haqida eslatma"""
    if auto_renew:
        message = (
            f"🔔 <b>Eslatma</b>\n\n"
            f"Obuna tugashiga <b>{days_left} kun</b> qoldi.\n"
            f"📅 Tugash sanasi: {end_date}\n\n"
            "Avtomatik yangilanish yoqilgan ✅"
        )
    else:
        message = (
            f"🔔 <b>Eslatma</b>\n\n"
            f"Obuna tugashiga <b>{days_left} kun</b> qoldi.\n"
            f"📅 Tugash sanasi: {end_date}\n\n"
            "Obunani uzaytirish: /start"
        )
    return await send_telegram_notification_async(telegram_id, message)


async def notify_subscription_expired(telegram_id: int):
    """Obuna tugadi"""
    message = (
        "⏰ <b>Obuna muddati tugadi</b>\n\n"
        "Premium funksiyalar yopildi.\n\n"
        "Qayta obuna bo'lish: /start"
    )
    return await send_telegram_notification_async(telegram_id, message)


async def notify_card_expired(telegram_id: int, last_four: str):
    """Karta muddati tugagan"""
    message = (
        "⚠️ <b>Karta muddati tugagan!</b>\n\n"
        f"💳 Karta: ****{last_four}\n\n"
        "Iltimos, yangi karta qo'shing:\n"
        "/start"
    )
    return await send_telegram_notification_async(telegram_id, message)
