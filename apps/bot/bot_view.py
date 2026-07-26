import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from telebot.types import (
	InlineKeyboardButton,
	InlineKeyboardMarkup,
	KeyboardButton,
	MenuButtonWebApp,
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


# Menu button matni (xabar maydoni yonidagi tugma). Brend nomi — ataylab
# tarjima qilinmaydi, shunda til almashganda tugmani yangilash shart emas.
MENU_BUTTON_TEXT = "Fitness"

LANGUAGE_SAVED_TEXTS = {
	"uz": "✅ Til o'zgartirildi.",
	"ru": "✅ Язык изменён.",
	"en": "✅ Language updated.",
}


def _normalize_lang(lang_code):
	lang_code = (lang_code or "")[:2].lower()
	return lang_code if lang_code in SUPPORTED_LANGUAGES else "en"


def miniapp_url(lang_code=None):
	"""Mini App kirish manzili — HAR DOIM til prefiksisiz `/app/`.

	`/app/` (`apps.views.miniapp.MiniAppEntryView`) tilni har ochilishda qayta
	aniqlaydi: ilovada saqlangan tanlov → `?lang=` (botdagi tanlov) → klient tili.
	Shu sababli tugmalar ichidagi URL hech qachon eskirmaydi — foydalanuvchi ilovada
	tilni almashtirsa, eski xabardagi tugma ham yangi tilni ochadi.

	MUHIM: Mini App'ni faqat `web_app=` (WebAppInfo) tugmalari orqali ochamiz —
	oddiy `url=` tugmalari initData'ni uzatmaydi va "Telegram ID topilmadi"
	xatosiga olib keladi. Mini App havolalarini hech qachon url= ga o'zgartirmang.
	"""
	base = f"{WEBAPP_URL}/app/"
	return f"{base}?lang={lang_code}" if lang_code else base


def _webapp_keyboard(lang_code):
	"""Xabar bilan birga keladigan, pastda doim turuvchi reply keyboard.

	Xabar ostidagi inline web_app tugmasi ATAYLAB yo'q: u reply keyboard bilan
	takrorlanadi va ba'zi klientlarda barqaror ishlamaydi (bosilganda ochilmaydi).
	"""
	texts = LANGUAGE_TEXTS[lang_code]
	keyboard = ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)
	keyboard.add(
		KeyboardButton(
			text=texts["start_button"],
			web_app=WebAppInfo(url=miniapp_url(lang_code)),
		)
	)
	return keyboard


def _set_menu_button(chat_id, lang_code):
	"""Xabar maydoni chap tomonidagi menu button'ni Mini App tugmasiga aylantiradi.

	Bu — PravaOL'dagi "PravaOL" tugmasining ayni o'zi (MenuButtonWebApp). Chat
	bo'yicha o'rnatiladi va BotFather'dagi global qiymatdan ustun turadi; URL esa
	til prefiksisiz `/app/` bo'lgani uchun til almashganda ham to'g'ri ishlaydi
	(ilgari bu tugma qat'iy til prefiksi bilan sozlangani uchun muammo tug'dirardi).
	"""
	try:
		bot.set_chat_menu_button(
			chat_id=chat_id,
			menu_button=MenuButtonWebApp(
				type="web_app",  # telebot buni pozitsion argument sifatida talab qiladi
				text=MENU_BUTTON_TEXT,
				web_app=WebAppInfo(url=miniapp_url(lang_code)),
			),
		)
	except Exception:
		logger.warning("set_chat_menu_button ishlamadi (chat_id=%s)", chat_id, exc_info=True)


def _send_webapp_message(chat_id, first_name, lang_code):
	lang_code = _normalize_lang(lang_code)
	texts = LANGUAGE_TEXTS[lang_code]

	_set_menu_button(chat_id, lang_code)

	# Reply keyboard xuddi shu xabar bilan birga keladi — "Tanangizni o'zgartirishga
	# tayyormisiz?" xabari ko'rinishi bilanoq tugma pastda paydo bo'ladi (avvalgi
	# "." bo'sh xabar kerak emas).
	bot.send_message(
		chat_id,
		texts["welcome"].format(first_name=first_name or "User"),
		reply_markup=_webapp_keyboard(lang_code),
	)


def send_language_updated(chat_id, lang_code):
	"""Ilova ichida til o'zgartirilgach — reply keyboard'ni yangi tilda qayta yuborish.

	Reply keyboard'ni xabar yubormasdan yangilashning imkoni yo'q, shuning uchun
	qisqa tasdiq xabari bilan yuboramiz. Aks holda tugma matni va uning ichidagi
	mini app URL'i eski tilda qolib ketadi va foydalanuvchi tilni o'zgartirgandan
	keyin ham eski tildagi ilovaga qaytadi. Hech qachon exception ko'tarmaydi.
	"""
	lang_code = _normalize_lang(lang_code)
	try:
		_set_menu_button(chat_id, lang_code)
		bot.send_message(
			chat_id,
			LANGUAGE_SAVED_TEXTS[lang_code],
			reply_markup=_webapp_keyboard(lang_code),
		)
		return True
	except Exception:
		logger.warning("send_language_updated ishlamadi (chat_id=%s)", chat_id, exc_info=True)
		return False


GIFT_CLAIM_TEXTS = {
	"uz": {
		"msg": "🎁 Sizga Premium sovg'a qilindi!\nUni olish uchun quyidagi tugmani bosing.",
		"button": "🎁 Sovg'ani olish",
	},
	"ru": {
		"msg": "🎁 Вам подарили Premium!\nНажмите кнопку ниже, чтобы получить его.",
		"button": "🎁 Получить подарок",
	},
	"en": {
		"msg": "🎁 You've received a Premium gift!\nTap the button below to claim it.",
		"button": "🎁 Claim your gift",
	},
}


def _send_gift_claim(message, code):
	"""Open the mini-app claim page for a `/start gift_<code>` deep link."""
	user = message.from_user
	lang = (getattr(user, "language_code", "") or "en")[:2]
	if lang not in SUPPORTED_LANGUAGES:
		lang = "en"
	texts = GIFT_CLAIM_TEXTS[lang]

	claim_url = f"{WEBAPP_URL}/{lang}/users/gift/claim/{code}/"
	keyboard = InlineKeyboardMarkup()
	keyboard.add(
		InlineKeyboardButton(texts["button"], web_app=WebAppInfo(url=claim_url))
	)
	bot.send_message(message.chat.id, texts["msg"], reply_markup=keyboard)


@bot.message_handler(commands=['start'])
def start(message):
	user = message.from_user

	# Menu button'ni (xabar maydoni yonidagi tugma) darhol o'rnatamiz/yangilaymiz —
	# BotFather'dagi eski, til prefiksi qotib qolgan URL o'rniga `/app/`.
	_set_menu_button(message.chat.id, _normalize_lang(getattr(user, "language_code", "")))

	# Deep link: `/start gift_<code>` → open the gift claim page directly.
	parts = (message.text or "").split(maxsplit=1)
	param = parts[1].strip() if len(parts) > 1 else ""
	if param.startswith("gift_"):
		code = param[len("gift_"):].strip()
		if code:
			_send_gift_claim(message, code)
			return

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
			InlineKeyboardButton(text="Admin Panelga o'tish!", url=f"{WEBAPP_URL}/manage/"))
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
