"""Progression section — manage the weekly-growth rules.

Two models share one nav section via tabs:
  * ``ProgressionSetting``      — Gym (sets / reps / weight). Custom programs
    reuse these same rules.
  * ``HomeProgressionSetting``  — Home (rounds / time / rest).

Admins create/edit these here and later pick one per plan in the workout builder.
"""
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

from apps.models.workouts import HomeProgressionSetting, ProgressionSetting
from apps.panel.forms import HomeProgressionSettingForm, ProgressionSettingForm
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView


def _progression_tabs(active):
    """Two-tab bar shared by the Gym/Home progression lists."""
    return [
        {"label": _("Gym (sets / reps)"), "url": reverse("panel:progression"), "active": active == "gym"},
        {"label": _("Home (rounds / time)"), "url": reverse("panel:progression_home"), "active": active == "home"},
    ]


# ───────────────────────── Gym progression ─────────────────────────

class ProgressionListView(PanelListView):
    model = ProgressionSetting
    nav_active = "progression"
    page_title = _("Progression rules")
    columns = [_("Key"), _("Sets W2"), _("Sets W4"), _("Reps W3"), _("Reps W5")]
    search_fields = ["key"]
    create_url_name = "panel:progression_add"
    edit_url_name = "panel:progression_edit"
    delete_url_name = "panel:progression_delete"
    create_label = _("Add gym rule")

    def get_queryset(self):
        return super().get_queryset().order_by("key")

    def get_row_cells(self, obj):
        return [obj.key, obj.set_w2, obj.set_w4, obj.rep_w3, obj.rep_w5]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tabs"] = _progression_tabs("gym")
        return ctx


class ProgressionCreateView(PanelCreateView):
    model = ProgressionSetting
    form_class = ProgressionSettingForm
    nav_active = "progression"
    page_title = _("Add gym progression")
    success_url = reverse_lazy("panel:progression")
    success_message = _("Progression rule created.")


class ProgressionUpdateView(PanelUpdateView):
    model = ProgressionSetting
    form_class = ProgressionSettingForm
    nav_active = "progression"
    page_title = _("Edit gym progression")
    success_url = reverse_lazy("panel:progression")


class ProgressionDeleteView(PanelDeleteView):
    model = ProgressionSetting
    nav_active = "progression"
    page_title = _("Delete progression")
    success_url = reverse_lazy("panel:progression")


# ───────────────────────── Home progression ─────────────────────────

class HomeProgressionListView(PanelListView):
    model = HomeProgressionSetting
    nav_active = "progression"
    page_title = _("Progression rules")
    columns = [_("Key"), _("Rounds W3"), _("Duration W4"), _("Rest W2"), _("Rest W4")]
    search_fields = ["key"]
    create_url_name = "panel:progression_home_add"
    edit_url_name = "panel:progression_home_edit"
    delete_url_name = "panel:progression_home_delete"
    create_label = _("Add home rule")

    def get_queryset(self):
        return super().get_queryset().order_by("key")

    def get_row_cells(self, obj):
        return [obj.key, obj.round_w3, obj.duration_w4, obj.rest_w2, obj.rest_w4]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tabs"] = _progression_tabs("home")
        return ctx


class HomeProgressionCreateView(PanelCreateView):
    model = HomeProgressionSetting
    form_class = HomeProgressionSettingForm
    nav_active = "progression"
    page_title = _("Add home progression")
    success_url = reverse_lazy("panel:progression_home")
    success_message = _("Home progression rule created.")


class HomeProgressionUpdateView(PanelUpdateView):
    model = HomeProgressionSetting
    form_class = HomeProgressionSettingForm
    nav_active = "progression"
    page_title = _("Edit home progression")
    success_url = reverse_lazy("panel:progression_home")


class HomeProgressionDeleteView(PanelDeleteView):
    model = HomeProgressionSetting
    nav_active = "progression"
    page_title = _("Delete home progression")
    success_url = reverse_lazy("panel:progression_home")
