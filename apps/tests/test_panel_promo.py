"""Promo kodlar bo'limi (/manage/promo-codes/) testlari.

Hisobot raqamlari komissiya to'lashga asos bo'ladi, shuning uchun ular alohida
tekshiriladi — noto'g'ri jamlanma bu yerda pul xatosi degani.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.models import (
	Payment, PromoCode, PromoRedemption, SubscriptionPlan, User, UserProfile,
)


class PanelPromoTests(TestCase):

	def setUp(self):
		self.admin = User.objects.create_user(username="admin", password="x", is_staff=True)
		self.client.force_login(self.admin)
		self.plan = SubscriptionPlan.objects.create(
			price_uzs=Decimal("100000"), price_usd=10,
			period=SubscriptionPlan.PeriodChoices.MONTHLY,
		)
		self.promo = PromoCode.objects.create(
			code="ALEX20", discount_percent=20, owner_label="Alex",
		)

	def _redeem(self, name, original, discount, final):
		user = User.objects.create_user(username=f"u{name}", password="x")
		profile = UserProfile.objects.create(user=user, name=name, telegram_id=hash(name) % 10**9)
		payment = Payment.objects.create(
			user=profile, plan=self.plan, amount=final, original_amount=original,
			promo_code=self.promo, status=Payment.PaymentStatus.COMPLETED,
		)
		return PromoRedemption.objects.create(
			promo_code=self.promo, user=profile, payment=payment,
			original_price=original, discount_amount_applied=discount, final_price=final,
		)

	# ── CRUD ───────────────────────────────────────────────────────────────
	def test_list_shows_redemption_count_and_revenue(self):
		self._redeem("A", Decimal("100000"), Decimal("20000"), Decimal("80000"))
		self._redeem("B", Decimal("300000"), Decimal("60000"), Decimal("240000"))

		html = self.client.get(reverse("panel:promo_codes")).content.decode()

		self.assertIn("ALEX20", html)
		self.assertIn("Alex", html)
		self.assertIn("20%", html)
		self.assertIn("320 000 UZS", html)   # 80 000 + 240 000

	def test_create_normalizes_the_code_and_records_the_author(self):
		response = self.client.post(reverse("panel:promo_code_add"), {
			"code": " new code 7 ", "discount_percent": 15,
			"owner_label": "Bek", "is_active": "on",
		})
		self.assertEqual(response.status_code, 302)
		promo = PromoCode.objects.get(code="NEWCODE7")
		self.assertEqual(promo.created_by, self.admin)

	def test_duplicate_code_in_a_different_case_is_rejected(self):
		"""Forma unikallikni normallashtirilgan qiymat bo'yicha tekshirsin —
		aks holda bu bazada IntegrityError bo'lardi."""
		response = self.client.post(reverse("panel:promo_code_add"), {
			"code": "alex20", "discount_percent": 10, "is_active": "on",
		})
		self.assertEqual(response.status_code, 200)   # forma xato bilan qayta chizildi
		self.assertEqual(PromoCode.objects.filter(code="ALEX20").count(), 1)

	def test_non_latin_lookalike_characters_are_rejected(self):
		"""Kirilcha "О" lotincha "O" ga o'xshaydi — kod yaratilishida to'siladi."""
		response = self.client.post(reverse("panel:promo_code_add"), {
			"code": "АLEX20", "discount_percent": 10, "is_active": "on",   # kirilcha А
		})
		self.assertEqual(response.status_code, 200)
		self.assertFalse(PromoCode.objects.filter(code="АLEX20").exists())

	# ── hisobot ────────────────────────────────────────────────────────────
	def test_report_totals(self):
		self._redeem("A", Decimal("100000"), Decimal("20000"), Decimal("80000"))
		self._redeem("B", Decimal("300000"), Decimal("60000"), Decimal("240000"))

		response = self.client.get(reverse("panel:promo_code_report", args=[self.promo.pk]))
		values = {t["label"]: t["value"] for t in response.context["totals"]}

		self.assertEqual(values["Redemptions"], 2)
		self.assertEqual(values["Revenue collected"], "320 000 UZS")
		self.assertEqual(values["Discount given"], "80 000 UZS")
		self.assertEqual(values["Gross before discount"], "400 000 UZS")

	def test_report_lists_each_redemption(self):
		self._redeem("Aziz", Decimal("100000"), Decimal("20000"), Decimal("80000"))
		html = self.client.get(
			reverse("panel:promo_code_report", args=[self.promo.pk])
		).content.decode()
		self.assertIn("Aziz", html)
		self.assertIn("1 oylik", html)

	def test_report_handles_a_code_with_no_redemptions(self):
		response = self.client.get(reverse("panel:promo_code_report", args=[self.promo.pk]))
		self.assertEqual(response.status_code, 200)
		values = {t["label"]: t["value"] for t in response.context["totals"]}
		self.assertEqual(values["Redemptions"], 0)
		self.assertEqual(values["Revenue collected"], "0 UZS")

	# ── CSV ────────────────────────────────────────────────────────────────
	def test_csv_export(self):
		self._redeem("Aziz", Decimal("100000"), Decimal("20000"), Decimal("80000"))

		response = self.client.get(reverse("panel:promo_code_export", args=[self.promo.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertIn("text/csv", response["Content-Type"])
		self.assertIn('filename="promo-ALEX20.csv"', response["Content-Disposition"])
		body = response.content.decode("utf-8")
		self.assertTrue(body.startswith("﻿"), "Excel uchun BOM kerak")
		self.assertIn("Aziz", body)
		self.assertIn("80000", body)

	# ── ruxsat ─────────────────────────────────────────────────────────────
	def test_non_staff_cannot_reach_the_section(self):
		user = User.objects.create_user(username="plain", password="x")
		UserProfile.objects.create(user=user, name="Plain")
		self.client.force_login(user)
		for name, args in (
			("panel:promo_codes", []),
			("panel:promo_code_report", [self.promo.pk]),
			("panel:promo_code_export", [self.promo.pk]),
		):
			with self.subTest(name=name):
				response = self.client.get(reverse(name, args=args))
				self.assertNotEqual(response.status_code, 200)
