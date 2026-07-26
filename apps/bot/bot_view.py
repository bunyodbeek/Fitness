import html
import logging
import os

from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from telebot.types import (
	InlineKeyboardButton,
	InlineKeyboardMarkup,
	MenuButtonWebApp,
	ReplyKeyboardRemove,
	Update,
	WebAppInfo,

)

from apps.bot.bot import bot
from root.settings import ADMIN_ID, BOT_INTRO_VIDEO, MEDIA_ROOT, WEBAPP_URL

# Logging
logging.basicConfig(
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	level=logging.INFO
)
logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("uz", "ru", "en")
LANGUAGE_TEXTS = {
	"uz": {
		# Til tanlangandan keyingi motivatsion xabar.
		"welcome": (
			"🔥 <b>{first_name}</b>, yo'lingiz aynan shu yerdan boshlanadi!\n\n"
			"Har bir mashg'ulot — bu o'zingizga bergan va'da. Bahona qidirmang — "
			"natija yarating.\n\n"
			"💪 Bugungi kuchli qaroringiz — ertangi kuchli tanangiz.\n\n"
			"Quyidagi tugmani bosing va shaxsiy mashg'ulot rejangizni yarating! 🚀"
		),
		"start_button": "🏋️ Fitness'ni boshlash",
	},
	"ru": {
		"welcome": (
			"🔥 <b>{first_name}</b>, ваш путь начинается прямо сейчас!\n\n"
			"Каждая тренировка — это обещание самому себе. Не ищите оправданий — "
			"создавайте результат.\n\n"
			"💪 Сильное решение сегодня — сильное тело завтра.\n\n"
			"Нажмите кнопку ниже и составьте свой персональный план тренировок! 🚀"
		),
		"start_button": "🏋️ Начать Fitness",
	},
	"en": {
		"welcome": (
			"🔥 <b>{first_name}</b>, your journey starts right now!\n\n"
			"Every workout is a promise you keep to yourself. No excuses — "
			"just results.\n\n"
			"💪 A strong decision today builds a strong body tomorrow.\n\n"
			"Tap the button below and build your personal workout plan! 🚀"
		),
		"start_button": "🏋️ Start Fitness",
	},
}

# Intro videoning izohi (caption). `/start` paytida foydalanuvchining tili hali
# noma'lum, shuning uchun uchala tilda ham yozamiz.
INTRO_CAPTION = (
	"🏋️ <b>Shredzville</b> — shaxsiy fitness murabbiyingiz.\n\n"
	"🇺🇿 Tilni tanlang\n"
	"🇷🇺 Выберите язык\n"
	"🇺🇸 Choose your language"
)


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
	"""Motivatsion xabar ostidagi inline "Mini App'ni ochish" tugmasi.

	Ilgari bu yerda pastda doim turuvchi `ReplyKeyboardMarkup` bor edi. U olib
	tashlandi: klaviatura maydonini egallab turardi, xabar yozishga xalaqit berardi
	va uni yangilashning yagona yo'li chatga qo'shimcha xabar yuborish edi (til
	almashganda bot "spam" qilardi). Inline `web_app` tugmasi ham initData'ni
	xuddi shunday uzatadi.
	"""
	texts = LANGUAGE_TEXTS[lang_code]
	keyboard = InlineKeyboardMarkup()
	keyboard.add(
		InlineKeyboardButton(
			text=texts["start_button"],
			web_app=WebAppInfo(url=miniapp_url(lang_code)),
		)
	)
	return keyboard


def _drop_reply_keyboard(chat_id):
	"""Eski, "yopishib qolgan" reply keyboard'ni chatdan olib tashlaydi.

	`ReplyKeyboardRemove`ni faqat xabar bilan birga yuborish mumkin, shuning uchun
	bir martalik xabar yuborib, darhol o'chiramiz — klaviatura o'chirilgani xabar
	o'chirilgandan keyin ham saqlanib qoladi. Avval reply tugmasini ko'rgan
	foydalanuvchilar uchun kerak; yangi foydalanuvchilarga zarari yo'q.
	"""
	try:
		msg = bot.send_message(
			chat_id, "⌛", reply_markup=ReplyKeyboardRemove(), disable_notification=True
		)
		bot.delete_message(chat_id, msg.message_id)
	except Exception:
		logger.debug("Reply keyboard'ni olib tashlab bo'lmadi (chat_id=%s)", chat_id, exc_info=True)


# Yuklangan intro video `file_id`si keshda saqlanadi — aks holda har bir `/start`da
# video qaytadan yuklanib, javob bir necha soniyaga cho'ziladi.
INTRO_VIDEO_CACHE_KEY = "bot:intro_video_file_id"


def _intro_video_ref():
	"""Intro video manbasi: Telegram `file_id`, https URL yoki lokal fayl yo'li.

	`BOT_INTRO_VIDEO` env o'zgaruvchisi ustuvor (file_id yoki to'g'ridan-to'g'ri
	URL bo'lishi mumkin), aks holda `media/bot/intro.mp4` qaraladi. Ikkalasi ham
	bo'lmasa — bo'sh satr qaytadi va bot matnli xabarga tushadi.
	"""
	configured = (BOT_INTRO_VIDEO or "").strip()
	if configured:
		return configured
	local = os.path.join(MEDIA_ROOT, "bot", "intro.mp4")
	return local if os.path.exists(local) else ""


def _send_intro_video(chat_id, keyboard):
	"""Intro videoni til tugmalari bilan yuboradi. Muvaffaqiyat holatini qaytaradi."""
	cached_id = cache.get(INTRO_VIDEO_CACHE_KEY)
	if cached_id:
		try:
			bot.send_video(
				chat_id, cached_id, caption=INTRO_CAPTION,
				reply_markup=keyboard, supports_streaming=True,
			)
			return True
		except Exception:
			# file_id eskirgan (masalan, bot tokeni almashgan) — qaytadan yuklaymiz.
			cache.delete(INTRO_VIDEO_CACHE_KEY)

	ref = _intro_video_ref()
	if not ref:
		return False

	try:
		if os.path.isabs(ref) and os.path.exists(ref):
			with open(ref, "rb") as video:
				sent = bot.send_video(
					chat_id, video, caption=INTRO_CAPTION,
					reply_markup=keyboard, supports_streaming=True,
				)
		else:
			sent = bot.send_video(
				chat_id, ref, caption=INTRO_CAPTION,
				reply_markup=keyboard, supports_streaming=True,
			)
	except Exception:
		logger.warning("Intro videoni yuborib bo'lmadi (chat_id=%s)", chat_id, exc_info=True)
		return False

	file_id = getattr(getattr(sent, "video", None), "file_id", None)
	if file_id:
		cache.set(INTRO_VIDEO_CACHE_KEY, file_id, None)  # muddatsiz
	return True


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


def _send_motivation_message(chat_id, first_name, lang_code):
	"""Til tanlangandan keyingi motivatsion xabar + Mini App'ni ochish tugmasi."""
	lang_code = _normalize_lang(lang_code)
	texts = LANGUAGE_TEXTS[lang_code]

	_set_menu_button(chat_id, lang_code)

	# Bot parse_mode="HTML" bilan ishlaydi — ism ichidagi `<`/`&` xabarni buzmasin.
	bot.send_message(
		chat_id,
		texts["welcome"].format(first_name=html.escape(first_name or "Champion")),
		reply_markup=_webapp_keyboard(lang_code),
	)


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

	# Eski persistent reply keyboard'ni tozalaymiz (endi ishlatilmaydi) — gift
	# deep-link bilan kelganlarda ham.
	_drop_reply_keyboard(message.chat.id)

	# Deep link: `/start gift_<code>` → open the gift claim page directly.
	parts = (message.text or "").split(maxsplit=1)
	param = parts[1].strip() if len(parts) > 1 else ""
	if param.startswith("gift_"):
		code = param[len("gift_"):].strip()
		if code:
			_send_gift_claim(message, code)
			return

	# Yangi tartib: avval ilova haqidagi intro video + til tugmalari bitta xabarda.
	# Video sozlanmagan bo'lsa yoki yuborilmasa — o'sha matn oddiy xabar sifatida.
	keyboard = _language_keyboard()
	if not _send_intro_video(message.chat.id, keyboard):
		bot.send_message(message.chat.id, INTRO_CAPTION, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("lang:"))
def handle_language_selection(call):
	user = call.from_user
	lang_code = call.data.split(":", 1)[1].strip().lower()
	if lang_code not in SUPPORTED_LANGUAGES:
		lang_code = "en"
	
	bot.answer_callback_query(call.id)
	# Til tanlandi — intro video ostidagi tugmalarni olib tashlaymiz, video esa
	# chatda qoladi.
	try:
		bot.edit_message_reply_markup(
			chat_id=call.message.chat.id,
			message_id=call.message.message_id,
			reply_markup=None,
		)
	except Exception:
		pass

	_send_motivation_message(
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
