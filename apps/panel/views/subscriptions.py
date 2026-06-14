"""Subscriptions section — CRUD over Subscription."""
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.models.payments import Subscription
from apps.panel.forms import SubscriptionForm
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView


class SubscriptionListView(PanelListView):
    model = Subscription
    nav_active = "subscriptions"
    page_title = _("Subscriptions")
    columns = [_("User"), _("Plan"), _("Start"), _("End"), _("Status")]
    search_fields = ["user__name"]
    create_url_name = "panel:subscription_add"
    edit_url_name = "panel:subscription_edit"
    delete_url_name = "panel:subscription_delete"
    create_label = _("Add subscription")

    def get_queryset(self):
        return super().get_queryset().select_related("user", "plan").order_by("-start_date")

    def get_row_cells(self, obj):
        if obj.is_valid:
            status = format_html('<span class="badge badge-green">{}</span>', _("Active"))
        else:
            status = format_html('<span class="badge badge-red">{}</span>', _("Expired"))
        return [
            obj.user.name,
            obj.plan.get_period_display() if obj.plan else "—",
            obj.start_date.strftime("%d.%m.%Y") if obj.start_date else "—",
            obj.end_date.strftime("%d.%m.%Y") if obj.end_date else "—",
            status,
        ]


class SubscriptionCreateView(PanelCreateView):
    model = Subscription
    form_class = SubscriptionForm
    nav_active = "subscriptions"
    page_title = _("Add subscription")
    success_url = reverse_lazy("panel:subscriptions")
    success_message = _("Subscription created.")


class SubscriptionUpdateView(PanelUpdateView):
    model = Subscription
    form_class = SubscriptionForm
    nav_active = "subscriptions"
    page_title = _("Edit subscription")
    success_url = reverse_lazy("panel:subscriptions")


class SubscriptionDeleteView(PanelDeleteView):
    model = Subscription
    nav_active = "subscriptions"
    page_title = _("Delete subscription")
    success_url = reverse_lazy("panel:subscriptions")
