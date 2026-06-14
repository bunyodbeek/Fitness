"""Programs section — build the full Program → Plan → Week → Workout →
WorkoutExercise hierarchy.

This is a drill-down UI over the *existing* models. All progression behaviour
(weeks 2..N generated from week-1 + apply_to_all_weeks) is produced by the
existing post_save signals on WorkoutExercise — nothing in that logic changes.
"""
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from apps.models import Plan, Program, Week, Workout, WorkoutExercise
from apps.panel.forms import PlanForm, ProgramForm, WeekForm, WorkoutExerciseForm, WorkoutForm
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView
from apps.services.programs import ProgramGenerationService


def _yesno(flag):
    if flag:
        return format_html('<span class="badge badge-green">{}</span>', _("Yes"))
    return format_html('<span class="badge badge-free">{}</span>', _("No"))


# ───────────────────────── parent-scoped create base ─────────────────────────

class _ScopedCreateView(PanelCreateView):
    """CreateView whose object belongs to a parent loaded from a URL kwarg."""
    parent_model = None
    parent_url_kwarg = None
    parent_attr = None       # FK attribute name on the child instance

    def get_parent(self):
        return get_object_or_404(self.parent_model, pk=self.kwargs[self.parent_url_kwarg])

    def form_valid(self, form):
        setattr(form.instance, self.parent_attr, self.get_parent())
        return super().form_valid(form)


# ───────────────────────── Program ─────────────────────────

class ProgramListView(PanelListView):
    model = Program
    nav_active = "programs"
    page_title = _("Programs")
    columns = [_("Name"), _("Mode"), _("Level"), _("Goal"), _("Plans"), _("Active")]
    search_fields = ["name", "name_uz", "name_ru"]
    create_url_name = "panel:program_add"
    edit_url_name = "panel:program_edit"
    delete_url_name = "panel:program_delete"
    create_label = _("Add program")

    def get_queryset(self):
        return super().get_queryset().order_by("-created_at")

    def get_row_cells(self, obj):
        return [
            obj.name,
            obj.get_workout_type_display(),
            obj.get_level_display(),
            obj.get_goal_display(),
            obj.plans.count(),
            _yesno(obj.is_active),
        ]


class ProgramCreateView(PanelCreateView):
    model = Program
    form_class = ProgramForm
    nav_active = "programs"
    page_title = _("Add program")
    success_url = reverse_lazy("panel:programs")
    success_message = _("Program created. Add plans for it in the Plans section.")


class ProgramUpdateView(PanelUpdateView):
    model = Program
    form_class = ProgramForm
    nav_active = "programs"
    page_title = _("Edit program")
    success_url = reverse_lazy("panel:programs")


class ProgramDeleteView(PanelDeleteView):
    model = Program
    nav_active = "programs"
    page_title = _("Delete program")
    success_url = reverse_lazy("panel:programs")


# ───────────────────────── Plan (own section) ─────────────────────────

class PlanListView(PanelListView):
    model = Plan
    nav_active = "plans"
    page_title = _("Plans")
    columns = [_("Name"), _("Program"), _("Order"), _("Weeks"), _("Premium")]
    search_fields = ["name", "program__name"]
    create_url_name = "panel:plan_add"
    open_url_name = "panel:plan_detail"
    delete_url_name = "panel:plan_delete"
    create_label = _("Add plan")

    def get_queryset(self):
        return super().get_queryset().select_related("program").order_by("program__name", "order")

    def get_row_cells(self, obj):
        return [obj.name, obj.program.name, obj.order, obj.weeks_count, _yesno(obj.is_premium)]


class PlanCreateView(PanelCreateView):
    model = Plan
    form_class = PlanForm
    nav_active = "plans"
    page_title = _("Add plan")
    success_url = reverse_lazy("panel:plans")
    success_message = _("Plan created. Weeks were generated automatically.")

    def form_valid(self, form):
        response = super().form_valid(form)
        # Auto-create the plan's weeks (1..N), mirroring existing behaviour.
        ProgramGenerationService.ensure_plan_weeks(self.object)
        return response

    def get_success_url(self):
        return reverse("panel:plan_detail", args=[self.object.pk])


class PlanUpdateView(PanelUpdateView):
    model = Plan
    form_class = PlanForm
    nav_active = "plans"
    page_title = _("Edit plan")

    def get_success_url(self):
        return reverse("panel:plan_detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("panel:plan_detail", args=[self.object.pk])


class PlanDeleteView(PanelDeleteView):
    model = Plan
    nav_active = "plans"
    page_title = _("Delete plan")
    success_url = reverse_lazy("panel:plans")


class PlanDetailView(StaffRequiredMixin, PanelContextMixin, DetailView):
    model = Plan
    template_name = "panel/detail.html"
    nav_active = "plans"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pl = self.object
        ctx["page_title"] = pl.name
        ctx["obj_title"] = f"{pl.program.name} · {pl.name}"
        ctx["obj_edit_url"] = reverse("panel:plan_edit", args=[pl.pk])
        ctx["back_url"] = reverse("panel:plans")
        ctx["breadcrumbs"] = [
            {"label": _("Plans"), "url": reverse("panel:plans")},
            {"label": pl.name},
        ]
        ctx["obj_meta"] = [
            {"label": _("Weeks"), "value": pl.weeks_count},
            {"label": _("Progression"), "value": pl.progression_config or _("Not set")},
        ]
        if not pl.progression_config:
            ctx["notice"] = _(
                "Tip: set a Progression rule on this plan so that adding week-1 "
                "exercises (with 'apply to all weeks') auto-fills weeks 2..N."
            )
        ctx["child_title"] = _("Weeks")
        ctx["child_add_url"] = reverse("panel:week_add", args=[pl.pk])
        ctx["child_add_label"] = _("Add week")
        ctx["child_columns"] = [_("Week"), _("Days")]
        ctx["child_rows"] = [
            {
                "cells": [w.display_name, w.workouts.count()],
                "open_url": reverse("panel:week_detail", args=[w.pk]),
                "delete_url": reverse("panel:week_delete", args=[w.pk]),
            }
            for w in pl.weeks.all()
        ]
        return ctx


# ───────────────────────── Week ─────────────────────────

class WeekCreateView(_ScopedCreateView):
    model = Week
    form_class = WeekForm
    parent_model = Plan
    parent_url_kwarg = "plan_pk"
    parent_attr = "plan"
    nav_active = "plans"
    page_title = _("Add week")
    success_message = _("Week created.")

    def form_valid(self, form):
        plan = self.get_parent()
        week_number = form.cleaned_data.get("week_number")
        # Weeks are auto-created with the plan, so guard against duplicates and
        # show a friendly error instead of a DB IntegrityError.
        if Week.objects.filter(plan=plan, week_number=week_number).exists():
            form.add_error("week_number", _("This week already exists for this plan."))
            return self.form_invalid(form)
        response = super().form_valid(form)
        if form.cleaned_data.get("generate_remaining_weeks"):
            plan = self.object.plan
            max_weeks = 4 if getattr(plan, "is_4_week", False) else 6
            for n in range(self.object.week_number + 1, max_weeks + 1):
                Week.objects.get_or_create(plan=plan, week_number=n)
        return response

    def get_success_url(self):
        return reverse("panel:plan_detail", args=[self.kwargs["plan_pk"]])

    def get_cancel_url(self):
        return reverse("panel:plan_detail", args=[self.kwargs["plan_pk"]])


class WeekDeleteView(PanelDeleteView):
    model = Week
    nav_active = "plans"
    page_title = _("Delete week")

    def get_success_url(self):
        return reverse("panel:plan_detail", args=[self.object.plan_id])


class WeekDetailView(StaffRequiredMixin, PanelContextMixin, DetailView):
    model = Week
    template_name = "panel/detail.html"
    nav_active = "plans"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        w = self.object
        plan = w.plan
        ctx["page_title"] = w.display_name
        ctx["obj_title"] = f"{plan.name} · {w.display_name}"
        ctx["back_url"] = reverse("panel:plan_detail", args=[plan.pk])
        ctx["breadcrumbs"] = [
            {"label": _("Plans"), "url": reverse("panel:plans")},
            {"label": plan.name, "url": reverse("panel:plan_detail", args=[plan.pk])},
            {"label": w.display_name},
        ]
        ctx["child_title"] = _("Days (workouts)")
        ctx["child_add_url"] = reverse("panel:workout_add", args=[w.pk])
        ctx["child_add_label"] = _("Add day")
        ctx["child_columns"] = [_("Day"), _("Title"), _("Exercises"), _("All weeks")]
        ctx["child_rows"] = [
            {
                "cells": [
                    f"{_('Day')} {wo.day_number}",
                    wo.title or "—",
                    wo.workout_exercises.count(),
                    _yesno(wo.apply_to_all_weeks),
                ],
                "open_url": reverse("panel:workout_detail", args=[wo.pk]),
                "edit_url": reverse("panel:workout_edit", args=[wo.pk]),
                "delete_url": reverse("panel:workout_delete", args=[wo.pk]),
            }
            for wo in w.workouts.all()
        ]
        return ctx


# ───────────────────────── Workout (day) ─────────────────────────

class WorkoutCreateView(_ScopedCreateView):
    model = Workout
    form_class = WorkoutForm
    parent_model = Week
    parent_url_kwarg = "week_pk"
    parent_attr = "week"
    nav_active = "plans"
    page_title = _("Add day")
    success_message = _("Day created. Now add exercises.")

    def get_success_url(self):
        return reverse("panel:workout_detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("panel:week_detail", args=[self.kwargs["week_pk"]])


class WorkoutUpdateView(PanelUpdateView):
    model = Workout
    form_class = WorkoutForm
    nav_active = "plans"
    page_title = _("Edit day")

    def get_success_url(self):
        return reverse("panel:workout_detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("panel:workout_detail", args=[self.object.pk])


class WorkoutDeleteView(PanelDeleteView):
    model = Workout
    nav_active = "plans"
    page_title = _("Delete day")

    def get_success_url(self):
        return reverse("panel:week_detail", args=[self.object.week_id])


class WorkoutDetailView(StaffRequiredMixin, PanelContextMixin, DetailView):
    model = Workout
    template_name = "panel/detail.html"
    nav_active = "plans"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        wo = self.object
        week = wo.week
        plan = week.plan
        ctx["page_title"] = wo.title or f"{_('Day')} {wo.day_number}"
        ctx["obj_title"] = wo.title or f"{_('Day')} {wo.day_number}"
        ctx["obj_edit_url"] = reverse("panel:workout_edit", args=[wo.pk])
        ctx["back_url"] = reverse("panel:week_detail", args=[week.pk])
        ctx["breadcrumbs"] = [
            {"label": _("Plans"), "url": reverse("panel:plans")},
            {"label": plan.name, "url": reverse("panel:plan_detail", args=[plan.pk])},
            {"label": week.display_name, "url": reverse("panel:week_detail", args=[week.pk])},
            {"label": ctx["obj_title"]},
        ]
        ctx["obj_meta"] = [
            {"label": _("Day"), "value": wo.day_number},
            {"label": _("Rounds"), "value": wo.rounds},
            {"label": _("Apply to all weeks"), "value": _("Yes") if wo.apply_to_all_weeks else _("No")},
        ]
        if week.week_number == 1 and wo.apply_to_all_weeks and plan.progression_config:
            ctx["notice"] = _(
                "Week-1 day with 'apply to all weeks' on: saving an exercise here "
                "auto-generates weeks 2..N via progression."
            )
        ctx["child_title"] = _("Exercises")
        ctx["child_add_url"] = reverse("panel:we_add", args=[wo.pk])
        ctx["child_add_label"] = _("Add exercise")
        ctx["child_columns"] = [_("Exercise"), _("Sets"), _("Reps"), _("Weight"), _("Order")]
        ctx["child_rows"] = [
            {
                "cells": [we.exercise.name, we.sets, we.reps, we.recommended_weight, we.order],
                "edit_url": reverse("panel:we_edit", args=[we.pk]),
                "delete_url": reverse("panel:we_delete", args=[we.pk]),
            }
            for we in wo.workout_exercises.select_related("exercise").all()
        ]
        return ctx


# ───────────────────────── WorkoutExercise ─────────────────────────

class WorkoutExerciseCreateView(_ScopedCreateView):
    model = WorkoutExercise
    form_class = WorkoutExerciseForm
    parent_model = Workout
    parent_url_kwarg = "workout_pk"
    parent_attr = "workout"
    nav_active = "plans"
    page_title = _("Add exercise")
    success_message = _("Exercise added.")

    def get_success_url(self):
        return reverse("panel:workout_detail", args=[self.kwargs["workout_pk"]])

    def get_cancel_url(self):
        return reverse("panel:workout_detail", args=[self.kwargs["workout_pk"]])


class WorkoutExerciseUpdateView(PanelUpdateView):
    model = WorkoutExercise
    form_class = WorkoutExerciseForm
    nav_active = "plans"
    page_title = _("Edit exercise")

    def get_success_url(self):
        return reverse("panel:workout_detail", args=[self.object.workout_id])

    def get_cancel_url(self):
        return reverse("panel:workout_detail", args=[self.object.workout_id])


class WorkoutExerciseDeleteView(PanelDeleteView):
    model = WorkoutExercise
    nav_active = "plans"
    page_title = _("Delete exercise")

    def get_success_url(self):
        return reverse("panel:workout_detail", args=[self.object.workout_id])
