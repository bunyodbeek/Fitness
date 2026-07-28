"""Promo kodlar — trener/sotuvchi bo'yicha chegirma va sotuv atributsiyasi.

Qoida: promo kod foydalanuvchining FAQAT BIRINCHI pullik obunasiga ishlaydi
(tarif uzunligidan qat'i nazar: 1/3/6/12 oy). Shundan keyin o'sha foydalanuvchi
uchun `PromoRedemption` qatori mavjud bo'ladi va keyingi har qanday to'lovda
kiritilgan kod rad etiladi.

Chegirma KEYINGI to'lovlarga o'tmaydi. Buni ta'minlash oson: obuna narxi hech
qayerda saqlanmaydi — `Subscription` da narx maydoni umuman yo'q va har safar
`plan.price_uzs` dan qayta o'qiladi. Chegirmali summa faqat bitta `Payment`
qatorida, tarixiy yozuv sifatida qoladi.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db.models import (
	CASCADE, PROTECT, SET_NULL, BooleanField, CharField, DateTimeField,
	DecimalField, ForeignKey, Model, PositiveIntegerField, Q, UniqueConstraint,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.models.base import CreatedBaseModel

# Kodda faqat KATTA lotin harflari va raqamlar. Bu ataylab qattiq qoida:
# shunga o'xshash belgilar muammosi (kirilcha "О" va lotincha "O", "І" va "I")
# kod YARATILAYOTGAN paytda to'siladi, ya'ni chalkashtiradigan kod umuman
# mavjud bo'la olmaydi. Qidiruv esa oddiy `__exact` bo'lib qoladi —
# `iexact`/`LOWER()` indeksni buzmaydi.
CODE_VALIDATOR = RegexValidator(
	r'^[A-Z0-9]+$',
	_("The code may contain only Latin letters A-Z and digits 0-9."),
)


class PromoCode(CreatedBaseModel):
	code = CharField(
		_("Promo kod"), max_length=32, unique=True, validators=[CODE_VALIDATOR],
		help_text=_("Latin letters and digits only. Case does not matter when entering."),
	)
	discount_percent = PositiveIntegerField(
		_("Chegirma (%)"),
		validators=[MinValueValidator(1), MaxValueValidator(100)],
	)
	# Trener / sotuvchi ismi. Ataylab oddiy matn, User FK emas — kod egasi
	# ilovada ro'yxatdan o'tgan bo'lishi shart emas.
	owner_label = CharField(_("Egasi (trener/sotuvchi)"), max_length=120, blank=True)
	is_active = BooleanField(_("Faol"), default=True)
	expires_at = DateTimeField(_("Amal qilish muddati"), null=True, blank=True)
	max_redemptions = PositiveIntegerField(
		_("Maksimal ishlatilish soni"), null=True, blank=True,
		help_text=_("Leave empty for unlimited."),
	)
	created_by = ForeignKey(
		'apps.User', SET_NULL, null=True, blank=True, related_name='created_promo_codes',
		verbose_name=_("Kim yaratdi"),
	)

	class Meta:
		verbose_name = _("Promo kod")
		verbose_name_plural = _("Promo kodlar")
		ordering = ['-created_at']

	def __str__(self):
		return self.code

	@staticmethod
	def normalize(raw: str) -> str:
		"""Kiritilgan matnni saqlash/qidirish shakliga keltiradi.

		Bo'shliqlar (ichkilari ham — nusxa ko'chirishda tez-tez tushadi) olib
		tashlanadi va katta harfga o'tkaziladi."""
		return ''.join((raw or '').split()).upper()

	def clean(self):
		self.code = self.normalize(self.code)
		super().clean()

	def save(self, *args, **kwargs):
		# `clean()` ni chaqirmaydigan yo'llar ham bor (masalan skript, bulk).
		# Normalizatsiya BITTA joyda kafolatlansin.
		self.code = self.normalize(self.code)
		super().save(*args, **kwargs)

	@property
	def is_expired(self) -> bool:
		return bool(self.expires_at and self.expires_at <= timezone.now())

	@property
	def redemption_count(self) -> int:
		return self.redemptions.count()

	@property
	def is_exhausted(self) -> bool:
		return bool(self.max_redemptions and self.redemption_count >= self.max_redemptions)

	def discount_for(self, amount) -> Decimal:
		"""``amount`` dan ushlanadigan chegirma summasi (tiyinsiz, butun so'mga).

		Yaxlitlash chegirma foydasiga emas, standart HALF_UP bilan qilinadi va
		natija hech qachon summadan oshmaydi."""
		amount = Decimal(amount)
		raw = amount * Decimal(self.discount_percent) / Decimal(100)
		discount = raw.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
		return min(discount, amount)

	def final_price_for(self, amount) -> Decimal:
		return Decimal(amount) - self.discount_for(amount)


class PromoRedemption(CreatedBaseModel):
	"""Muvaffaqiyatli ishlatilgan promo kod — komissiya hisobining manbai.

	Qator FAQAT to'lov muvaffaqiyatli yakunlanganda yaratiladi
	(`Payment.mark_as_completed`). Kod kiritilib to'lov tashlab ketilsa hech
	narsa yozilmaydi va `max_redemptions` o'rni band bo'lib qolmaydi."""

	promo_code = ForeignKey(
		'apps.PromoCode', PROTECT, related_name='redemptions', verbose_name=_("Promo kod"),
	)
	user = ForeignKey(
		'apps.UserProfile', CASCADE, related_name='promo_redemptions', verbose_name=_("Foydalanuvchi"),
	)
	# To'lov — atributsiya uchun ASOSIY bog'lanish: tarif, summa va sana shu
	# yerda. `subscription` esa foydalanuvchida bitta (O2O) va uzaytirilib
	# boraveradi, shuning uchun undan qaysi xarid ekanini bilib bo'lmaydi.
	payment = ForeignKey(
		'apps.Payment', SET_NULL, null=True, blank=True, related_name='promo_redemptions',
		verbose_name=_("To'lov"),
	)
	subscription = ForeignKey(
		'apps.Subscription', SET_NULL, null=True, blank=True, related_name='promo_redemptions',
		verbose_name=_("Obuna"),
	)

	original_price = DecimalField(_("Asl narx"), max_digits=12, decimal_places=2)
	discount_amount_applied = DecimalField(_("Chegirma summasi"), max_digits=12, decimal_places=2)
	final_price = DecimalField(_("Yakuniy narx"), max_digits=12, decimal_places=2)
	redeemed_at = DateTimeField(_("Ishlatilgan sana"), default=timezone.now)

	class Meta:
		verbose_name = _("Promo kod ishlatilishi")
		verbose_name_plural = _("Promo kod ishlatilishlari")
		ordering = ['-redeemed_at']
		constraints = [
			# Har bir foydalanuvchi UMRIDA bir marta. Ataylab kod bo'yicha emas,
			# global — "faqat birinchi pullik obuna" qoidasining ma'lumotlar
			# bazasi darajasidagi kafolati.
			UniqueConstraint(fields=['user'], name='uniq_promo_redemption_per_user'),
		]

	def __str__(self):
		return f"{self.promo_code_id} → {self.user_id}"
