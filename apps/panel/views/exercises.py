"""Exercises section — CRUD over the exercise library."""
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from apps.models import Exercise
from apps.panel.forms import ExerciseForm
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView


class ExerciseListView(PanelListView):
    model = Exercise
    nav_active = "exercises"
    page_title = _("Exercises")
    columns = [_("Name"), _("Muscle group"), _("Type"), _("Calories"), _("Duration")]
    search_fields = ["name", "name_uz", "name_ru"]
    create_url_name = "panel:exercise_add"
    edit_url_name = "panel:exercise_edit"
    delete_url_name = "panel:exercise_delete"
    create_label = _("Add exercise")

    def get_row_cells(self, obj):
        return [
            obj.name,
            obj.get_primary_body_part_display(),
            obj.get_workout_type_display(),
            obj.calory,
            obj.duration,
        ]


class ExerciseCreateView(PanelCreateView):
    model = Exercise
    form_class = ExerciseForm
    template_name = "panel/exercise_form.html"
    nav_active = "exercises"
    page_title = _("Add exercise")
    success_url = reverse_lazy("panel:exercises")
    success_message = _("Exercise created.")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["progression_fields"] = ExerciseForm.PROGRESSION_FIELDS
        return ctx


class ExerciseUpdateView(PanelUpdateView):
    model = Exercise
    form_class = ExerciseForm
    template_name = "panel/exercise_form.html"
    nav_active = "exercises"
    page_title = _("Edit exercise")
    success_url = reverse_lazy("panel:exercises")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["progression_fields"] = ExerciseForm.PROGRESSION_FIELDS
        return ctx


class ExerciseDeleteView(PanelDeleteView):
    model = Exercise
    nav_active = "exercises"
    page_title = _("Delete exercise")
    success_url = reverse_lazy("panel:exercises")
