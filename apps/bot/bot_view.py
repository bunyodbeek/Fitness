import logging

from apps.bot.bot import bot
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from root.settings import ADMIN_ID, WEBAPP_URL
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user

    webapp_link = WEBAPP_URL + "/miniapp/questionnaire/"
    webapp_info = WebAppInfo(url=webapp_link)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("🏋️ Start Fitness Inline", web_app=webapp_info)
    )

    bot.send_message(
        message.chat.id,
        f"💪 Welcome {user.first_name}!\n\n"
        "Ready to transform your body?\n\n"
        "Tap the button below to create your personalized workout plan! 🚀",
        reply_markup=keyboard
    )


@bot.message_handler(commands=['admin'])
def admin_panel(message):
    keyboard = InlineKeyboardMarkup()
    if int(message.from_user.id) == int(ADMIN_ID):
        keyboard.add(
            InlineKeyboardButton(text="Admin Panelga o'tish!", url=f"{WEBAPP_URL}/admin/"))
        bot.send_message(chat_id=message.chat.id, text="Admin panelga xush kelibsiz!", reply_markup=keyboard)
    else:
        bot.send_message(chat_id=message.chat.id, text="⚠️ Bu bo'lim faqat adminlar uchun!")


@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.send_message(
        message.chat.id,
        "🏋️ Fitness Bot Commands:\n\n"
        "/start - Begin your fitness journey\n"
        "/help - Show help menu"
    )


class TelegramWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        update = Update.de_json(request.data)
        bot.process_new_updates([update])
        return Response({"status": "ok"})
