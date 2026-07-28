"""Promo kodni tekshirish va yozib qo'yish.

Ikki bosqich ataylab ajratilgan:

  * ``validate()`` — to'lov sahifasida "Qo'llash" bosilganda. Hech narsa
    yozmaydi, faqat kodni va uning foydalanuvchi uchun yaroqliligini tekshiradi.
  * ``record_redemption()`` — to'lov MUVAFFAQIYATLI yakunlangach
    (`Payment.mark_as_completed`). Faqat shu yerda `PromoRedemption` yaratiladi.

Nima uchun shunday: kod kiritib to'lovni tashlab ketgan odam
``max_redemptions`` o'rnini band qilib qo'ymasligi kerak. Buning narxi —
"qo'llash" paytida yaroqli bo'lgan kod to'lov paytida tugab qolishi mumkin;
shuning uchun `PaymentCreateView` zaryaddan oldin QAYTA tekshiradi va
`record_redemption` qulf ostida yakuniy qarorni chiqaradi.
"""
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _

from apps.models.promo import PromoCode, PromoRedemption


class PromoError:
	NOT_FOUND = 'not_found'
	INACTIVE = 'inactive'
	EXPIRED = 'expired'
	EXHAUSTED = 'exhausted'
	ALREADY_USED = 'already_used'
	EMPTY = 'empty'


# Har bir rad etish sababi uchun ALOHIDA xabar — "kod yaroqsiz" degan umumiy
# javob foydalanuvchini ham, qo'llab-quvvatlashni ham sarosimaga soladi.
ERROR_MESSAGES = {
	PromoError.EMPTY: _("Enter a promo code."),
	PromoError.NOT_FOUND: _("This promo code does not exist."),
	PromoError.INACTIVE: _("This promo code is no longer active."),
	PromoError.EXPIRED: _("This promo code has expired."),
	PromoError.EXHAUSTED: _("This promo code has reached its usage limit."),
	PromoError.ALREADY_USED: _("A promo code can only be used on your first purchase."),
}


def error_message(key):
	return ERROR_MESSAGES.get(key, ERROR_MESSAGES[PromoError.NOT_FOUND])


def has_redeemed(profile) -> bool:
	"""Foydalanuvchi promo kodni allaqachon ishlatganmi (umri davomida)."""
	return PromoRedemption.objects.filter(user=profile).exists()


def validate(raw_code, profile):
	"""``(promo_code, None)`` yoki ``(None, xato_kaliti)`` qaytaradi."""
	code = PromoCode.normalize(raw_code)
	if not code:
		return None, PromoError.EMPTY

	promo = PromoCode.objects.filter(code=code).first()
	if promo is None:
		return None, PromoError.NOT_FOUND
	if not promo.is_active:
		return None, PromoError.INACTIVE
	if promo.is_expired:
		return None, PromoError.EXPIRED
	# Foydalanuvchi tekshiruvi limitdan OLDIN: "siz allaqachon ishlatgansiz"
	# degan javob "limit tugagan" dan aniqroq va to'g'riroq.
	if has_redeemed(profile):
		return None, PromoError.ALREADY_USED
	if promo.is_exhausted:
		return None, PromoError.EXHAUSTED
	return promo, None


def record_redemption(payment):
	"""To'lov yakunlangach `PromoRedemption` yaratadi. Yaratilgan qatorni yoki
	``None`` ni qaytaradi.

	Idempotent va poyga (race) ga chidamli:
	  * `PromoCode` qatori `select_for_update` bilan qulflanadi, shuning uchun
	    ikki foydalanuvchi oxirgi o'rinni bir vaqtda ololmaydi;
	  * foydalanuvchi bo'yicha unikal cheklov `IntegrityError` bilan ushlanadi,
	    ya'ni Atmos callback'i takroran kelsa ikkinchi qator yaratilmaydi.

	Bu yerda xato yuz bersa ham to'lov BEKOR QILINMAYDI — pul allaqachon
	yechilgan. Atributsiya yozuvining yo'qligi obunani bermaslikdan afzal."""
	promo_id = payment.promo_code_id
	if not promo_id or payment.is_gift:
		return None

	with transaction.atomic():
		promo = PromoCode.objects.select_for_update().filter(pk=promo_id).first()
		if promo is None:
			return None
		if promo.is_exhausted:
			# Qulf ostida limit to'lgani aniqlandi. To'lov o'tib bo'lgan, lekin
			# chegirma allaqachon qo'llanilgan — o'rin bermaganimiz uchun
			# atributsiyani ham yozmaymiz va buni panelda ko'rish mumkin
			# (to'lovda `promo_code` bor, `redemption` yo'q).
			return None

		original = payment.original_amount or payment.amount
		try:
			return PromoRedemption.objects.create(
				promo_code=promo,
				user=payment.user,
				payment=payment,
				subscription=payment.subscription,
				original_price=original,
				discount_amount_applied=original - payment.amount,
				final_price=payment.amount,
			)
		except IntegrityError:
			# Foydalanuvchida allaqachon qator bor (takroriy callback yoki
			# parallel urinish) — unikal cheklov ushladi.
			return None
