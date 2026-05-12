import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from telebot.types import (
	InlineKeyboardButton,
	InlineKeyboardMarkup,
	ReplyKeyboardMarkup,
	Update,
	WebAppInfo,

)

from apps.bot.bot import bot
from root.settings import ADMIN_ID, WEBAPP_URL

# Logging
logging.basicConfig(
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	level=logging.INFO
)
logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("uz", "ru", "en")
LANGUAGE_TEXTS = {
	"uz": {
		"choose_language": "🌐 Tilni tanlang:",
		"welcome": (
			"💪 Xush kelibsiz, {first_name}!\n\n"
			"Tanangizni o'zgartirishga tayyormisiz?\n\n"
			"Quyidagi tugma orqali shaxsiy mashg'ulot rejangizni yarating! 🚀"
		),
		"start_button": "🏋️ Fitness'ni boshlash",
	},
	"ru": {
		"choose_language": "🌐 Выберите язык:",
		"welcome": (
			"💪 Добро пожаловать, {first_name}!\n\n"
			"Готовы трансформировать своё тело?\n\n"
			"Нажмите кнопку ниже, чтобы создать персональный план тренировок! 🚀"
		),
		"start_button": "🏋️ Начать Fitness",
	},
	"en": {
		"choose_language": "🌐 Choose your language:",
		"welcome": (
			"💪 Welcome, {first_name}!\n\n"
			"Ready to transform your body?\n\n"
			"Tap the button below to create your personalized workout plan! 🚀"
		),
		"start_button": "🏋️ Start Fitness",
	},
}


def _language_keyboard():
	keyboard = InlineKeyboardMarkup(row_width=1)
	keyboard.add(
		InlineKeyboardButton("🇺🇿 O‘zbekcha", callback_data="lang:uz"),
		InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
		InlineKeyboardButton("🇺🇸 English", callback_data="lang:en"),
	)
	return keyboard


def _send_webapp_message(chat_id, first_name, lang_code):
	lang_code = lang_code if lang_code in SUPPORTED_LANGUAGES else "en"
	texts = LANGUAGE_TEXTS[lang_code]
	
	webapp_link = f"{WEBAPP_URL}/{lang_code}/miniapp/questionnaire/"
	webapp_info = WebAppInfo(url=webapp_link)
	persistent_keyboard = ReplyKeyboardMarkup(
		resize_keyboard=True,
		is_persistent=True  
	)
	keyboard = InlineKeyboardMarkup()
	keyboard.add(InlineKeyboardButton(texts["start_button"], web_app=webapp_info))
	
	bot.send_message(
		chat_id,
		texts["welcome"].format(first_name=first_name or "User"),
		reply_markup=keyboard,
	)


@bot.message_handler(commands=['start'])
def start(message):
	user = message.from_user
	bot.send_message(
		message.chat.id,
		LANGUAGE_TEXTS["en"]["choose_language"],
		reply_markup=_language_keyboard(),
	)


@bot.callback_query_handler(func=lambda call: call.data.startswith("lang:"))
def handle_language_selection(call):
	user = call.from_user
	lang_code = call.data.split(":", 1)[1].strip().lower()
	if lang_code not in SUPPORTED_LANGUAGES:
		lang_code = "en"
	
	bot.answer_callback_query(call.id)
	try:
		bot.edit_message_reply_markup(
			chat_id=call.message.chat.id,
			message_id=call.message.message_id,
			reply_markup=None,
		)
	except Exception:
		pass
	
	_send_webapp_message(
		chat_id=call.message.chat.id,
		first_name=user.first_name,
		lang_code=lang_code,
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


import json


class TelegramWebhookView(APIView):
	permission_classes = [AllowAny]
	
	def post(self, request, *args, **kwargs):
		try:
			# request.data o'rniga request.body ishlatamiz
			data = json.loads(request.body.decode('utf-8'))
			update = Update.de_json(data)
			bot.process_new_updates([update])
		except Exception as e:
			logger.error(f"Webhook error: {e}")
		return Response({"status": "ok"})
