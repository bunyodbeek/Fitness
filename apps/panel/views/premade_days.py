"""Pre-made days — standalone, reusable days of exercises (a day "library").

A pre-made day (``DayTemplate``) is NOT bound to any plan/week. Admins build it
here, then attach it to a plan from the week view: attaching COPIES the day's
exercises into a normal ``Workout`` / ``WorkoutExercise`` (a snapshot), which
means the existing progression / generation signals run exactly as they do for a
hand-built day. None of the backend model logic is changed.
"""
import json

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from apps.models import Exercise, Week, Workout, WorkoutExercise
from apps.models.exercises import MuscleGroup
from apps.models.workouts import DayTemplate, DayTemplateExercise, WorkoutType
from apps.panel.forms import DayTemplateForm
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView
from apps.panel.views.programs import _current_mode, _mode_tabs, _to_float, _to_int, _yesno


def _type_badge(workout_type):
    label = _("Home") if workout_type == WorkoutType.HOME else _("Gym")
    css = "badge-green" if workout_type == WorkoutType.HOME else "badge-premium"
    from django.utils.html import format_html
    return format_html('<span class="badge {}">{}</span>', css, label)


# ───────────────────────── Pre-made day CRUD ─────────────────────────

class PremadeDayListView(PanelListView):
    model = DayTemplate
    nav_active = "premade_days"
    page_title = _("Pre-made days")
    columns = [_("Name"), _("Type"), _("Exercises")]
    search_fields = ["name", "name_uz", "name_ru"]
    create_url_name = "panel:premade_day_add"
    open_url_name = "panel:premade_day_builder"
    edit_url_name = "panel:premade_day_edit"
    delete_url_name = "panel:premade_day_delete"
    create_label = _("Add pre-made day")

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("exercises")
        mode = _current_mode(self.request)
        if mode:
            qs = qs.filter(workout_type=mode)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tabs"] = _mode_tabs(_current_mode(self.request))
        return ctx

    def get_row_cells(self, obj):
        return [obj.name, _type_badge(obj.workout_type), obj.exercises.count()]


class PremadeDayCreateView(PanelCreateView):
    model = DayTemplate
    form_class = DayTemplateForm
    nav_active = "premade_days"
    page_title = _("Add pre-made day")
    success_message = _("Pre-made day created. Now add exercises.")

    def get_success_url(self):
        return reverse("panel:premade_day_builder", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("panel:premade_days")


class PremadeDayUpdateView(PanelUpdateView):
    model = DayTemplate
    form_class = DayTemplateForm
    nav_active = "premade_days"
    page_title = _("Edit pre-made day")

    def get_success_url(self):
        return reverse("panel:premade_day_builder", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("panel:premade_day_builder", args=[self.object.pk])


class PremadeDayDeleteView(PanelDeleteView):
    model = DayTemplate
    nav_active = "premade_days"
    page_title = _("Delete pre-made day")
    success_url = reverse_lazy("panel:premade_days")


# ───────────────────────── Pre-made day builder ─────────────────────────

class PremadeDayBuilderView(StaffRequiredMixin, PanelContextMixin, TemplateView):
    """Visual exercise builder for a pre-made day. Mirrors the workout builder
    but has no weeks / progression — it just edits this day's exercises."""
    template_name = "panel/premade_day_builder.html"
    nav_active = "premade_days"

    def get_day(self):
        return get_object_or_404(DayTemplate, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        day = self.get_day()
        is_home = day.workout_type == WorkoutType.HOME

        added = list(day.exercises.select_related("exercise").all())
        ctx["added_json"] = [
            {
                "exercise_id": e.exercise_id,
                "name": e.exercise.name,
                "muscle": e.exercise.get_primary_body_part_display(),
                "thumb": e.exercise.thumbnail.url if e.exercise.thumbnail else "",
                "sets": e.sets,
                "reps": e.reps,
                "weight": e.recommended_weight or 0,
                "minutes": e.minutes or 0,
            }
            for e in added
        ]
        ctx.update({
            "day": day,
            "is_home": is_home,
            "page_title": _("Build pre-made day"),
            "obj_title": day.name,
            "back_url": reverse("panel:premade_days"),
            "breadcrumbs": [
                {"label": _("Pre-made days"), "url": reverse("panel:premade_days")},
                {"label": day.name},
            ],
            "exercises": Exercise.objects.filter(workout_type=day.workout_type).order_by("name"),
            "body_parts": MuscleGroup.choices,
        })
        return ctx

    def post(self, request, *args, **kwargs):
        day = self.get_day()
        is_home = day.workout_type == WorkoutType.HOME

        if is_home:
            try:
                day.rounds = max(1, int(request.POST.get("rounds") or day.rounds or 1))
                day.save(update_fields=["rounds"])
            except (TypeError, ValueError):
                pass

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
            if is_home:
                defaults.update({"minutes": _to_int(row.get("minutes")), "sets": 0, "reps": 0})
            else:
                defaults.update({
                    "sets": _to_int(row.get("sets")),
                    "reps": _to_int(row.get("reps")),
                    "recommended_weight": _to_float(row.get("weight")),
                })
            DayTemplateExercise.objects.update_or_create(
                day=day, exercise_id=eid, defaults=defaults,
            )

        # Drop exercises the admin removed.
        day.exercises.exclude(exercise_id__in=submitted_ids).delete()

        messages.success(request, _("Pre-made day saved."))
        return redirect("panel:premade_days")


# ───────────────────────── Attach a pre-made day to a plan week ─────────────────────────

class WorkoutFromTemplateView(StaffRequiredMixin, PanelContextMixin, TemplateView):
    """Pick a pre-made day and copy it into a new day (Workout) of this week.

    The copy creates real ``WorkoutExercise`` rows one-by-one, so the existing
    week-1 → weeks 2..N generation signal fires just like a hand-built day.
    """
    template_name = "panel/premade_day_attach.html"
    nav_active = "plans"

    def get_week(self):
        return get_object_or_404(Week.objects.select_related("plan__program"), pk=self.kwargs["week_pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        week = self.get_week()
        plan = week.plan
        wtype = plan.program.workout_type
        days = (
            DayTemplate.objects.filter(workout_type=wtype)
            .prefetch_related("exercises")
            .order_by("-created_at")
        )
        ctx.update({
            "week": week,
            "plan": plan,
            "page_title": _("Add from pre-made day"),
            "obj_title": f"{plan.name} · {week.display_name}",
            "back_url": reverse("panel:week_detail", args=[week.pk]),
            "breadcrumbs": [
                {"label": _("Plans"), "url": reverse("panel:plans")},
                {"label": plan.name, "url": reverse("panel:plan_detail", args=[plan.pk])},
                {"label": week.display_name, "url": reverse("panel:week_detail", args=[week.pk])},
                {"label": _("Add from pre-made day")},
            ],
            "days": days,
            "workout_type_label": _("Home") if wtype == WorkoutType.HOME else _("Gym"),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        week = self.get_week()
        plan = week.plan
        template = get_object_or_404(
            DayTemplate, pk=request.POST.get("day_template_id"),
            workout_type=plan.program.workout_type,
        )

        # New day in this week — same numbering / apply-to-all rule as a manual add.
        last = week.workouts.order_by("-day_number").first()
        workout = Workout.objects.create(
            week=week,
            day_number=(last.day_number + 1) if last else 1,
            title=template.name,
            title_uz=template.name_uz,
            title_ru=template.name_ru,
            rounds=template.rounds,
            apply_to_all_weeks=(week.week_number == 1),
        )

        # Copy each exercise via .create() (NOT bulk) so post_save generation runs.
        for tex in template.exercises.all().order_by("order", "id"):
            WorkoutExercise.objects.create(
                workout=workout,
                exercise_id=tex.exercise_id,
                sets=tex.sets,
                reps=tex.reps,
                recommended_weight=tex.recommended_weight,
                minutes=tex.minutes,
                order=tex.order,
            )

        messages.success(
            request,
            _("Pre-made day '%(name)s' added as day %(num)d.")
            % {"name": template.name, "num": workout.day_number},
        )
        return redirect("panel:workout_detail", pk=workout.pk)
