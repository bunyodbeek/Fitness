"""Tracking section — CRUD over WorkoutProgress (user workout tracking)."""
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.models.workouts import WorkoutProgress
from apps.panel.forms import WorkoutProgressForm
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView


class TrackingListView(PanelListView):
    model = WorkoutProgress
    nav_active = "tracking"
    page_title = _("Tracking")
    columns = [_("User"), _("Workout"), _("Status"), _("Calories"), _("Date")]
    search_fields = ["user__name", "workout__title"]
    create_url_name = "panel:tracking_add"
    edit_url_name = "panel:tracking_edit"
    delete_url_name = "panel:tracking_delete"
    create_label = _("Add record")

    def get_queryset(self):
        return super().get_queryset().select_related("user", "workout").order_by("-completed_at")

    def get_row_cells(self, obj):
        if obj.status == WorkoutProgress.Status.COMPLETED:
            status = format_html('<span class="badge badge-green">{}</span>', obj.get_status_display())
        else:
            status = format_html('<span class="badge badge-free">{}</span>', obj.get_status_display())
        return [
            obj.user.name,
            obj.workout.title or str(obj.workout),
            status,
            round(obj.total_calories or 0),
            obj.completed_at.strftime("%d.%m.%Y") if obj.completed_at else "—",
        ]


class TrackingCreateView(PanelCreateView):
    model = WorkoutProgress
    form_class = WorkoutProgressForm
    nav_active = "tracking"
    page_title = _("Add record")
    success_url = reverse_lazy("panel:tracking")
    success_message = _("Tracking record created.")


class TrackingUpdateView(PanelUpdateView):
    model = WorkoutProgress
    form_class = WorkoutProgressForm
    nav_active = "tracking"
    page_title = _("Edit record")
    success_url = reverse_lazy("panel:tracking")


class TrackingDeleteView(PanelDeleteView):
    model = WorkoutProgress
    nav_active = "tracking"
    page_title = _("Delete record")
    success_url = reverse_lazy("panel:tracking")
