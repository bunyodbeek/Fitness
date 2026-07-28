"""Promo kodning to'lov sahifasidagi oqimi (qo'llash → zaryad → yozib qo'yish).

Asosiy xavf — klient holatiga ishonish. Shuning uchun testlar chegirma FAQAT
serverda hisoblanishini va "qo'llash" bilan "to'lash" orasida o'zgargan holat
zaryadga ta'sir qilishini tekshiradi.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.models import (
	Payment, PromoCode, PromoRedemption, SubscriptionPlan, User, UserProfile,
)
from apps.views.payments import PROMO_SESSION_KEY


class PromoCheckoutTests(TestCase):

	def setUp(self):
		self.plan = SubscriptionPlan.objects.create(
			price_uzs=Decimal("100000"), price_usd=10,
			period=SubscriptionPlan.PeriodChoices.MONTHLY,
		)
		self.user = User.objects.create_user(username="payer", password="x")
		self.profile = UserProfile.objects.create(user=self.user, name="Payer")
		self.client.force_login(self.user)
		self.promo = PromoCode.objects.create(code="ALEX20", discount_percent=20, owner_label="Alex")

	def _apply(self, code):
		return self.client.post(reverse('promo_apply'), {'code': code})

	def _pay(self):
		return self.client.post(
			reverse('payment_create', args=[self.plan.id]),
			{'card_number': '8600123412341234', 'expiry': '12/30', 'currency': 'UZS'},
		)

	# ── qo'llash / olib tashlash ───────────────────────────────────────────
	def test_apply_stores_the_code_in_the_session(self):
		response = self._apply(" alex20 ")
		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertTrue(body['ok'])
		self.assertEqual(body['code'], "ALEX20")
		self.assertEqual(body['discount_percent'], 20)
		self.assertEqual(self.client.session[PROMO_SESSION_KEY], "ALEX20")

	def test_apply_never_creates_a_redemption(self):
		"""To'lovni tashlab ketgan odam limitdan o'rin band qilmasligi kerak."""
		self._apply("ALEX20")
		self.assertFalse(PromoRedemption.objects.exists())

	def test_invalid_code_returns_its_specific_reason(self):
		response = self._apply("NOPE")
		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['error'], 'not_found')
		self.assertNotIn(PROMO_SESSION_KEY, self.client.session)

	def test_remove_clears_the_session(self):
		self._apply("ALEX20")
		self.client.post(reverse('promo_remove'))
		self.assertNotIn(PROMO_SESSION_KEY, self.client.session)

	def test_applied_promo_survives_a_page_reload(self):
		self._apply("ALEX20")
		html = self.client.get(reverse('tariff_select')).content
		self.assertIn(b"ALEX20", html)

	# ── zaryad ─────────────────────────────────────────────────────────────
	@patch('apps.views.payments.AtmosClient')
	def test_charge_uses_the_discounted_amount(self, mock_client):
		mock_client.return_value.create_transaction.return_value = 777
		self._apply("ALEX20")

		self.assertEqual(self._pay().status_code, 200)

		payment = Payment.objects.get()
		self.assertEqual(payment.amount, Decimal("80000"))
		self.assertEqual(payment.original_amount, Decimal("100000"))
		self.assertEqual(payment.promo_code, self.promo)
		# Atmos tiyinda oladi — chegirmali summadan.
		self.assertEqual(
			mock_client.return_value.create_transaction.call_args.kwargs['amount_tiyin'],
			8000000,
		)

	@patch('apps.views.payments.AtmosClient')
	def test_charge_without_a_promo_uses_the_full_price(self, mock_client):
		mock_client.return_value.create_transaction.return_value = 777
		self._pay()
		payment = Payment.objects.get()
		self.assertEqual(payment.amount, Decimal("100000"))
		self.assertIsNone(payment.original_amount)
		self.assertIsNone(payment.promo_code)

	@patch('apps.views.payments.AtmosClient')
	def test_code_deactivated_between_apply_and_pay_is_rejected(self, mock_client):
		"""Server zaryaddan oldin QAYTA tekshiradi."""
		mock_client.return_value.create_transaction.return_value = 777
		self._apply("ALEX20")
		PromoCode.objects.filter(pk=self.promo.pk).update(is_active=False)

		response = self._pay()

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['promo_error'], 'inactive')
		self.assertFalse(Payment.objects.exists())
		self.assertNotIn(PROMO_SESSION_KEY, self.client.session)

	@patch('apps.views.payments.AtmosClient')
	def test_tampering_with_the_client_cannot_change_the_amount(self, mock_client):
		"""Summani klient umuman yubormaydi — u faqat tarifdan olinadi."""
		mock_client.return_value.create_transaction.return_value = 777
		self.client.post(
			reverse('payment_create', args=[self.plan.id]),
			{
				'card_number': '8600123412341234', 'expiry': '12/30',
				'currency': 'UZS', 'amount': '1', 'discount_percent': '99',
			},
		)
		self.assertEqual(Payment.objects.get().amount, Decimal("100000"))

	@patch('apps.views.payments.AtmosClient')
	def test_gift_payments_ignore_an_applied_promo(self, mock_client):
		mock_client.return_value.create_transaction.return_value = 777
		self._apply("ALEX20")
		self.client.post(
			reverse('payment_create', args=[self.plan.id]),
			{'card_number': '8600123412341234', 'expiry': '12/30', 'is_gift': '1'},
		)
		payment = Payment.objects.get()
		self.assertTrue(payment.is_gift)
		self.assertEqual(payment.amount, Decimal("100000"))
		self.assertIsNone(payment.promo_code)

	# ── to'liq zanjir ──────────────────────────────────────────────────────
	@patch('apps.views.payments.AtmosClient')
	def test_full_flow_records_attribution_once(self, mock_client):
		mock_client.return_value.create_transaction.return_value = 777
		self._apply("ALEX20")
		self._pay()
		payment = Payment.objects.get()

		payment.mark_as_completed()

		redemption = PromoRedemption.objects.get()
		self.assertEqual(redemption.promo_code, self.promo)
		self.assertEqual(redemption.user, self.profile)
		self.assertEqual(redemption.original_price, Decimal("100000"))
		self.assertEqual(redemption.discount_amount_applied, Decimal("20000"))
		self.assertEqual(redemption.final_price, Decimal("80000"))

	@patch('apps.views.payments.AtmosClient')
	def test_second_purchase_cannot_use_a_promo(self, mock_client):
		mock_client.return_value.create_transaction.return_value = 777
		self._apply("ALEX20")
		self._pay()
		Payment.objects.get().mark_as_completed()

		# Boshqa kod bilan ikkinchi urinish.
		PromoCode.objects.create(code="SECOND", discount_percent=50)
		response = self._apply("SECOND")

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['error'], 'already_used')

	def test_success_page_clears_the_applied_code(self):
		self._apply("ALEX20")
		self.client.get(reverse('payment_success'))
		self.assertNotIn(PROMO_SESSION_KEY, self.client.session)
