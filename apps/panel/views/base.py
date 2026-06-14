"""Shared base view + context for all panel pages."""
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from apps.panel.mixins import StaffRequiredMixin

# Month names (translatable) for the header date label.
_MONTHS = [
    _("January"), _("February"), _("March"), _("April"), _("May"), _("June"),
    _("July"), _("August"), _("September"), _("October"), _("November"), _("December"),
]


class PanelContextMixin:
    """Adds the nav-active key + a localized header date to the context."""

    nav_active = ""
    page_title = ""

    def get_page_title(self):
        return self.page_title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()
        context["nav_active"] = self.nav_active
        context["page_title"] = self.get_page_title()
        context["header_date"] = f"{_MONTHS[now.month - 1]} {now.year}"
        context["admin_user"] = self.request.user
        return context


class PanelView(StaffRequiredMixin, PanelContextMixin, TemplateView):
    """Base for simple staff-only panel template views."""


class PlaceholderView(PanelView):
    """Temporary 'under construction' page used until a section is built."""

    template_name = "panel/placeholder.html"
