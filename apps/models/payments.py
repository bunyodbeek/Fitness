from datetime import timedelta, date

from dateutil.relativedelta import relativedelta
from django.db.models import CASCADE, SET_NULL, ForeignKey, Model, OneToOneField, TextChoices
from django.db.models.fields import (
	BooleanField,
	CharField,
	DateTimeField,
	DecimalField,
	IntegerField, BigIntegerField,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.models.base import CreatedBaseModel


class SubscriptionPlan(Model):
	class PeriodChoices(TextChoices):
		MONTHLY = 'monthly', "1 oylik"
		QUARTERLY = 'quarterly', "3 oylik"
		YEARLY = 'yearly', "1 yillik"
	
	price = DecimalField(max_digits=10, decimal_places=2)
	period = CharField(max_length=20, choices=PeriodChoices.choices)
	
	is_active = BooleanField(default=True)
	
	def __str__(self):
		return f"{self.get_period_display()}"
	
	def get_expiry_date(self, start_date):
		if self.period == 'monthly':
			return start_date + relativedelta(months=1)
		elif self.period == 'quarterly':
			return start_date + relativedelta(months=3)
		elif self.period == 'yearly':
			return start_date + relativedelta(years=1)
		return 0
	
	# def get_expiry_date(self, start_date):
	#     data = {
	#         'monthly': relativedelta(months=1),
	#         'quarterly': relativedelta(months=3),
	#         'yearly': relativedelta(years=1)
	#     }
	#
	#     if data.get(self.period):
	#         return start_date + data[self.period]
	#     return 0
	
	def period_days(self) -> int:
		data = {
			'monthly': 30,
			'quarterly': 90,
			'yearly': 365
		}
		return data.get(self.period, 0)


class Subscription(Model):
	user = OneToOneField('apps.UserProfile', CASCADE, related_name='subscription', verbose_name=_("User"))
	plan = ForeignKey('apps.SubscriptionPlan', CASCADE, related_name='subscriptions')
	start_date = DateTimeField(_("Start Date"), auto_now_add=True)
	end_date = DateTimeField(_("End Date"), editable=False)
	is_active = BooleanField(_("Is Active"), default=True)
	
	def __calc_end_date(self):
		if not self.end_date and self.plan:
			start = self.start_date or timezone.now()
			self.end_date = self.plan.get_expiry_date(start)
	
	def save(self, *args, **kwargs):
		self.__calc_end_date()
		super().save(*args, **kwargs)
	
	@property
	def is_valid(self):
		return self.end_date < date.today()
	
	def days_remaining(self) -> int:
		if not self.is_active or not self.end_date:
			return 0
		delta: timedelta = self.end_date - timezone.now()
		return max(0, delta.days)
	
	def total_days(self):
		return max((self.end_date - self.start_date).days, 1)
	
	class Meta:
		verbose_name = _("Subscription")
		verbose_name_plural = _("Subscriptions")
		ordering = ['-start_date']
	
	def __str__(self):
		return f"{self.user.name} - Premium"


class Payment(CreatedBaseModel):
	class PaymentStatus(TextChoices):
		PENDING = 'pending', 'Kutilmoqda'
		COMPLETED = 'completed', 'Bajarildi'
		PROCESSING = 'processing', _("Jarayonda")
		FAILED = 'failed', 'Muvaffaqiyatsiz'
	
	user = ForeignKey("apps.UserProfile", CASCADE, related_name='payments', verbose_name=_("User"))
	subscription = ForeignKey('apps.Subscription', SET_NULL, null=True, blank=True, related_name='payments',
	                          verbose_name=_("Subscription"))
	status = CharField(_("Status"), max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
	amount = IntegerField(verbose_name=_('Summasi'))
	is_auto_payment = BooleanField(_("Is Auto Payment"), default=False)
	auto_payment_attempt = IntegerField(_("Automatic payment attempt"), default=0)
	completed_at = DateTimeField(_("Completed Date"), null=True, blank=True, auto_now_add=True)
	
	created_at_ms = BigIntegerField(_("Created At MS"), null=True, blank=True)
	perform_time = BigIntegerField(_("Perform Time"), null=True, default=0)
	cancel_time = BigIntegerField(_("Cancel Time"), null=True, default=0)
	state = IntegerField(_("State"), null=True, default=1)
	payme_id = CharField(max_length=255, null=True, blank=True)
	reason = IntegerField(null=True, blank=True)
	
	class Meta:
		verbose_name = _("Payment")
		verbose_name_plural = _("Payments")
	
	def mark_as_completed(self):
		self.status = self.PaymentStatus.COMPLETED
		self.completed_at = timezone.now()
		self.save(update_fields=['status', 'completed_at'])
		if self.user.telegram_id:
			msg = (
				f"✅ <b>To'lov qabul qilindi!</b>\n"
				f"Summa: {self.amount:,.0f} UZS\n"
				f"Obuna muddati: {self.subscription.end_date.strftime('%d.%m.%Y')} gacha."
			)
			# send_notification funksiyasi orqali
			from apps.bot.management import send_notification
			send_notification(self.user.telegram_id, msg)
	
	def mark_as_failed(self):
		self.status = self.PaymentStatus.FAILED
		self.save(update_fields=['status'])
