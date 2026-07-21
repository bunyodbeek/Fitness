import json
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, View

from apps.models import UserProfile
from apps.models.payments import SubscriptionPlan, Payment, PremiumGift
from apps.services import otp_guard
from apps.utils.telegram_webapp import parse_init_data
from apps.services.atmos import (
	ApplyError, AtmosClient, AtmosError, callback_response,
	classify_apply_error, validate_callback_signature,
)

logger = logging.getLogger(__name__)


# gettext_lazy — har bir so'rovda aktiv tilga qarab tarjima qilinadi (uz/ru/en).
PREMIUM_BENEFITS = [
	_("Individual workout programs for home and gym"),
	_("Full access to all 10 plans inside each program"),
	_("Complete 6-week system in every gym plan"),
	_("Complete 4-week system in every home workout plan"),
	_("Free access to marathons and challenges"),
	_("Create your own program in the Favorites section"),
	_("Workout statistics and history"),
]


class PremiumView(LoginRequiredMixin, TemplateView):
	"""Screen 5 — premium benefits / paywall."""
	template_name = 'payment/premium.html'

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx['benefits'] = PREMIUM_BENEFITS
		return ctx


class TariffSelectView(LoginRequiredMixin, TemplateView):
	"""Screen 6 — choose tariff + currency toggle."""
	template_name = 'payment/tariff_select.html'

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		plans = SubscriptionPlan.objects.filter(is_active=True).order_by('order')
		monthly = plans.filter(period='monthly').first()
		monthly_uzs = monthly.price_uzs if monthly else None
		monthly_usd = monthly.price_usd if monthly else None

		plan_list = []
		for p in plans:
			# discount % vs paying monthly for the same span
			disc_uzs = disc_usd = 0
			if monthly_uzs and p.months:
				full = monthly_uzs * p.months
				if full:
					disc_uzs = round((full - p.price_uzs) / full * 100)
			if monthly_usd and p.months:
				full = monthly_usd * p.months
				if full:
					disc_usd = round((full - p.price_usd) / full * 100)
			plan_list.append({
				'id': p.id,
				'period_display': p.get_period_display(),
				'months': p.months,
				'price_uzs': p.price_uzs,
				'price_usd': p.price_usd,
				'is_popular': p.is_popular,
				'discount_uzs': max(disc_uzs, 0),
				'discount_usd': max(disc_usd, 0),
			})
		ctx['plans'] = plan_list
		return ctx


def _payment_method_context(plan, currency, *, error='', card_number='', expiry='', method=None):
	"""Shared context for the payment-method screen. Reused by both the initial
	GET (TemplateView) and the in-place re-render when a card charge is rejected,
	so the error + the values the user already typed stay on the same page."""
	return {
		'plan': plan,
		'currency': currency,
		'amount': plan.price_for(currency),
		'card_methods': [
			('humo', 'Humo'),
			('uzcard', 'Uzcard'),
			('visa', 'Visa'),
			('mastercard', 'Mastercard'),
		],
		'error': error,
		'card_number': card_number,
		'expiry': expiry,
		'selected_method': method,
	}


class PaymentMethodView(LoginRequiredMixin, View):
	"""Legacy two-step route. Tariff + card are now one page — redirect so old
	links / bookmarks don't 404."""

	def get(self, request, plan_id):
		currency = request.GET.get('currency')
		url = reverse('tariff_select')
		if currency:
			url += f'?currency={currency}'
		return redirect(url)


def _normalize_expiry(raw: str) -> str:
	"""Accept 'MM/YY', 'MMYY' or 'YYMM' and return Atmos format 'YYMM'."""
	digits = ''.join(ch for ch in (raw or '') if ch.isdigit())
	if len(digits) != 4:
		return ''
	# If first two look like a month (01-12) it's MMYY → swap to YYMM.
	if 1 <= int(digits[:2]) <= 12 and int(digits[2:]) > 12:
		return digits[2:] + digits[:2]
	return digits


def _session_card_key(payment_id):
	return f'atmos_card_{payment_id}'


def _detect_scheme(card_number: str):
	"""Infer the card scheme from the PAN (the radio picker was removed).

	8600* → Uzcard, 9860* → Humo, 4* → Visa, 5*/2* → Mastercard. Returns a
	``Payment.Method`` value or ``None`` (kept for the payment record / history)."""
	n = card_number or ''
	if n.startswith('8600'):
		return Payment.Method.UZCARD
	if n.startswith('9860'):
		return Payment.Method.HUMO
	if n.startswith('4'):
		return Payment.Method.VISA
	if n[:1] in ('5', '2'):
		return Payment.Method.MASTERCARD
	return None


class PaymentCreateView(LoginRequiredMixin, View):
	"""Start an Atmos card charge: create the transaction, send the card to get
	an OTP, then hand the OTP screen URL to the frontend. Atmos is UZS-only, so
	the UZS price is always used regardless of the currency toggle.

	AJAX endpoint — always returns JSON. The frontend disables the button and
	shows a spinner on the first tap; the backend is made idempotent with a cache
	lock + a 60s "reuse the fresh transaction" window so a double-tap or retry can
	never make Atmos send two OTP codes."""

	def post(self, request, plan_id):
		plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)
		profile = request.user.profile

		# A gift buys Premium for a friend (one time only) instead of extending
		# the payer's own subscription.
		is_gift = request.POST.get('is_gift') == '1'
		if is_gift:
			existing_gift = PremiumGift.objects.filter(sender=profile).first()
			if existing_gift and existing_gift.is_used:
				return JsonResponse({
					'ok': False, 'error': 'already_gifted',
					'message': _("You have already sent a Premium gift."),
				}, status=409)

		currency = request.POST.get('currency', Payment.Currency.UZS)
		if currency not in Payment.Currency.values:
			currency = Payment.Currency.UZS

		raw_card = request.POST.get('card_number') or ''
		raw_expiry = request.POST.get('expiry') or ''
		card_number = ''.join(ch for ch in raw_card if ch.isdigit())
		expiry = _normalize_expiry(raw_expiry)

		# Scheme is derived from the PAN (no radio picker); kept on the Payment record.
		method = _detect_scheme(card_number)

		if len(card_number) < 16 or not expiry:
			return JsonResponse({
				'ok': False, 'error': 'invalid_card',
				'message': _("Enter a valid card number and expiry date."),
			}, status=400)

		def otp_url(pid):
			return reverse('payment_otp', args=[pid])

		def recent_processing():
			"""A fresh, still-usable transaction for this user+plan (last 60s)."""
			cutoff = timezone.now() - timedelta(seconds=otp_guard.IDEMPOTENT_WINDOW)
			return (
				Payment.objects
				.filter(
					user=profile, plan=plan, is_gift=is_gift,
					status=Payment.PaymentStatus.PROCESSING,
					atmos_transaction_id__isnull=False,
					created_at__gte=cutoff,
				)
				.order_by('-created_at')
				.first()
			)

		# ── rate limit: max SEND_MAX OTP sends per window ──
		allowed, retry_after = otp_guard.send_rate_status(profile.id)
		if not allowed:
			return JsonResponse({
				'ok': False, 'error': 'too_many_requests', 'retry_after': retry_after,
				'message': _("Too many requests. Please try again later."),
			}, status=429)

		# ── in-flight lock: another send is already talking to Atmos ──
		if not otp_guard.acquire_send_lock(profile.id):
			existing = recent_processing()
			if existing:
				return JsonResponse({'ok': True, 'otp_url': otp_url(existing.id)})
			return JsonResponse({
				'ok': False, 'error': 'in_progress',
				'message': _("A request is already being processed. Please wait."),
			}, status=409)

		try:
			# ── idempotency: reuse the OTP we just sent instead of a new code ──
			existing = recent_processing()
			if existing:
				return JsonResponse({'ok': True, 'otp_url': otp_url(existing.id)})

			payment = Payment.objects.create(
				user=profile,
				plan=plan,
				amount=plan.price_uzs,
				currency=Payment.Currency.UZS,
				method=method,
				status=Payment.PaymentStatus.PENDING,
				is_gift=is_gift,
			)

			# Attach (or reuse) this sender's single gift row and point it at the
			# current payment attempt. It becomes AVAILABLE on payment success.
			if is_gift:
				gift, _created = PremiumGift.objects.get_or_create(
					sender=profile,
					defaults={'code': PremiumGift.generate_code(), 'plan': plan},
				)
				if gift.status != PremiumGift.Status.CLAIMED:
					gift.plan = plan
					gift.payment = payment
					gift.status = PremiumGift.Status.PENDING
					gift.save(update_fields=['plan', 'payment', 'status'])

			client = AtmosClient()
			try:
				# amount is sent in tiyin (1 UZS = 100 tiyin)
				tx_id = client.create_transaction(
					amount_tiyin=int((payment.amount * 100).to_integral_value()),
					account=str(payment.id),
				)
				payment.atmos_transaction_id = tx_id
				payment.status = Payment.PaymentStatus.PROCESSING
				payment.save(update_fields=['atmos_transaction_id', 'status'])
				client.pre_apply(tx_id, card_number=card_number, expiry=expiry)
			except AtmosError as exc:
				logger.warning("Atmos start failed for payment %s: %s", payment.id, exc)
				payment.mark_as_failed()
				return JsonResponse({
					'ok': False, 'error': 'atmos',
					'message': _("Payment could not be started: %(err)s") % {"err": exc.message},
				}, status=502)

			# Keep the card in the SERVER-SIDE session so "resend" can re-trigger the
			# OTP without asking for the card again. Cleared on success / lockout.
			request.session[_session_card_key(payment.id)] = {
				'card': card_number, 'expiry': expiry,
			}
			otp_guard.record_send(profile.id)
			return JsonResponse({
				'ok': True, 'otp_url': otp_url(payment.id),
				'otp_ttl': otp_guard.OTP_TTL_SECONDS,
			})
		finally:
			otp_guard.release_send_lock(profile.id)


class PaymentOtpView(LoginRequiredMixin, View):
	"""Render the OTP screen (GET) and confirm the Atmos transaction (POST/AJAX)."""
	template_name = 'payment/otp.html'

	def get_payment(self, request, payment_id):
		return get_object_or_404(
			Payment, pk=payment_id, user=request.user.profile,
			status=Payment.PaymentStatus.PROCESSING,
		)

	def get(self, request, payment_id):
		payment = self.get_payment(request, payment_id)
		return render(request, self.template_name, {
			'payment': payment,
			'otp_ttl': otp_guard.OTP_TTL_SECONDS,
			'resend_after': 60,
		})

	def post(self, request, payment_id):
		payment = self.get_payment(request, payment_id)
		profile = request.user.profile

		# ── verification lockout (too many wrong codes earlier) ──
		blocked, retry_after = otp_guard.verify_block_status(profile.id)
		if blocked:
			return JsonResponse({
				'ok': False, 'error': 'locked', 'retry_after': retry_after,
				'restart_url': reverse('tariff_select'),
				'message': _("Too many attempts. Please try again later."),
			}, status=429)

		otp = ''.join(ch for ch in (request.POST.get('otp') or '') if ch.isdigit())
		if not otp:
			return JsonResponse({
				'ok': False, 'error': 'empty_otp',
				'message': _("Enter the SMS code."),
			}, status=400)

		client = AtmosClient()
		try:
			client.apply(payment.atmos_transaction_id, otp=otp)
		except AtmosError as exc:
			# A code-less error is a transient network/parse failure — don't burn an
			# attempt for that.
			if exc.code is None:
				logger.warning("Atmos apply transient error for payment %s: %s", payment.id, exc)
				return JsonResponse({
					'ok': False, 'error': 'atmos',
					'message': _("Confirmation failed: %(err)s") % {"err": exc.message},
				}, status=502)

			kind = classify_apply_error(exc.code, exc.message)

			# ── Only a genuinely WRONG OTP consumes an attempt / triggers lockout. ──
			if kind == ApplyError.WRONG_OTP:
				attempts, remaining, locked = otp_guard.record_wrong_attempt(profile.id, payment.id)
				logger.warning(
					"Atmos apply wrong OTP for payment %s (attempt %s): %s",
					payment.id, attempts, exc,
				)
				if locked:
					payment.mark_as_failed()
					request.session.pop(_session_card_key(payment.id), None)
					return JsonResponse({
						'ok': False, 'error': 'too_many_attempts',
						'retry_after': otp_guard.VERIFY_BLOCK,
						'restart_url': reverse('tariff_select'),
						'message': _("Too many attempts. Please request a new code later."),
					}, status=429)
				return JsonResponse({
					'ok': False, 'error': 'wrong_otp', 'remaining': remaining,
					'message': _("Wrong code. %(n)s attempt(s) left.") % {"n": remaining},
				}, status=400)

			# ── Non-OTP rejections: the code was fine, so DON'T touch the attempt
			#    counter and keep the transaction alive so the user can retry. Log the
			#    real Atmos detail; return a localized, error-specific message. ──
			logger.warning(
				"Atmos apply rejected (%s) for payment %s: code=%s msg=%s",
				kind, payment.id, exc.code, exc.message,
			)
			if kind == ApplyError.INSUFFICIENT_FUNDS:
				return JsonResponse({
					'ok': False, 'error': 'insufficient_funds',
					'message': _("Insufficient funds on the card"),
				}, status=400)
			if kind == ApplyError.OTP_EXPIRED:
				return JsonResponse({
					'ok': False, 'error': 'otp_expired',
					'message': _("The code has expired. Please request a new one."),
				}, status=400)
			if kind == ApplyError.CARD_ERROR:
				return JsonResponse({
					'ok': False, 'error': 'card_error',
					'message': _("There was a problem with the card. Please try another card."),
				}, status=400)
			return JsonResponse({
				'ok': False, 'error': 'payment_failed',
				'message': _("Payment failed. Please try again."),
			}, status=400)

		# Apply confirms synchronously; the callback is the async backstop, so guard
		# against double-activation.
		if payment.status != Payment.PaymentStatus.COMPLETED:
			payment.mark_as_completed()
		otp_guard.reset_verify_attempts(profile.id, payment.id)
		request.session.pop(_session_card_key(payment.id), None)
		redirect_name = 'gift_share' if payment.is_gift else 'payment_success'
		return JsonResponse({'ok': True, 'redirect': reverse(redirect_name)})


class PaymentOtpResendView(LoginRequiredMixin, View):
	"""Re-trigger the Atmos OTP SMS for an in-flight transaction. Respects the
	same send rate limit as the initial request."""

	def post(self, request, payment_id):
		payment = get_object_or_404(
			Payment, pk=payment_id, user=request.user.profile,
			status=Payment.PaymentStatus.PROCESSING,
		)
		profile = request.user.profile

		card = request.session.get(_session_card_key(payment.id))
		if not card:
			return JsonResponse({
				'ok': False, 'error': 'restart_required',
				'restart_url': reverse('tariff_select'),
				'message': _("Session expired. Please start the payment again."),
			}, status=409)

		allowed, retry_after = otp_guard.send_rate_status(profile.id)
		if not allowed:
			return JsonResponse({
				'ok': False, 'error': 'too_many_requests', 'retry_after': retry_after,
				'message': _("Too many requests. Please try again later."),
			}, status=429)

		if not otp_guard.acquire_send_lock(profile.id):
			return JsonResponse({
				'ok': False, 'error': 'in_progress',
				'message': _("A request is already being processed. Please wait."),
			}, status=409)

		try:
			client = AtmosClient()
			try:
				client.pre_apply(
					payment.atmos_transaction_id,
					card_number=card['card'], expiry=card['expiry'],
				)
			except AtmosError as exc:
				logger.warning("Atmos resend failed for payment %s: %s", payment.id, exc)
				return JsonResponse({
					'ok': False, 'error': 'atmos',
					'message': _("Could not resend the code: %(err)s") % {"err": exc.message},
				}, status=502)

			otp_guard.record_send(profile.id)
			return JsonResponse({
				'ok': True, 'retry_after': 60, 'otp_ttl': otp_guard.OTP_TTL_SECONDS,
			})
		finally:
			otp_guard.release_send_lock(profile.id)


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
	template_name = 'payment/success.html'

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx['benefits'] = PREMIUM_BENEFITS
		return ctx


# ── Premium gifting ──────────────────────────────────────────────────────────

class GiftPremiumView(LoginRequiredMixin, View):
	"""Entry point (from the profile page) to gift Premium to a friend.

	The sender picks any of the active subscription plans (1/3/6/12 months) —
	the chosen plan is what the recipient receives on claim.

	If the user has already used their one-time gift, they are sent to the share
	page instead of the purchase form."""
	template_name = 'payment/gift_purchase.html'

	def get(self, request):
		profile = request.user.profile
		gift = PremiumGift.objects.filter(sender=profile).first()
		if gift and gift.is_used:
			return redirect('gift_share')

		# Same plan list + discount maths as the normal tariff screen so the
		# gift sender can choose any package, not just the monthly one.
		plans = SubscriptionPlan.objects.filter(is_active=True).order_by('order')
		monthly = plans.filter(period='monthly').first()
		monthly_uzs = monthly.price_uzs if monthly else None
		monthly_usd = monthly.price_usd if monthly else None

		plan_list = []
		for p in plans:
			disc_uzs = disc_usd = 0
			if monthly_uzs and p.months:
				full = monthly_uzs * p.months
				if full:
					disc_uzs = round((full - p.price_uzs) / full * 100)
			if monthly_usd and p.months:
				full = monthly_usd * p.months
				if full:
					disc_usd = round((full - p.price_usd) / full * 100)
			plan_list.append({
				'id': p.id,
				'period_display': p.get_period_display(),
				'months': p.months,
				'price_uzs': p.price_uzs,
				'price_usd': p.price_usd,
				'is_popular': p.is_popular,
				'discount_uzs': max(disc_uzs, 0),
				'discount_usd': max(disc_usd, 0),
			})
		return render(request, self.template_name, {'plans': plan_list})


class GiftShareView(LoginRequiredMixin, TemplateView):
	"""Shows the sender their shareable gift link and its current status."""
	template_name = 'payment/gift_share.html'

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		profile = self.request.user.profile
		gift = PremiumGift.objects.filter(sender=profile).select_related('recipient').first()
		# Only a paid (available/claimed) gift has a usable link.
		ctx['gift'] = gift if (gift and gift.is_used) else None
		ctx['share_link'] = ctx['gift'].share_link if ctx['gift'] else ''
		return ctx


@method_decorator(csrf_exempt, name='dispatch')
class GiftClaimView(View):
	"""Recipient-facing claim page opened from the shared Telegram link.

	Not LoginRequired: the recipient is identified from the signed Telegram
	``initData`` (same trust model as onboarding), so a friend who is not logged
	into a browser session can still claim inside the Telegram mini app."""
	template_name = 'payment/gift_claim.html'

	def get(self, request, code):
		gift = (
			PremiumGift.objects
			.filter(code=code)
			.select_related('sender', 'plan')
			.first()
		)
		return render(request, self.template_name, {'gift': gift, 'code': code})

	def post(self, request, code):
		verified = parse_init_data(request.POST.get('init_data') or '')
		if not verified:
			return JsonResponse({
				'ok': False, 'error': 'auth',
				'message': _("Could not verify your Telegram account. Please reopen the link."),
			}, status=400)

		recipient = UserProfile.objects.filter(telegram_id=verified['telegram_id']).first()
		if recipient is None:
			from apps.utils.telegram_bot_link import get_bot_deeplink
			return JsonResponse({
				'ok': False, 'error': 'no_profile', 'redirect': get_bot_deeplink(),
				'message': _("Open the app and finish setup first, then claim your gift."),
			}, status=403)

		with transaction.atomic():
			gift = PremiumGift.objects.select_for_update().filter(code=code).first()
			if gift is None:
				return JsonResponse({
					'ok': False, 'error': 'not_found',
					'message': _("This gift link is invalid."),
				}, status=404)
			ok, err = gift.claim(recipient)

		if not ok:
			messages_map = {
				'unavailable': _("This gift has already been claimed or is not available."),
				'self': _("You can't claim your own gift."),
			}
			return JsonResponse({
				'ok': False, 'error': err,
				'message': messages_map.get(err, _("This gift is not available.")),
			}, status=409)

		return JsonResponse({
			'ok': True,
			'message': _("Premium activated! Enjoy your gift."),
		})


@method_decorator(csrf_exempt, name='dispatch')
class AtmosCallbackView(View):
	"""
	Result/callback endpoint Atmos POSTs to after a transaction is confirmed.

	Atmos sends a JSON body with store_id, transaction_id, transaction_time,
	amount (in tiyin), invoice (= our Payment.id) and an md5 `sign`. We verify
	the signature, mark the matching Payment as completed and answer with the
	JSON shape Atmos expects: {"status": 1|0, "message": "..."}.
	"""

	def post(self, request, *args, **kwargs):
		try:
			data = json.loads(request.body.decode() or '{}')
		except (ValueError, UnicodeDecodeError):
			logger.warning("Atmos callback: invalid JSON body")
			return JsonResponse(callback_response(False, "Invalid payload"), status=400)
		logger.warning("ATMOS RAW: %s | CT: %s", request.body.decode(errors='replace'), request.content_type)
		if not validate_callback_signature(data, settings.ATMOS_API_KEY):
			logger.warning("Atmos callback: invalid signature for %s", data.get('invoice'))
			return JsonResponse(callback_response(False, "Invalid signature"), status=400)

		invoice = data.get('account')
		payment = Payment.objects.filter(pk=invoice).first()
		if payment is None:
			logger.warning("Atmos callback: payment %s not found", invoice)
			return JsonResponse(callback_response(False, "Payment not found"), status=404)

		# Amount comes in tiyin; our Payment.amount is stored in UZS.
		try:
			expected_tiyin = int((payment.amount * 100).to_integral_value())
			received_tiyin = int(Decimal(str(data['amount'])))
		except (ArithmeticError, ValueError, TypeError):
			logger.warning("Atmos callback: bad amount for payment %s", invoice)
			return JsonResponse(callback_response(False, "Invalid amount"), status=400)

		if received_tiyin != expected_tiyin:
			logger.warning(
				"Atmos callback: amount mismatch for payment %s (got %s, expected %s)",
				invoice, received_tiyin, expected_tiyin,
			)
			return JsonResponse(callback_response(False, "Amount mismatch"), status=400)

		# Idempotent: a repeated callback for an already-completed payment is OK.
		if payment.status != Payment.PaymentStatus.COMPLETED:
			payment.payme_id = str(data.get('transaction_id', '')) or payment.payme_id
			payment.mark_as_completed()

		logger.info("Atmos callback: payment %s completed", invoice)
		return JsonResponse(callback_response(True, "Payment accepted"))
