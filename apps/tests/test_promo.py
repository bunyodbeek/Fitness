"""Promo kod tekshiruvi va ishlatilishini yozib qo'yish testlari.

Diqqat markazi — pul bilan bog'liq qoidalar: kim chegirma ololadi, necha marta
va chegirma keyingi to'lovlarga o'tib ketmasligi.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.models import (
	Payment, PromoCode, PromoRedemption, Subscription, SubscriptionPlan, User, UserProfile,
)
from apps.services.promo import PromoError, record_redemption, validate


class PromoCodeModelTests(TestCase):

	def test_code_is_normalized_on_save(self):
		promo = PromoCode.objects.create(code="  al ex 20 ", discount_percent=20)
		self.assertEqual(promo.code, "ALEX20")

	def test_lookup_is_case_and_whitespace_insensitive(self):
		PromoCode.objects.create(code="ALEX20", discount_percent=20)
		self.assertEqual(PromoCode.normalize(" alex20 "), "ALEX20")
		self.assertEqual(PromoCode.normalize("Alex 20"), "ALEX20")

	def test_discount_rounds_half_up_and_never_exceeds_the_amount(self):
		promo = PromoCode(code="X", discount_percent=15)
		self.assertEqual(promo.discount_for(Decimal("100000")), Decimal("15000"))
		# 33.333% emas — 15% dan 12345 → 1851.75 → 1852
		self.assertEqual(promo.discount_for(Decimal("12345")), Decimal("1852"))
		full = PromoCode(code="Y", discount_percent=100)
		self.assertEqual(full.final_price_for(Decimal("99999")), Decimal("0"))

	def test_expiry_and_exhaustion_flags(self):
		past = PromoCode.objects.create(
			code="OLD", discount_percent=10, expires_at=timezone.now() - timedelta(hours=1),
		)
		self.assertTrue(past.is_expired)
		unlimited = PromoCode.objects.create(code="FREE", discount_percent=10)
		self.assertFalse(unlimited.is_exhausted)


class PromoValidationTests(TestCase):

	@classmethod
	def setUpTestData(cls):
		cls.plan = SubscriptionPlan.objects.create(
			price_uzs=Decimal("100000"), price_usd=10,
			period=SubscriptionPlan.PeriodChoices.MONTHLY,
		)

	def _profile(self, name="U"):
		user = User.objects.create_user(username=f"u{name}{timezone.now().timestamp()}", password="x")
		return UserProfile.objects.create(user=user, name=name)

	def test_valid_code_passes(self):
		promo = PromoCode.objects.create(code="ALEX20", discount_percent=20)
		found, error = validate("alex20", self._profile())
		self.assertIsNone(error)
		self.assertEqual(found, promo)

	def test_each_failure_has_its_own_reason(self):
		profile = self._profile()
		self.assertEqual(validate("", profile)[1], PromoError.EMPTY)
		self.assertEqual(validate("NOPE", profile)[1], PromoError.NOT_FOUND)

		PromoCode.objects.create(code="OFF", discount_percent=10, is_active=False)
		self.assertEqual(validate("OFF", profile)[1], PromoError.INACTIVE)

		PromoCode.objects.create(
			code="OLD", discount_percent=10, expires_at=timezone.now() - timedelta(hours=1),
		)
		self.assertEqual(validate("OLD", profile)[1], PromoError.EXPIRED)

	def test_exhausted_code_is_rejected(self):
		promo = PromoCode.objects.create(code="LIMIT", discount_percent=10, max_redemptions=1)
		PromoRedemption.objects.create(
			promo_code=promo, user=self._profile("first"),
			original_price=Decimal("100000"), discount_amount_applied=Decimal("10000"),
			final_price=Decimal("90000"),
		)
		self.assertEqual(validate("LIMIT", self._profile("second"))[1], PromoError.EXHAUSTED)

	def test_a_user_can_only_ever_redeem_once(self):
		"""Ikkinchi kod ham rad etiladi — qoida kod bo'yicha emas, foydalanuvchi
		bo'yicha global."""
		first = PromoCode.objects.create(code="ONE", discount_percent=10)
		PromoCode.objects.create(code="TWO", discount_percent=50)
		profile = self._profile()
		PromoRedemption.objects.create(
			promo_code=first, user=profile,
			original_price=Decimal("100000"), discount_amount_applied=Decimal("10000"),
			final_price=Decimal("90000"),
		)
		self.assertEqual(validate("TWO", profile)[1], PromoError.ALREADY_USED)
		self.assertEqual(validate("ONE", profile)[1], PromoError.ALREADY_USED)

	def test_one_redemption_per_user_is_enforced_by_the_database(self):
		promo = PromoCode.objects.create(code="DB", discount_percent=10)
		profile = self._profile()
		kwargs = dict(
			promo_code=promo, user=profile, original_price=Decimal("1"),
			discount_amount_applied=Decimal("0"), final_price=Decimal("1"),
		)
		PromoRedemption.objects.create(**kwargs)
		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				PromoRedemption.objects.create(**kwargs)


class PromoRedemptionRecordingTests(TestCase):

	@classmethod
	def setUpTestData(cls):
		cls.plan = SubscriptionPlan.objects.create(
			price_uzs=Decimal("100000"), price_usd=10,
			period=SubscriptionPlan.PeriodChoices.MONTHLY,
		)

	def _profile(self, name="U"):
		user = User.objects.create_user(username=f"u{name}{timezone.now().timestamp()}", password="x")
		return UserProfile.objects.create(user=user, name=name)

	def _payment(self, profile, promo, amount, original):
		return Payment.objects.create(
			user=profile, plan=self.plan, amount=amount, original_amount=original,
			promo_code=promo, status=Payment.PaymentStatus.PROCESSING,
		)

	def test_completing_a_payment_records_the_redemption(self):
		promo = PromoCode.objects.create(code="ALEX20", discount_percent=20, owner_label="Alex")
		profile = self._profile()
		payment = self._payment(profile, promo, Decimal("80000"), Decimal("100000"))

		payment.mark_as_completed()

		redemption = PromoRedemption.objects.get(user=profile)
		self.assertEqual(redemption.promo_code, promo)
		self.assertEqual(redemption.original_price, Decimal("100000"))
		self.assertEqual(redemption.discount_amount_applied, Decimal("20000"))
		self.assertEqual(redemption.final_price, Decimal("80000"))
		self.assertEqual(redemption.payment, payment)

	def test_a_repeated_callback_does_not_double_record(self):
		promo = PromoCode.objects.create(code="TWICE", discount_percent=20)
		profile = self._profile()
		payment = self._payment(profile, promo, Decimal("80000"), Decimal("100000"))

		payment.mark_as_completed()
		record_redemption(payment)
		record_redemption(payment)

		self.assertEqual(PromoRedemption.objects.filter(user=profile).count(), 1)

	def test_payment_without_a_promo_records_nothing(self):
		profile = self._profile()
		payment = Payment.objects.create(
			user=profile, plan=self.plan, amount=Decimal("100000"),
			status=Payment.PaymentStatus.PROCESSING,
		)
		payment.mark_as_completed()
		self.assertFalse(PromoRedemption.objects.filter(user=profile).exists())

	def test_exhausted_code_records_nothing_but_still_grants_the_subscription(self):
		"""Pul yechilgan — obuna HAR HOLDA berilishi kerak, atributsiya yo'q bo'lsa ham."""
		promo = PromoCode.objects.create(code="RACE", discount_percent=20, max_redemptions=1)
		PromoRedemption.objects.create(
			promo_code=promo, user=self._profile("winner"),
			original_price=Decimal("100000"), discount_amount_applied=Decimal("20000"),
			final_price=Decimal("80000"),
		)
		loser = self._profile("loser")
		payment = self._payment(loser, promo, Decimal("80000"), Decimal("100000"))

		payment.mark_as_completed()

		self.assertFalse(PromoRedemption.objects.filter(user=loser).exists())
		self.assertTrue(Subscription.objects.filter(user=loser).exists())
		self.assertEqual(payment.status, Payment.PaymentStatus.COMPLETED)

	def test_renewal_charges_the_regular_price(self):
		"""Chegirma KEYINGI to'lovga o'tmaydi — obunada narx saqlanmaydi."""
		promo = PromoCode.objects.create(code="ONCE", discount_percent=50)
		profile = self._profile()
		self._payment(profile, promo, Decimal("50000"), Decimal("100000")).mark_as_completed()

		subscription = Subscription.objects.get(user=profile)
		# Obuna faqat tarifga ishora qiladi; narx har safar tarifdan o'qiladi.
		self.assertFalse(hasattr(subscription, 'price'))
		self.assertEqual(subscription.plan.price_uzs, Decimal("100000"))

		renewal = Payment.objects.create(
			user=profile, plan=self.plan, amount=subscription.plan.price_uzs,
			status=Payment.PaymentStatus.PROCESSING,
		)
		renewal.mark_as_completed()
		self.assertEqual(renewal.amount, Decimal("100000"))
		self.assertEqual(PromoRedemption.objects.filter(user=profile).count(), 1)

	def test_gift_payments_never_redeem(self):
		promo = PromoCode.objects.create(code="GIFT", discount_percent=20)
		profile = self._profile()
		payment = self._payment(profile, promo, Decimal("80000"), Decimal("100000"))
		payment.is_gift = True
		payment.save(update_fields=['is_gift'])

		payment.mark_as_completed()

		self.assertFalse(PromoRedemption.objects.filter(user=profile).exists())
