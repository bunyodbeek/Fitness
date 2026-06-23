import json
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, View

from apps.models.payments import SubscriptionPlan, Payment
from apps.services.atmos import AtmosClient, AtmosError, callback_response, validate_callback_signature

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


class PaymentMethodView(LoginRequiredMixin, TemplateView):
	"""Screen 7 — choose payment method (cards only for now)."""
	template_name = 'payment/payment_method.html'

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		plan = get_object_or_404(SubscriptionPlan, pk=kwargs['plan_id'], is_active=True)
		currency = self.request.GET.get('currency', Payment.Currency.UZS)
		if currency not in Payment.Currency.values:
			currency = Payment.Currency.UZS
		ctx['plan'] = plan
		ctx['currency'] = currency
		ctx['amount'] = plan.price_for(currency)
		ctx['card_methods'] = [
			('humo', 'Humo'),
			('uzcard', 'Uzcard'),
			('visa', 'Visa'),
			('mastercard', 'Mastercard'),
		]
		return ctx


def _normalize_expiry(raw: str) -> str:
	"""Accept 'MM/YY', 'MMYY' or 'YYMM' and return Atmos format 'YYMM'."""
	digits = ''.join(ch for ch in (raw or '') if ch.isdigit())
	if len(digits) != 4:
		return ''
	# If first two look like a month (01-12) it's MMYY → swap to YYMM.
	if 1 <= int(digits[:2]) <= 12 and int(digits[2:]) > 12:
		return digits[2:] + digits[:2]
	return digits


class PaymentCreateView(LoginRequiredMixin, View):
	"""Start an Atmos card charge: create the transaction, send the card to get
	an OTP, then move the user to the OTP screen. Atmos is UZS-only, so the UZS
	price is always used regardless of the currency toggle."""

	def post(self, request, plan_id):
		plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)
		method = request.POST.get('method')
		if method not in Payment.Method.values:
			method = None

		card_number = ''.join(ch for ch in (request.POST.get('card_number') or '') if ch.isdigit())
		expiry = _normalize_expiry(request.POST.get('expiry'))
		if len(card_number) < 16 or not expiry:
			messages.error(request, _("Enter a valid card number and expiry date."))
			return redirect(reverse('payment_method', args=[plan.id]))

		payment = Payment.objects.create(
			user=request.user.profile,
			plan=plan,
			amount=plan.price_uzs,
			currency=Payment.Currency.UZS,
			method=method,
			status=Payment.PaymentStatus.PENDING,
		)

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
			messages.error(request, _("Payment could not be started: %(err)s") % {"err": exc.message})
			return redirect(reverse('payment_method', args=[plan.id]))

		return redirect(reverse('payment_otp', args=[payment.id]))


class PaymentOtpView(LoginRequiredMixin, View):
	"""Collect the SMS OTP and confirm the Atmos transaction."""
	template_name = 'payment/otp.html'

	def get_payment(self, request, payment_id):
		return get_object_or_404(
			Payment, pk=payment_id, user=request.user.profile,
			status=Payment.PaymentStatus.PROCESSING,
		)

	def get(self, request, payment_id):
		payment = self.get_payment(request, payment_id)
		return render(request, self.template_name, {'payment': payment})

	def post(self, request, payment_id):
		payment = self.get_payment(request, payment_id)
		otp = ''.join(ch for ch in (request.POST.get('otp') or '') if ch.isdigit())
		if not otp:
			messages.error(request, _("Enter the SMS code."))
			return render(request, self.template_name, {'payment': payment})

		client = AtmosClient()
		try:
			client.apply(payment.atmos_transaction_id, otp=otp)
		except AtmosError as exc:
			logger.warning("Atmos apply failed for payment %s: %s", payment.id, exc)
			messages.error(request, _("Confirmation failed: %(err)s") % {"err": exc.message})
			return render(request, self.template_name, {'payment': payment})

		# Apply confirms synchronously; the callback is the async backstop, so guard
		# against double-activation.
		if payment.status != Payment.PaymentStatus.COMPLETED:
			payment.mark_as_completed()
		return redirect(reverse('payment_success'))


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
	template_name = 'payment/success.html'

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx['benefits'] = PREMIUM_BENEFITS
		return ctx


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

		if not validate_callback_signature(data, settings.ATMOS_API_KEY):
			logger.warning("Atmos callback: invalid signature for %s", data.get('invoice'))
			return JsonResponse(callback_response(False, "Invalid signature"), status=400)

		invoice = data.get('invoice')
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