from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView, View

from apps.models.payments import SubscriptionPlan, Payment


PREMIUM_BENEFITS = [
	"Uy va sport zali uchun individual mashg‘ulot dasturlari",
	"Har bir dastur ichidagi barcha 10 ta rejaga to‘liq kirish",
	"Har bir sport zali rejasida to‘liq 6 haftalik tizim",
	"Har bir uy mashg‘ulot rejasida to‘liq 4 haftalik tizim",
	"Marafon va challenge’larga bepul kirish",
	"Sevimlilar bo‘limida o‘z dasturingizni yaratish imkoniyati",
	"Mashg‘ulot statistikasi va tarixi",
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


class PaymentCreateView(LoginRequiredMixin, View):
	"""Creates a PENDING payment (no gateway yet) and shows success screen."""

	def post(self, request, plan_id):
		plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)
		currency = request.POST.get('currency', Payment.Currency.UZS)
		method = request.POST.get('method')
		if currency not in Payment.Currency.values:
			currency = Payment.Currency.UZS
		if method not in Payment.Method.values:
			method = None

		Payment.objects.create(
			user=request.user,
			plan=plan,
			amount=plan.price_for(currency),
			currency=currency,
			method=method,
			status=Payment.PaymentStatus.PENDING,
		)
		# Placeholder: no real gateway. Success screen shown.
		return redirect(reverse('payment_success'))


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
	template_name = 'payment/success.html'

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx['benefits'] = PREMIUM_BENEFITS
		return ctx