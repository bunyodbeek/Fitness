"""7 kunlik paywall gate testlari (apps/middleware.py: PaywallGateMiddleware).

Gate BITTA joyda — middleware'da — hal qilinadi, shuning uchun testlar ham
HTTP qatlamidan tekshiradi: sinov muddati o'tgan foydalanuvchi uchun har qanday
tab yopiq, to'lov zanjiri esa ochiq bo'lishi shart.

Eng muhim test — `test_premium_user_is_never_gated`: `Subscription` modeli
ilova yuklanganda ro'yxatdan o'tmasa `is_premium` jimgina False qaytaradi va
pul to'lagan foydalanuvchi ilovadan qulflanadi (apps/models/__init__.py dagi
izohga qarang).
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.models import (
	Subscription, SubscriptionPlan, User, UserProfile,
)


class PaywallGateTests(TestCase):

	@classmethod
	def setUpTestData(cls):
		cls.plan = SubscriptionPlan.objects.create(
			price_uzs=100000, price_usd=10, period=SubscriptionPlan.PeriodChoices.MONTHLY,
		)

	def _make_user(self, *, days_ago, is_staff=False):
		"""Sinovi ``days_ago`` kun oldin boshlangan foydalanuvchi."""
		user = User.objects.create_user(
			username=f"telegram_{days_ago}_{is_staff}_{timezone.now().timestamp()}",
			password="x", is_staff=is_staff,
		)
		profile = UserProfile.objects.create(user=user, name="Tester")
		UserProfile.objects.filter(pk=profile.pk).update(
			trial_started_at=timezone.now() - timedelta(days=days_ago),
		)
		profile.refresh_from_db()
		return user, profile

	def _login(self, user):
		self.client.force_login(user)

	# ── sinov ichida ───────────────────────────────────────────────────────
	def test_user_inside_trial_reaches_the_app(self):
		user, profile = self._make_user(days_ago=3)
		self.assertTrue(profile.is_in_trial)
		self.assertTrue(profile.has_app_access)
		self._login(user)
		self.assertEqual(self.client.get("/en/workout/").status_code, 200)

	def test_trial_boundary_is_exactly_seven_days(self):
		_, inside = self._make_user(days_ago=6)
		_, outside = self._make_user(days_ago=7)
		self.assertTrue(inside.is_in_trial)
		self.assertFalse(outside.is_in_trial)

	# ── sinov tugagan ──────────────────────────────────────────────────────
	def test_expired_trial_is_redirected_to_the_gate(self):
		user, profile = self._make_user(days_ago=8)
		self.assertFalse(profile.has_app_access)
		self._login(user)
		gate = reverse("paywall_gate")
		for path in (
			"/en/workout/", "/en/exercises/", "/en/users/profile/",
			"/en/handbook/", "/en/favorites/", "/en/users/settings/",
			"/en/gym/programs/", "/en/user/progress/",
		):
			with self.subTest(path=path):
				response = self.client.get(path)
				self.assertEqual(response.status_code, 302, path)
				self.assertEqual(response["Location"], gate, path)

	def test_payment_chain_stays_open_while_gated(self):
		user, _ = self._make_user(days_ago=8)
		self._login(user)
		for path in ("/en/premium/required/", "/en/premium/tariffs/", "/en/premium/"):
			with self.subTest(path=path):
				self.assertEqual(self.client.get(path).status_code, 200, path)

	def test_intro_and_onboarding_stay_open_while_gated(self):
		user, _ = self._make_user(days_ago=8)
		self._login(user)
		# Gate ANIQ intro'dan keyin chiqadi — intro o'zi bloklanmaydi.
		self.assertEqual(self.client.get("/en/").status_code, 200)

	def test_gate_page_has_no_way_back(self):
		user, _ = self._make_user(days_ago=8)
		self._login(user)
		html = self.client.get(reverse("paywall_gate")).content
		# Faqat MARKUP tekshiriladi — `.close-btn` CSS qoidasi shablonda qoladi.
		self.assertNotIn(b'<button class="close-btn"', html)
		self.assertNotIn(b">Later<", html)
		self.assertIn(b'class="gate-note"', html)

	def test_fragment_request_gets_a_hard_redirect_script(self):
		"""Tab router `fetch` i redirect'ga ergashib gate sahifasini tab ichiga
		joylab qo'ymasligi kerak — o'rniga to'liq sahifa yuklashga o'tadi."""
		user, _ = self._make_user(days_ago=8)
		self._login(user)
		response = self.client.get(
			"/en/workout/?partial=1", headers={"x-requested-with": "XMLHttpRequest"},
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn(b"location.replace", response.content)
		self.assertIn(reverse("paywall_gate").encode(), response.content)
		self.assertEqual(response["Cache-Control"], "no-store")

	def test_write_requests_are_rejected_with_403(self):
		"""Yozuv amallariga redirect emas, 403 — klient uni tushunarli xato
		sifatida ko'rsatadi va jimgina HTML redirect'ni yutmaydi."""
		user, _ = self._make_user(days_ago=8)
		self._login(user)
		response = self.client.post(
			"/en/api/programs/custom/create/", data="{}", content_type="application/json",
		)
		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json()["error"], "subscription_required")

	# ── obuna / premium ────────────────────────────────────────────────────
	def test_premium_user_is_never_gated(self):
		user, profile = self._make_user(days_ago=400)
		Subscription.objects.create(user=profile, plan=self.plan)
		profile.refresh_from_db()
		self.assertTrue(profile.is_premium)
		self.assertTrue(profile.has_app_access)
		self._login(user)
		self.assertEqual(self.client.get("/en/workout/").status_code, 200)

	def test_expired_subscription_falls_back_into_the_gate(self):
		"""To'lagan, keyin muddati tugagan foydalanuvchi sinovga QAYTMAYDI."""
		user, profile = self._make_user(days_ago=400)
		sub = Subscription.objects.create(user=profile, plan=self.plan)
		Subscription.objects.filter(pk=sub.pk).update(
			end_date=timezone.now() - timedelta(days=1),
		)
		profile.refresh_from_db()
		self.assertFalse(profile.has_app_access)
		self._login(user)
		self.assertEqual(self.client.get("/en/workout/")["Location"], reverse("paywall_gate"))

	def test_gate_page_redirects_users_who_still_have_access(self):
		"""To'lab bo'lgan odam gate sahifasida qolib ketmasligi kerak."""
		user, _ = self._make_user(days_ago=1)
		self._login(user)
		response = self.client.get(reverse("paywall_gate"))
		self.assertEqual(response.status_code, 302)

	# ── istisnolar ─────────────────────────────────────────────────────────
	def test_staff_are_never_gated(self):
		user, _ = self._make_user(days_ago=400, is_staff=True)
		self._login(user)
		self.assertEqual(self.client.get("/en/workout/").status_code, 200)

	def test_anonymous_requests_are_left_alone(self):
		"""Gate anonim foydalanuvchini ushlamaydi — u avval autentifikatsiyaga
		boradi, aks holda kirish oqimi buzilardi."""
		response = self.client.get("/en/workout/")
		self.assertNotEqual(response.get("Location"), reverse("paywall_gate"))

	def test_atmos_callback_is_never_gated(self):
		"""To'lov tasdig'i gate ortida qolsa, to'lov hech qachon yakunlanmaydi."""
		response = self.client.post(
			"/payments/atmos/callback/", data="{}", content_type="application/json",
		)
		self.assertNotEqual(response.status_code, 403)


class TrialAnchorTests(TestCase):

	def test_anchor_is_written_once_and_never_moves(self):
		user = User.objects.create_user(username="anchor", password="x")
		profile = UserProfile.objects.create(user=user, name="A")
		first = profile.trial_started_at
		self.assertIsNotNone(first)

		profile.name = "B"
		profile.save()
		profile.refresh_from_db()
		self.assertEqual(profile.trial_started_at, first)

		# `update_fields` bilan saqlash ham anchor'ni surib yubormaydi.
		profile.name = "C"
		profile.save(update_fields=["name"])
		profile.refresh_from_db()
		self.assertEqual(profile.trial_started_at, first)

	def test_anchor_comes_from_date_joined(self):
		"""Profil o'chib qayta yaratilsa ham sinov qaytadan boshlanmaydi."""
		joined = timezone.now() - timedelta(days=30)
		user = User.objects.create_user(username="rejoin", password="x")
		User.objects.filter(pk=user.pk).update(date_joined=joined)
		user.refresh_from_db()

		profile = UserProfile.objects.create(user=user, name="R")
		self.assertEqual(profile.trial_started_at, joined)
		self.assertFalse(profile.is_in_trial)
