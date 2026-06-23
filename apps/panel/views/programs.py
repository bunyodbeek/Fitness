"""Programs section — build the full Program → Plan → Week → Workout →
WorkoutExercise hierarchy.

This is a drill-down UI over the *existing* models. All progression behaviour
(weeks 2..N generated from week-1 + apply_to_all_weeks) is produced by the
existing post_save signals on WorkoutExercise — nothing in that logic changes.
"""
import json

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, TemplateView

from apps.models import Exercise, Plan, Program, Week, Workout, WorkoutExercise
from apps.models.exercises import MuscleGroup
from apps.models.workouts import WorkoutType
from apps.panel.forms import (
    IndividualProgramForm, OneTimeProgramForm, PlanForm, ProgramForm,
    WeekForm, WorkoutExerciseForm, WorkoutForm,
)
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView
from apps.services.programs import ProgramGenerationService


def _yesno(flag):
    if flag:
        return format_html('<span class="badge badge-green">{}</span>', _("Yes"))
    return format_html('<span class="badge badge-free">{}</span>', _("No"))


def _mode_tabs(active, include_user=False):
    """Gym/Home (and optionally User) filter tabs for the Plans & Programs lists."""
    tabs = [
        {"label": _("All"), "url": "?", "active": not active},
        {"label": _("Gym"), "url": "?mode=gym", "active": active == "gym"},
        {"label": _("Home"), "url": "?mode=home", "active": active == "home"},
    ]
    if include_user:
        tabs.append({"label": _("User"), "url": "?mode=user", "active": active == "user"})
    return tabs


def _current_mode(request, allow_user=False):
    mode = (request.GET.get("mode") or "").lower()
    valid = {WorkoutType.GYM, WorkoutType.HOME}
    if allow_user:
        valid = valid | {"user"}
    return mode if mode in valid else ""


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
        qs = super().get_queryset()
        mode = _current_mode(self.request, allow_user=True)
        if mode == "user":
            # User-created (custom) programs — kept apart from admin content.
            return qs.filter(type=Program.ProgramType.CUSTOM).order_by("-created_at")
        # Admin programs only; individual & one-time live in their own sections.
        qs = qs.filter(
            type=Program.ProgramType.ADMIN, is_individual=False, is_one_time=False,
        )
        if mode in {WorkoutType.GYM, WorkoutType.HOME}:
            qs = qs.filter(workout_type=mode)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tabs"] = _mode_tabs(_current_mode(self.request, allow_user=True), include_user=True)
        return ctx

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
        qs = super().get_queryset().select_related("program").order_by("program__name", "order")
        mode = _current_mode(self.request)
        if mode:
            qs = qs.filter(program__workout_type=mode)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tabs"] = _mode_tabs(_current_mode(self.request))
        return ctx

    def get_row_cells(self, obj):
        return [obj.name, obj.program.name, obj.order, obj.weeks_count, _yesno(obj.is_premium)]


class PlanCreateView(PanelCreateView):
    model = Plan
    form_class = PlanForm
    nav_active = "plans"
    page_title = _("Add plan")
    success_url = reverse_lazy("panel:plans")
    success_message = _("Plan created. Weeks were generated automatically.")

    def get_initial(self):
        initial = super().get_initial()
        program_id = self.request.GET.get("program")
        if program_id:
            initial["program"] = program_id
        return initial

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
        is_home = pl.program.workout_type == WorkoutType.HOME
        progression = pl.home_progression_config if is_home else pl.progression_config
        ctx["obj_meta"] = [
            {"label": _("Mode"), "value": pl.program.get_workout_type_display()},
            {"label": _("Weeks"), "value": pl.weeks_count},
            {"label": _("Progression"), "value": progression or _("Not set")},
        ]
        if not progression:
            ctx["notice"] = _(
                "Tip: open a week-1 day and use “Build / add exercises” to pick a "
                "progression rule and add exercises — weeks 2..N then auto-fill."
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
        ctx["child_add2_url"] = reverse("panel:workout_from_template", args=[w.pk])
        ctx["child_add2_label"] = _("Add from pre-made day")
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

    def form_valid(self, form):
        week = self.get_parent()
        # Auto-number the day (next free) so many days can be added freely, and
        # auto-enable progression copy for week-1 days (applies to every day).
        last = week.workouts.order_by("-day_number").first()
        form.instance.day_number = (last.day_number + 1) if last else 1
        form.instance.apply_to_all_weeks = (week.week_number == 1)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("panel:workout_builder", args=[self.object.pk])

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
        ctx["child_add_url"] = reverse("panel:workout_builder", args=[wo.pk])
        ctx["child_add_label"] = _("Build / add exercises")
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


# ───────────────────────── Visual workout builder ─────────────────────────

class WorkoutBuilderView(StaffRequiredMixin, PanelContextMixin, TemplateView):
    """Mode-aware exercise builder for one day (Workout).

    Replaces the plain add-exercise form with a visual picker (body-part dropdown
    + name search). Inputs adapt to the program mode — Gym shows sets/reps/weight,
    Home shows rounds (day) + time. The plan's progression rule is also chosen
    here. Saving week-1 seeds still triggers the existing weeks 2..N generation.
    """
    template_name = "panel/workout_builder.html"
    nav_active = "plans"

    def get_workout(self):
        return get_object_or_404(
            Workout.objects.select_related("week__plan__program"), pk=self.kwargs["pk"]
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        wo = self.get_workout()
        week = wo.week
        plan = week.plan
        program = plan.program
        is_one_time = program.is_one_time
        is_home = program.workout_type == WorkoutType.HOME
        # One-time programs always use gym-style inputs (sets / reps / weight) and
        # have no weeks / progression.
        show_home_inputs = is_home and not is_one_time

        added = list(wo.workout_exercises.select_related("exercise").all())
        ctx["added_json"] = [
            {
                "exercise_id": we.exercise_id,
                "name": we.exercise.name,
                "muscle": we.exercise.get_primary_body_part_display(),
                "thumb": we.exercise.thumbnail.url if we.exercise.thumbnail else "",
                "sets": we.sets,
                "reps": we.reps,
                "weight": we.recommended_weight or 0,
                "minutes": we.minutes or 0,
            }
            for we in added
        ]
        if is_one_time:
            back_url = reverse("panel:onetime")
            breadcrumbs = [
                {"label": _("One-time programs"), "url": back_url},
                {"label": program.name},
            ]
        else:
            back_url = reverse("panel:workout_detail", args=[wo.pk])
            breadcrumbs = [
                {"label": _("Plans"), "url": reverse("panel:plans")},
                {"label": plan.name, "url": reverse("panel:plan_detail", args=[plan.pk])},
                {"label": week.display_name, "url": reverse("panel:week_detail", args=[week.pk])},
                {"label": wo.title or f"{_('Day')} {wo.day_number}",
                 "url": reverse("panel:workout_detail", args=[wo.pk])},
                {"label": _("Build")},
            ]

        ctx.update({
            "workout": wo,
            "week": week,
            "plan": plan,
            "program": program,
            "is_home": is_home,
            "is_one_time": is_one_time,
            "show_home_inputs": show_home_inputs,
            "page_title": program.name if is_one_time else _("Build day"),
            "obj_title": program.name if is_one_time else (wo.title or f"{_('Day')} {wo.day_number}"),
            "back_url": back_url,
            "breadcrumbs": breadcrumbs,
            "exercises": Exercise.objects.filter(
                workout_type=program.workout_type
            ).order_by("name"),
            "body_parts": MuscleGroup.choices,
        })
        return ctx

    def post(self, request, *args, **kwargs):
        wo = self.get_workout()
        plan = wo.week.plan
        program = plan.program
        is_one_time = program.is_one_time
        is_home = program.workout_type == WorkoutType.HOME
        # One-time → gym-style inputs, no progression/weeks.
        save_home_inputs = is_home and not is_one_time

        if not is_one_time:
            # Day-level fields: apply-to-all-weeks (+ rounds for home). The
            # progression rule itself now lives on the Plan (chosen at plan
            # creation), so the generation signal reads it from there.
            wo.apply_to_all_weeks = bool(request.POST.get("apply_to_all_weeks"))
            if is_home:
                try:
                    wo.rounds = max(1, int(request.POST.get("rounds") or wo.rounds or 1))
                except (TypeError, ValueError):
                    pass
            wo.save()

        # 3) Exercises (create/update + delete removed).
        try:
            rows = json.loads(request.POST.get("exercises_json") or "[]")
        except (ValueError, TypeError):
            rows = []

        submitted_ids = []
        for i, row in enumerate(rows):
            try:
                eid = int(row.get("exercise_id"))
            except (TypeError, ValueError):
                continue
            submitted_ids.append(eid)
            defaults = {"order": i}
            if save_home_inputs:
                defaults.update({"minutes": _to_int(row.get("minutes")), "sets": 0, "reps": 0})
            else:
                defaults.update({
                    "sets": _to_int(row.get("sets")),
                    "reps": _to_int(row.get("reps")),
                    "recommended_weight": _to_float(row.get("weight")),
                })
            WorkoutExercise.objects.update_or_create(
                workout=wo, exercise_id=eid, defaults=defaults,
            )

        # Remove exercises the admin took out (and their generated week 2..N copies).
        for we in wo.workout_exercises.exclude(exercise_id__in=submitted_ids):
            WorkoutExercise.objects.filter(source_week_one=we).delete()
            we.delete()

        if is_one_time:
            messages.success(request, _("One-time program saved."))
            return redirect("panel:onetime")
        messages.success(request, _("Day saved."))
        return redirect("panel:workout_detail", pk=wo.pk)


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ───────────────────────── Gym / Home workout sections ─────────────────────────

class _ModeWorkoutsListView(PlanListView):
    """Plans for one mode (gym/home), excluding individual & one-time programs.

    These are the primary entry points for building normal workouts: pick a
    plan → week → day → the visual builder.
    """
    forced_mode = None

    def get_queryset(self):
        return (
            Plan.objects.filter(
                program__workout_type=self.forced_mode,
                program__type=Program.ProgramType.ADMIN,
                program__is_individual=False,
                program__is_one_time=False,
            )
            .select_related("program")
            .order_by("program__name", "order")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.pop("tabs", None)  # mode is fixed by the section
        return ctx


class GymWorkoutsListView(_ModeWorkoutsListView):
    forced_mode = WorkoutType.GYM
    nav_active = "gym_workouts"
    page_title = _("Gym Workouts")
    create_label = _("Add gym plan")


class HomeWorkoutsListView(_ModeWorkoutsListView):
    forced_mode = WorkoutType.HOME
    nav_active = "home_workouts"
    page_title = _("Home Workouts")
    create_label = _("Add home plan")


# ───────────────────────── Individual (recommended) programs ─────────────────────────

class IndividualProgramListView(ProgramListView):
    nav_active = "individual"
    page_title = _("Individual programs")
    create_url_name = "panel:individual_add"
    edit_url_name = "panel:individual_edit"
    delete_url_name = "panel:individual_delete"
    open_url_name = "panel:program_plans"
    create_label = _("Add individual program")

    def get_queryset(self):
        return Program.objects.filter(is_individual=True).order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.pop("tabs", None)
        return ctx


class IndividualProgramCreateView(PanelCreateView):
    model = Program
    form_class = IndividualProgramForm
    nav_active = "individual"
    page_title = _("Add individual program")
    success_url = reverse_lazy("panel:individual")
    success_message = _("Individual program created. Now add a plan and build its weeks.")

    def form_valid(self, form):
        form.instance.is_individual = True
        form.instance.is_one_time = False
        return super().form_valid(form)


class IndividualProgramUpdateView(PanelUpdateView):
    model = Program
    form_class = IndividualProgramForm
    nav_active = "individual"
    page_title = _("Edit individual program")
    success_url = reverse_lazy("panel:individual")

    def get_queryset(self):
        return Program.objects.filter(is_individual=True)

    def form_valid(self, form):
        form.instance.is_individual = True
        return super().form_valid(form)


class IndividualProgramDeleteView(PanelDeleteView):
    model = Program
    nav_active = "individual"
    page_title = _("Delete individual program")
    success_url = reverse_lazy("panel:individual")

    def get_queryset(self):
        return Program.objects.filter(is_individual=True)


# ───────────────────────── One-time programs (single session) ─────────────────────────

def _ensure_single_workout(program):
    """A one-time program hides the plan/week/day structure: behind the scenes it
    is one plan → one week → one day. Create it lazily and return that day."""
    plan = program.plans.order_by("order", "id").first()
    if plan is None:
        plan = Plan.objects.create(
            program=program, name=program.name or "One-time", order=1, weeks_count=1,
        )
    week = plan.weeks.order_by("week_number").first()
    if week is None:
        week = Week.objects.create(plan=plan, week_number=1)
    workout = week.workouts.order_by("day_number", "id").first()
    if workout is None:
        workout = Workout.objects.create(week=week, day_number=1, title=program.name or "")
    return workout


class OneTimeProgramListView(ProgramListView):
    nav_active = "onetime"
    page_title = _("One-time programs")
    columns = [_("Name"), _("Mode"), _("Exercises"), _("Active")]
    create_url_name = "panel:onetime_add"
    open_url_name = "panel:onetime_builder"
    delete_url_name = "panel:onetime_delete"
    edit_url_name = None
    create_label = _("Add one-time program")

    def get_queryset(self):
        return Program.objects.filter(is_one_time=True).order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.pop("tabs", None)
        return ctx

    def get_row_cells(self, obj):
        workout = obj.first_workout
        ex_count = workout.workout_exercises.count() if workout else 0
        return [obj.name, obj.get_workout_type_display(), ex_count, _yesno(obj.is_active)]


class OneTimeProgramCreateView(PanelCreateView):
    model = Program
    form_class = OneTimeProgramForm
    nav_active = "onetime"
    page_title = _("Add one-time program")
    success_url = reverse_lazy("panel:onetime")
    success_message = _("One-time program created. Now add exercises.")

    def form_valid(self, form):
        form.instance.is_one_time = True
        form.instance.is_individual = False
        response = super().form_valid(form)
        # Scaffold the hidden single day, then go straight to the builder.
        workout = _ensure_single_workout(self.object)
        return redirect("panel:workout_builder", pk=workout.pk)


class OneTimeProgramDeleteView(PanelDeleteView):
    model = Program
    nav_active = "onetime"
    page_title = _("Delete one-time program")
    success_url = reverse_lazy("panel:onetime")

    def get_queryset(self):
        return Program.objects.filter(is_one_time=True)


class OneTimeBuilderRedirectView(StaffRequiredMixin, PanelContextMixin, TemplateView):
    """Open a one-time program straight in the exercise builder (its single day)."""

    def get(self, request, *args, **kwargs):
        program = get_object_or_404(Program, pk=self.kwargs["pk"], is_one_time=True)
        workout = _ensure_single_workout(program)
        return redirect("panel:workout_builder", pk=workout.pk)


# ───────────────────────── Program → plans drill-down ─────────────────────────

class ProgramPlansView(StaffRequiredMixin, PanelContextMixin, DetailView):
    """Show one program's plans (used by the Individual section to build them)."""
    model = Program
    template_name = "panel/detail.html"
    nav_active = "individual"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pr = self.object
        is_individual = pr.is_individual
        ctx["page_title"] = pr.name
        ctx["obj_title"] = pr.name
        ctx["obj_edit_url"] = reverse(
            "panel:individual_edit" if is_individual else "panel:program_edit", args=[pr.pk]
        )
        back = reverse("panel:individual") if is_individual else reverse("panel:programs")
        ctx["back_url"] = back
        ctx["breadcrumbs"] = [
            {"label": _("Individual programs") if is_individual else _("Programs"), "url": back},
            {"label": pr.name},
        ]
        ctx["obj_meta"] = [
            {"label": _("Mode"), "value": pr.get_workout_type_display()},
            {"label": _("Goal"), "value": pr.get_goal_display()},
            {"label": _("Level"), "value": pr.get_level_display()},
        ]
        ctx["child_title"] = _("Plans")
        ctx["child_add_url"] = reverse("panel:plan_add") + f"?program={pr.pk}"
        ctx["child_add_label"] = _("Add plan")
        ctx["child_columns"] = [_("Name"), _("Weeks")]
        ctx["child_rows"] = [
            {
                "cells": [pl.name, pl.weeks_count],
                "open_url": reverse("panel:plan_detail", args=[pl.pk]),
                "delete_url": reverse("panel:plan_delete", args=[pl.pk]),
            }
            for pl in pr.plans.order_by("order", "id")
        ]
        return ctx
