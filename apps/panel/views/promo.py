"""Promo kodlar bo'limi — CRUD + trener bo'yicha sotuv hisoboti.

Hisobot komissiya hisoblash uchun: har bir kod bo'yicha kim, qachon, qaysi
tarifni va qancha to'lab olgani. Jamlanmalar `PromoRedemption` dan olinadi —
ya'ni faqat HAQIQATDA to'langan xaridlar (qator to'lov o'tgandagina yaratiladi).
"""
import csv

from django.db.models import Count, Sum
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from apps.models.promo import PromoCode, PromoRedemption
from apps.panel.forms import PromoCodeForm
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin
from apps.panel.views.crud import (
	PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView,
)


def _uzs(amount) -> str:
	return f"{int(amount or 0):,}".replace(",", " ") + " UZS"


class PromoCodeListView(PanelListView):
	model = PromoCode
	nav_active = "promo_codes"
	page_title = _("Promo codes")
	columns = [
		_("Code"), _("Owner"), _("Discount"), _("Redemptions"),
		_("Revenue"), _("Status"), _("Created"),
	]
	search_fields = ["code", "owner_label"]
	create_url_name = "panel:promo_code_add"
	edit_url_name = "panel:promo_code_edit"
	delete_url_name = "panel:promo_code_delete"
	open_url_name = "panel:promo_code_report"
	create_label = _("Add promo code")

	def get_queryset(self):
		# Jamlanmalar bitta so'rovda — har bir qator uchun alohida COUNT/SUM
		# qilmaslik uchun (ro'yxat kattalashganda sezilarli farq).
		return (
			super().get_queryset()
			.annotate(
				used_count=Count("redemptions", distinct=True),
				revenue=Sum("redemptions__final_price"),
			)
			.order_by("-created_at")
		)

	def get_row_cells(self, obj):
		if not obj.is_active:
			status = format_html('<span class="badge badge-red">{}</span>', _("Inactive"))
		elif obj.is_expired:
			status = format_html('<span class="badge badge-red">{}</span>', _("Expired"))
		elif obj.max_redemptions and obj.used_count >= obj.max_redemptions:
			status = format_html('<span class="badge badge-red">{}</span>', _("Limit reached"))
		else:
			status = format_html('<span class="badge badge-green">{}</span>', _("Active"))

		used = str(obj.used_count)
		if obj.max_redemptions:
			used = f"{obj.used_count} / {obj.max_redemptions}"

		return [
			format_html("<strong>{}</strong>", obj.code),
			obj.owner_label or "—",
			f"{obj.discount_percent}%",
			used,
			_uzs(obj.revenue),
			status,
			obj.created_at.strftime("%d.%m.%Y"),
		]


class PromoCodeCreateView(PanelCreateView):
	model = PromoCode
	form_class = PromoCodeForm
	nav_active = "promo_codes"
	page_title = _("Add promo code")
	success_url = reverse_lazy("panel:promo_codes")
	success_message = _("Promo code created.")

	def form_valid(self, form):
		form.instance.created_by = self.request.user
		return super().form_valid(form)


class PromoCodeUpdateView(PanelUpdateView):
	model = PromoCode
	form_class = PromoCodeForm
	nav_active = "promo_codes"
	page_title = _("Edit promo code")
	success_url = reverse_lazy("panel:promo_codes")


class PromoCodeDeleteView(PanelDeleteView):
	model = PromoCode
	nav_active = "promo_codes"
	page_title = _("Delete promo code")
	success_url = reverse_lazy("panel:promo_codes")


def _redemptions_for(promo):
	return (
		PromoRedemption.objects
		.filter(promo_code=promo)
		.select_related("user", "payment", "payment__plan")
		.order_by("-redeemed_at")
	)


class PromoCodeReportView(StaffRequiredMixin, PanelContextMixin, DetailView):
	"""Bitta kod bo'yicha batafsil hisobot — komissiya shu yerdan hisoblanadi."""
	model = PromoCode
	template_name = "panel/promo_report.html"
	context_object_name = "promo"
	nav_active = "promo_codes"

	def get_page_title(self):
		return _("Promo code: %(code)s") % {"code": self.object.code}

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		redemptions = list(_redemptions_for(self.object))

		gross = sum((r.original_price for r in redemptions), 0)
		discount = sum((r.discount_amount_applied for r in redemptions), 0)
		net = sum((r.final_price for r in redemptions), 0)

		ctx["redemptions"] = redemptions
		ctx["totals"] = [
			{"label": _("Redemptions"), "value": len(redemptions)},
			# Komissiya odatda HAQIQATDA tushgan puldan hisoblanadi, shuning
			# uchun "Revenue" — chegirmadan keyingi summa.
			{"label": _("Revenue collected"), "value": _uzs(net)},
			{"label": _("Discount given"), "value": _uzs(discount)},
			{"label": _("Gross before discount"), "value": _uzs(gross)},
		]
		ctx["export_url"] = reverse("panel:promo_code_export", args=[self.object.pk])
		ctx["back_url"] = reverse("panel:promo_codes")
		return ctx


class PromoCodeExportView(StaffRequiredMixin, DetailView):
	"""Hisobotning CSV varianti."""
	model = PromoCode

	def render_to_response(self, context, **response_kwargs):
		promo = self.object
		response = HttpResponse(content_type="text/csv; charset=utf-8")
		response["Content-Disposition"] = f'attachment; filename="promo-{promo.code}.csv"'
		# Excel UTF-8 ni BOM'siz noto'g'ri o'qiydi (kirill/o'zbek harflari buziladi).
		response.write("﻿")

		writer = csv.writer(response)
		writer.writerow(["Date", "User", "Telegram ID", "Plan", "Original", "Discount", "Paid"])
		for r in _redemptions_for(promo):
			plan = r.payment.plan if r.payment_id and r.payment.plan_id else None
			writer.writerow([
				r.redeemed_at.strftime("%Y-%m-%d %H:%M"),
				r.user.name if r.user_id else "",
				r.user.telegram_id if r.user_id else "",
				plan.get_period_display() if plan else "",
				r.original_price,
				r.discount_amount_applied,
				r.final_price,
			])
		return response
