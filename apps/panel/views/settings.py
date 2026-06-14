"""Settings section — subscription tariffs management (real data)."""
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.models.payments import SubscriptionPlan
from apps.panel.forms import SubscriptionPlanForm
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView


def _yesno(flag):
    if flag:
        return format_html('<span class="badge badge-green">{}</span>', _("Yes"))
    return format_html('<span class="badge badge-free">{}</span>', _("No"))


class SettingsListView(PanelListView):
    model = SubscriptionPlan
    nav_active = "settings"
    page_title = _("Settings — Tariffs")
    columns = [_("Period"), _("Price (UZS)"), _("Price (USD)"), _("Popular"), _("Active"), _("Order")]
    create_url_name = "panel:settings_plan_add"
    edit_url_name = "panel:settings_plan_edit"
    delete_url_name = "panel:settings_plan_delete"
    create_label = _("Add tariff")

    def get_queryset(self):
        return super().get_queryset().order_by("order", "price_uzs")

    def get_row_cells(self, obj):
        return [
            obj.get_period_display(),
            f"{obj.price_uzs:,.0f}".replace(",", " "),
            f"{obj.price_usd:,.2f}",
            _yesno(obj.is_popular),
            _yesno(obj.is_active),
            obj.order,
        ]


class TariffCreateView(PanelCreateView):
    model = SubscriptionPlan
    form_class = SubscriptionPlanForm
    nav_active = "settings"
    page_title = _("Add tariff")
    success_url = reverse_lazy("panel:settings")
    success_message = _("Tariff created.")


class TariffUpdateView(PanelUpdateView):
    model = SubscriptionPlan
    form_class = SubscriptionPlanForm
    nav_active = "settings"
    page_title = _("Edit tariff")
    success_url = reverse_lazy("panel:settings")


class TariffDeleteView(PanelDeleteView):
    model = SubscriptionPlan
    nav_active = "settings"
    page_title = _("Delete tariff")
    success_url = reverse_lazy("panel:settings")
