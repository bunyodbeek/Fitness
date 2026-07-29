"""Foydalanuvchi tilini profilda saqlash va bot xabarlarida ishlatish.

Ilova tilni cookie/sessiyadan oladi (`LocaleMiddleware`), lekin BOT xabarlari
uchun bu yetmaydi: ular cron (`premium_notifications`), webhook yoki Atmos
callback'idan ketadi — u yerlarda so'rov ham, sessiya ham yo'q. Shuning uchun
tanlangan til `UserProfile.language` da ham saqlanadi.

Til tanlanadigan HAR BIR joy shu moduldagi `remember_language()` ni chaqiradi,
xabar yuboradigan har bir joy esa `user_locale()` ichida matn tayyorlaydi.
"""
from contextlib import contextmanager

from django.conf import settings
from django.utils import translation

DEFAULT_LANGUAGE = 'uz'


def normalize(code) -> str | None:
	"""``code`` ni qo'llab-quvvatlanadigan til kodiga keltiradi yoki ``None``.

	`en-US` kabi qiymatlar ham keladi (Telegram `language_code`, brauzer
	`Accept-Language`), shuning uchun faqat birinchi ikki harf olinadi."""
	code = (code or '').strip().lower()[:2]
	valid = {lang[0] for lang in settings.LANGUAGES}
	return code if code in valid else None


def remember_language(profile, code) -> bool:
	"""Tanlangan tilni profilga yozadi. O'zgargan bo'lsa ``True`` qaytaradi.

	Til almashtirish foydalanuvchi kutayotgan amal, shuning uchun bu yerda hech
	qachon istisno ko'tarilmasligi kerak — profil yo'q yoki kod noto'g'ri
	bo'lsa jimgina qaytamiz."""
	code = normalize(code)
	if profile is None or code is None or profile.language == code:
		return False
	profile.language = code
	profile.save(update_fields=['language'])
	return True


def language_of(profile) -> str:
	return normalize(getattr(profile, 'language', None)) or DEFAULT_LANGUAGE


@contextmanager
def user_locale(profile):
	"""Blok ichidagi tarjimalarni ``profile`` tilida hisoblaydi.

	Xabar matni SHU blok ichida yig'ilishi shart — `gettext` chaqirilgan payt
	muhim, satr keyinroq ishlatilgani emas."""
	with translation.override(language_of(profile)):
		yield
