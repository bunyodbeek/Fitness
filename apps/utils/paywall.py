"""7-kunlik paywall gate qoidalari — YAGONA manba.

Ro'yxatdan o'tgandan 7 kun o'tgach obunasi yo'q foydalanuvchi premium
sahifasida qamalib qoladi: hech qanday tab, ma'lumotnoma, mashqlar, mushak
xaritasi yoki PDF ochilmaydi. Qaror `UserProfile.has_app_access` da hisoblanadi
(premium YOKI sinov ichida), bu yerda esa faqat "qaysi manzillar ochiq
qolishi" ro'yxati va uni HTTP qatlamiga ulash bor.

Nazorat SERVER tomonida — `PaywallGateMiddleware` har bir so'rovda ishlaydi.
Klientdagi redirect faqat UX uchun va hech qachon ishonch manbai emas.
"""
from django.urls import Resolver404, resolve, reverse

# Til prefiksisiz (i18n_patterns tashqarisidagi) manzillar va statik fayllar.
EXEMPT_PATH_PREFIXES = (
	'/static/',
	'/media/',
	'/app/',                        # mini app kirish nuqtasi (tilni aniqlaydi)
	'/bot/webhook/',                # Telegram webhook
	'/payments/atmos/callback/',    # Atmos natija callback'i — gate'ga tushmasligi SHART
	'/favicon.ico',
)

# Gate paytida ham ochiq qoladigan URL nomlari. Ro'yxat ataylab qisqa: to'lovni
# yakunlash uchun kerak bo'lgan zanjir + autentifikatsiya + til almashtirish.
EXEMPT_URL_NAMES = frozenset({
	# Kirish / autentifikatsiya / onboarding
	'animation',                # intro video — gate ANIQ shundan KEYIN chiqadi
	'onboarding',
	'questionnaire_submit',
	'auth_telegram',
	'language_select',
	'workout_type_select',
	'miniapp_entry',

	# Gate sahifasining o'zi va to'liq to'lov zanjiri
	'paywall_gate',
	'premium',
	'tariff_select',
	'payment_method',
	'payment_create',
	'payment_otp',
	'payment_otp_resend',
	'payment_success',
	'promo_apply',
	'promo_remove',
	'atmos_callback',

	# Sovg'a havolasini ochish premium BERADI — bloklash mantiqsiz.
	'gift_claim',

	# Gate sahifasida tilni almashtira olishi kerak.
	'change_language',
	'set_language',
})

# Butun namespace sifatida ochiq qoladiganlar (xodimlar uchun boshqaruv paneli).
EXEMPT_NAMESPACES = frozenset({'panel'})


def is_exempt_path(path: str) -> bool:
	return path.startswith(EXEMPT_PATH_PREFIXES)


def is_exempt_route(path: str) -> bool:
	"""URL NOMI bo'yicha tekshiramiz, manzil satri bo'yicha emas — shunda
	til prefiksi (/uz/, /ru/, /en/) va kelajakdagi manzil o'zgarishlari
	ro'yxatni buzmaydi."""
	try:
		match = resolve(path)
	except Resolver404:
		# Noma'lum manzil = 404. Uni gate qilish 404 o'rniga redirect berardi.
		return True
	if match.namespace in EXEMPT_NAMESPACES:
		return True
	return match.url_name in EXEMPT_URL_NAMES


def user_is_gated(user) -> bool:
	"""``user`` hozir paywall ortida qolishi kerakmi.

	Profil topilmasa False — bunday holatni `TelegramProfileRedirectMiddleware`
	hal qiladi, biz uni onboardingga borish yo'lida to'sib qo'ymaymiz."""
	if not user or not user.is_authenticated:
		return False
	# Xodimlar (panel, qo'llab-quvvatlash) hech qachon qamalmaydi.
	if user.is_staff or user.is_superuser:
		return False
	from apps.models import UserProfile
	try:
		# `user.profile` teskari O2O — Django uni instansiyada keshlaydi, shuning
		# uchun keyingi view'lardagi `request.user.profile` qayta so'rov qilmaydi.
		profile = user.profile
	except UserProfile.DoesNotExist:
		return False
	return not profile.has_app_access


def gate_url() -> str:
	return reverse('paywall_gate')
