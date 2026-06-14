"""Reports section — revenue & user reports aggregated from real data."""
from datetime import date

from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from apps.models import User
from apps.models.payments import Payment, Subscription
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin

_MONTHS = [
    _("January"), _("February"), _("March"), _("April"), _("May"), _("June"),
    _("July"), _("August"), _("September"), _("October"), _("November"), _("December"),
]


def _month_bounds(year, month):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


class ReportsView(StaffRequiredMixin, PanelContextMixin, TemplateView):
    template_name = "panel/reports.html"
    nav_active = "reports"
    page_title = _("Reports")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        today = timezone.localdate()

        completed = Payment.objects.filter(
            status=Payment.PaymentStatus.COMPLETED, currency=Payment.Currency.UZS
        )
        total_revenue = completed.aggregate(t=Sum("amount"))["t"] or 0
        total_users = User.objects.count()
        premium_users = Subscription.objects.filter(is_active=True, end_date__gte=now).count()
        conversion = round(premium_users / total_users * 100, 1) if total_users else 0

        ctx["summary"] = [
            {"label": _("Total revenue"), "value": f"{int(total_revenue):,} UZS".replace(",", " ")},
            {"label": _("Completed payments"), "value": completed.count()},
            {"label": _("Total users"), "value": total_users},
            {"label": _("Premium members"), "value": premium_users},
            {"label": _("Conversion rate"), "value": f"{conversion}%"},
        ]

        # Last 6 months series (oldest -> newest)
        months = []
        y, m = today.year, today.month
        seq = []
        for _i in range(6):
            seq.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        seq.reverse()

        rev_values = []
        for (yy, mm) in seq:
            start, end = _month_bounds(yy, mm)
            rev = completed.filter(created_at__date__gte=start, created_at__date__lt=end).aggregate(t=Sum("amount"))["t"] or 0
            new_users = User.objects.filter(date_joined__date__gte=start, date_joined__date__lt=end).count()
            months.append({"label": f"{_MONTHS[mm - 1]} {yy}", "revenue": int(rev), "users": new_users})
            rev_values.append(int(rev))

        max_rev = max(rev_values) if any(rev_values) else 1
        for row in months:
            row["height"] = round(row["revenue"] / max_rev * 100) if max_rev else 0
            row["revenue_display"] = f"{row['revenue']:,}".replace(",", " ")
        ctx["months"] = months
        return ctx
