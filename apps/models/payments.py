from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.db.models import (
	CASCADE, SET_NULL, ForeignKey, Model, OneToOneField, TextChoices,
)
from django.db.models.fields import (
	BooleanField, CharField, DateTimeField, DecimalField, IntegerField, BigIntegerField,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.models.base import CreatedBaseModel


class SubscriptionPlan(Model):
	class PeriodChoices(TextChoices):
		MONTHLY = 'monthly', _("1 oylik")
		QUARTERLY = 'quarterly', _("3 oylik")
		SEMIANNUAL = 'semiannual', _("6 oylik")
		YEARLY = 'yearly', _("1 yillik")

	# Admin sets both prices independently — they are NOT derived from each other
	price_uzs = DecimalField(_("Narx (UZS)"), max_digits=12, decimal_places=2)
	price_usd = DecimalField(_("Narx (USD)"), max_digits=10, decimal_places=2)

	period = CharField(_("Davr"), max_length=20, choices=PeriodChoices.choices, unique=True)
	is_popular = BooleanField(_("Eng mashhur"), default=False)
	is_active = BooleanField(_("Faol"), default=True)
	order = IntegerField(_("Tartib"), default=0)

	class Meta:
		verbose_name = _("Obuna tarifi")
		verbose_name_plural = _("Obuna tariflari")
		ordering = ['order', 'price_uzs']

	def __str__(self):
		return f"{self.get_period_display()}"

	@property
	def months(self) -> int:
		return {'monthly': 1, 'quarterly': 3, 'semiannual': 6, 'yearly': 12}.get(self.period, 0)

	def price_for(self, currency: str):
		return self.price_usd if currency == Payment.Currency.USD else self.price_uzs

	def get_expiry_date(self, start_date):
		months_map = {
			'monthly': relativedelta(months=1),
			'quarterly': relativedelta(months=3),
			'semiannual': relativedelta(months=6),
			'yearly': relativedelta(years=1),
		}
		delta = months_map.get(self.period)
		return start_date + delta if delta else start_date

	def period_days(self) -> int:
		return {'monthly': 30, 'quarterly': 90, 'semiannual': 180, 'yearly': 365}.get(self.period, 0)


class Subscription(Model):
	user = OneToOneField('apps.UserProfile', CASCADE, related_name='subscription', verbose_name=_("User"))
	plan = ForeignKey('apps.SubscriptionPlan', CASCADE, related_name='subscriptions', verbose_name=_("Tarif"))
	start_date = DateTimeField(_("Boshlanish sanasi"), auto_now_add=True)
	end_date = DateTimeField(_("Tugash sanasi"), editable=False)
	is_active = BooleanField(_("Faol"), default=True)

	class Meta:
		verbose_name = _("Obuna")
		verbose_name_plural = _("Obunalar")
		ordering = ['-start_date']

	def __str__(self):
		return f"{self.user} - Premium"

	def _calc_end_date(self):
		if not self.end_date and self.plan:
			start = self.start_date or timezone.now()
			self.end_date = self.plan.get_expiry_date(start)

	def save(self, *args, **kwargs):
		self._calc_end_date()
		super().save(*args, **kwargs)

	@property
	def is_valid(self) -> bool:
		# Valid while not expired (your old version had this inverted)
		return self.is_active and self.end_date and self.end_date >= timezone.now()

	def days_remaining(self) -> int:
		if not self.is_valid:
			return 0
		delta: timedelta = self.end_date - timezone.now()
		return max(0, delta.days)

	def total_days(self) -> int:
		if not self.end_date:
			return 1
		return max((self.end_date - self.start_date).days, 1)

	def extend(self, plan=None):
		"""Renew / extend from current end_date (or now if already expired)."""
		plan = plan or self.plan
		base = self.end_date if (self.end_date and self.end_date > timezone.now()) else timezone.now()
		self.plan = plan
		self.end_date = plan.get_expiry_date(base)
		self.is_active = True
		self.save()


class Payment(CreatedBaseModel):
	class PaymentStatus(TextChoices):
		PENDING = 'pending', _("Kutilmoqda")
		PROCESSING = 'processing', _("Jarayonda")
		COMPLETED = 'completed', _("Bajarildi")
		FAILED = 'failed', _("Muvaffaqiyatsiz")

	class Currency(TextChoices):
		UZS = 'UZS', 'UZS'
		USD = 'USD', 'USD'

	class Method(TextChoices):
		HUMO = 'humo', 'Humo'
		UZCARD = 'uzcard', 'Uzcard'
		VISA = 'visa', 'Visa'
		MASTERCARD = 'mastercard', 'Mastercard'

	user = ForeignKey('apps.UserProfile', CASCADE, related_name='payments', verbose_name=_("User"))
	plan = ForeignKey('apps.SubscriptionPlan', SET_NULL, null=True, blank=True, related_name='payments',
	                  verbose_name=_("Tarif"))
	subscription = ForeignKey('apps.Subscription', SET_NULL, null=True, blank=True, related_name='payments',
	                          verbose_name=_("Obuna"))

	status = CharField(_("Status"), max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
	amount = DecimalField(_("Summasi"), max_digits=12, decimal_places=2)
	currency = CharField(_("Valyuta"), max_length=3, choices=Currency.choices, default=Currency.UZS)
	method = CharField(_("To'lov usuli"), max_length=20, choices=Method.choices, null=True, blank=True)

	is_auto_payment = BooleanField(_("Avto to'lov"), default=False)
	auto_payment_attempt = IntegerField(_("Avto to'lov urinishi"), default=0)
	completed_at = DateTimeField(_("Bajarilgan sana"), null=True, blank=True)

	# Atmos transaction id (returned by /merchant/pay/create).
	atmos_transaction_id = BigIntegerField(_("Atmos transaction id"), null=True, blank=True, db_index=True)

	# Payme/Click integration fields (kept for the future)
	created_at_ms = BigIntegerField(_("Created At MS"), null=True, blank=True)
	perform_time = BigIntegerField(_("Perform Time"), null=True, default=0)
	cancel_time = BigIntegerField(_("Cancel Time"), null=True, default=0)
	state = IntegerField(_("State"), null=True, default=1)
	payme_id = CharField(max_length=255, null=True, blank=True)
	reason = IntegerField(null=True, blank=True)

	class Meta:
		verbose_name = _("To'lov")
		verbose_name_plural = _("To'lovlar")
		ordering = ['-created_at']

	def __str__(self):
		return f"{self.user} - {self.amount} {self.currency} ({self.get_status_display()})"

	def mark_as_completed(self):
		"""Activate / extend the subscription and notify the user."""
		self.status = self.PaymentStatus.COMPLETED
		self.completed_at = timezone.now()

		sub, _created = Subscription.objects.get_or_create(
			user=self.user,
			defaults={'plan': self.plan},
		)
		sub.extend(self.plan)
		self.subscription = sub
		self.save(update_fields=['status', 'completed_at', 'subscription'])

		if getattr(self.user, 'telegram_id', None):
			msg = (
				f"✅ <b>To'lov qabul qilindi!</b>\n"
				f"Summa: {self.amount:,.0f} {self.currency}\n"
				f"Obuna muddati: {sub.end_date.strftime('%d.%m.%Y')} gacha."
			)
			from apps.management.commands.bot_notisfication import send_notification
			send_notification(self.user.telegram_id, msg)

	def mark_as_failed(self):
		self.status = self.PaymentStatus.FAILED
		self.save(update_fields=['status'])