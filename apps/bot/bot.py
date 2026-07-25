import logging

import telebot

from root.settings import BOT_TOKEN

logger = logging.getLogger("apps.telegram_bot")

# BOT_TOKEN productionda MAJBURIY. Agar o'rnatilmagan bo'lsa — import paytida butun
# ilovani qulatib qo'ymaymiz (barcha so'rovlar bot moduliga bog'liq), balki aniq
# ogohlantirish yozamiz. Botga bog'liq amallar (webhook, xabar yuborish) o'z
# joyida xavfsiz ishlamay qoladi (bot_send_message try/except bilan himoyalangan).
if not BOT_TOKEN:
    logger.error(
        "TELEGRAM_BOT_TOKEN / BOT_TOKEN o'rnatilmagan — Telegram bot va mini-app "
        "autentifikatsiyasi ishlamaydi. Production env'da ushbu o'zgaruvchini o'rnating."
    )

bot = telebot.TeleBot(BOT_TOKEN or "", parse_mode="HTML")
