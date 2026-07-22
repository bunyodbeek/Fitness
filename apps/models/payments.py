import secrets
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

	def cancel(self):
		"""Cancel the subscription — premium access is revoked immediately.

		``is_valid`` (and therefore ``UserProfile.is_premium``) checks
		``is_active``, so flipping it off is enough to lock premium features.
		The row is kept so the payment history and a future re-subscribe stay
		intact."""
		self.is_active = False
		self.save(update_fields=['is_active'])


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

	# A gift payment buys Premium for a friend instead of extending the payer's
	# own subscription — see PremiumGift and mark_as_completed().
	is_gift = BooleanField(_("Sovg'a to'lovi"), default=False)

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
		"""Activate the purchase and notify the user.

		A normal payment extends the payer's own subscription. A *gift* payment
		instead activates the linked ``PremiumGift`` so the payer can share it —
		their own subscription is left untouched."""
		self.status = self.PaymentStatus.COMPLETED
		self.completed_at = timezone.now()

		# A gift payment activates the sender's gift (found by is_gift + sender,
		# so it's robust to which retry attempt actually completed) and never
		# touches the sender's own subscription.
		if self.is_gift:
			gift = PremiumGift.objects.filter(sender=self.user).first()
			self.save(update_fields=['status', 'completed_at'])
			if gift is not None:
				gift.payment = self
				gift.save(update_fields=['payment'])
				gift.activate()
			return

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
			try:
				from apps.management.commands.bot_notisfication import send_notification
				send_notification(self.user.telegram_id, msg)
			except Exception as exc:
				import logging
				logging.getLogger(__name__).warning("Payment notification failed: %s", exc)

	def mark_as_failed(self):
		self.status = self.PaymentStatus.FAILED
		self.save(update_fields=['status'])


class PremiumGift(CreatedBaseModel):
	"""A one-time Premium gift a user buys for a friend (à la Telegram Premium).

	The sender pays for it through the normal Atmos flow; on success the gift
	becomes ``AVAILABLE`` and the sender gets a shareable Telegram link. The
	first person to open the link and claim it receives the gifted plan.

	The ``OneToOneField`` on ``sender`` enforces the "only one time" rule at the
	database level — a user can ever have a single gift row."""

	class Status(TextChoices):
		PENDING = 'pending', _("Kutilmoqda")      # payment not completed yet
		AVAILABLE = 'available', _("Faol")        # paid — waiting to be claimed
		CLAIMED = 'claimed', _("Olingan")         # claimed by a recipient

	sender = OneToOneField('apps.UserProfile', CASCADE, related_name='premium_gift',
	                       verbose_name=_("Yuboruvchi"))
	recipient = ForeignKey('apps.UserProfile', SET_NULL, null=True, blank=True,
	                       related_name='claimed_gifts', verbose_name=_("Qabul qiluvchi"))
	plan = ForeignKey('apps.SubscriptionPlan', SET_NULL, null=True, blank=True,
	                  related_name='gifts', verbose_name=_("Tarif"))
	payment = ForeignKey('apps.Payment', SET_NULL, null=True, blank=True,
	                     related_name='gift_payments', verbose_name=_("To'lov"))
	code = CharField(_("Kod"), max_length=64, unique=True, db_index=True)
	status = CharField(_("Status"), max_length=20, choices=Status.choices, default=Status.PENDING)
	claimed_at = DateTimeField(_("Olingan sana"), null=True, blank=True)

	class Meta:
		verbose_name = _("Premium sovg'a")
		verbose_name_plural = _("Premium sovg'alar")

	def __str__(self):
		return f"Gift {self.code} ({self.get_status_display()})"

	@staticmethod
	def generate_code() -> str:
		return secrets.token_urlsafe(16)

	@property
	def is_available(self) -> bool:
		return self.status == self.Status.AVAILABLE

	@property
	def is_used(self) -> bool:
		"""True once the gift has been paid for — i.e. the one-time chance is spent."""
		return self.status in (self.Status.AVAILABLE, self.Status.CLAIMED)

	@property
	def share_link(self) -> str:
		from apps.utils.telegram_bot_link import get_bot_deeplink
		base = get_bot_deeplink()
		if not base:
			return ''
		return f"{base}?start=gift_{self.code}"

	def activate(self):
		"""Make a paid gift claimable and notify the sender with the share link."""
		if self.status == self.Status.CLAIMED:
			return
		self.status = self.Status.AVAILABLE
		self.save(update_fields=['status'])
		self._notify_sender()

	def _notify_sender(self):
		telegram_id = getattr(self.sender, 'telegram_id', None)
		if not telegram_id:
			return
		link = self.share_link
		plan_name = self.plan.get_period_display() if self.plan else _("Premium")
		msg = (
			"🎁 <b>Premium sovg'angiz tayyor!</b>\n"
			"Quyidagi havolani do'stingizga yuboring — uni birinchi ochgan inson "
			f"{plan_name} Premium oladi.\n\n"
			f"{link}"
		)
		try:
			from apps.management.commands.bot_notisfication import send_notification
			send_notification(telegram_id, msg)
		except Exception as exc:
			import logging
			logging.getLogger(__name__).warning("Gift notification failed: %s", exc)

	def claim(self, recipient):
		"""Grant ``recipient`` the gifted plan. Returns ``(ok, error_key)``.

		Re-checks the status under the caller's row lock so two people opening
		the same link can never both claim it."""
		if self.status != self.Status.AVAILABLE:
			return False, 'unavailable'
		if recipient.id == self.sender_id:
			return False, 'self'
		plan = self.plan
		if plan is None:
			return False, 'unavailable'

		sub, _created = Subscription.objects.get_or_create(
			user=recipient, defaults={'plan': plan},
		)
		sub.extend(plan)

		self.recipient = recipient
		self.status = self.Status.CLAIMED
		self.claimed_at = timezone.now()
		self.save(update_fields=['recipient', 'status', 'claimed_at'])

		if getattr(recipient, 'telegram_id', None):
			plan_name = plan.get_period_display() if plan else _("Premium")
			try:
				from apps.management.commands.bot_notisfication import send_notification
				send_notification(
					recipient.telegram_id,
					"🎉 <b>Premium faollashtirildi!</b>\n"
					f"Sizga {plan_name} Premium sovg'a qilindi. Obuna {sub.end_date.strftime('%d.%m.%Y')} gacha.",
				)
			except Exception as exc:
				import logging
				logging.getLogger(__name__).warning("Gift claim notification failed: %s", exc)

		return True, None