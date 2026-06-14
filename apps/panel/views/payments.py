"""Payments section — list of payments (read-only detail)."""
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from apps.models.payments import Payment
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin
from apps.panel.views.crud import PanelListView

_STATUS_BADGE = {
    Payment.PaymentStatus.COMPLETED: "badge-green",
    Payment.PaymentStatus.PENDING: "badge-free",
    Payment.PaymentStatus.PROCESSING: "badge-free",
    Payment.PaymentStatus.FAILED: "badge-red",
}


class PaymentListView(PanelListView):
    model = Payment
    nav_active = "payments"
    page_title = _("Payments")
    columns = [_("User"), _("Amount"), _("Method"), _("Status"), _("Date")]
    search_fields = ["user__name"]
    open_url_name = "panel:payment_detail"

    def get_queryset(self):
        return super().get_queryset().select_related("user", "plan").order_by("-created_at")

    def get_row_cells(self, obj):
        badge = _STATUS_BADGE.get(obj.status, "badge-free")
        return [
            obj.user.name,
            f"{obj.amount:,.0f} {obj.currency}".replace(",", " "),
            obj.get_method_display() if obj.method else "—",
            format_html('<span class="badge {}">{}</span>', badge, obj.get_status_display()),
            obj.created_at.strftime("%d.%m.%Y %H:%M"),
        ]


class PaymentDetailView(StaffRequiredMixin, PanelContextMixin, DetailView):
    model = Payment
    template_name = "panel/object_detail.html"
    nav_active = "payments"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self.object
        ctx["page_title"] = _("Payment")
        ctx["obj_title"] = f"{p.user.name} — {p.amount:,.0f} {p.currency}".replace(",", " ")
        ctx["back_url"] = reverse("panel:payments")
        ctx["obj_meta"] = [
            {"label": _("User"), "value": p.user.name},
            {"label": _("Amount"), "value": f"{p.amount:,.0f} {p.currency}".replace(",", " ")},
            {"label": _("Plan"), "value": p.plan.get_period_display() if p.plan else "—"},
            {"label": _("Method"), "value": p.get_method_display() if p.method else "—"},
            {"label": _("Status"), "value": p.get_status_display()},
            {"label": _("Auto payment"), "value": _("Yes") if p.is_auto_payment else _("No")},
            {"label": _("Created"), "value": p.created_at.strftime("%d.%m.%Y %H:%M")},
            {"label": _("Completed"), "value": p.completed_at.strftime("%d.%m.%Y %H:%M") if p.completed_at else "—"},
        ]
        return ctx
