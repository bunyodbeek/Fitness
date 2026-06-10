from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.models import Program
from apps.services.programs import UserProgramService


class GenerateShareLinkView(LoginRequiredMixin, View):
    """POST — generate (or return existing) share token for a program the user owns.
    Returns JSON: {token, url}."""

    def post(self, request, pk):
        program = get_object_or_404(Program, pk=pk)
        profile = getattr(request.user, "profile", None)

        if program.created_by_id != getattr(profile, "pk", None):
            return JsonResponse({"error": _("Forbidden")}, status=403)

        token = UserProgramService.get_or_create_share_token(program)

        bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
        if bot_username:
            share_url = f"https://t.me/{bot_username}?startapp=import_{token}"
        else:
            # Fallback to direct HTTPS link if bot username not configured
            lang = get_language() or "uz"
            share_url = f"{settings.WEBAPP_URL}/{lang}/programs/import/{token}/"

        return JsonResponse({"token": token, "url": share_url})


class ImportProgramEntryView(LoginRequiredMixin, TemplateView):
    """GET — one input field where the user pastes a share code or full link."""

    template_name = "workouts/import_entry.html"


class ImportProgramPreviewView(LoginRequiredMixin, View):
    """GET — preview a program before importing.
    POST — confirm import, clone program, redirect to detail."""

    def _get_program(self, token: str):
        return get_object_or_404(Program, share_token=token)

    def get(self, request, token):
        program = self._get_program(token)
        profile = getattr(request.user, "profile", None)

        plan_count = program.plans.count()
        day_count = sum(
            week.workouts.count()
            for plan in program.plans.prefetch_related("weeks__workouts")
            for week in plan.weeks.filter(week_number=1)
        )
        exercise_count = sum(
            workout.workout_exercises.count()
            for plan in program.plans.prefetch_related(
                "weeks__workouts__workout_exercises"
            )
            for week in plan.weeks.filter(week_number=1)
            for workout in week.workouts.all()
        )

        owner = program.created_by
        owner_name = owner.name if owner else _("Unknown")

        context = {
            "program": program,
            "token": token,
            "plan_count": plan_count,
            "day_count": day_count,
            "exercise_count": exercise_count,
            "owner_name": owner_name,
            "is_premium": bool(profile and profile.is_premium),
        }
        return render(request, "workouts/import_preview.html", context)

    def post(self, request, token):
        profile = request.user.profile
        if not profile.is_premium:
            lang = get_language() or "uz"
            return redirect(f"/{lang}/premium/")

        program = self._get_program(token)
        cloned = UserProgramService.clone_program(program, profile)
        messages.success(request, _("Program successfully imported!"))
        return redirect("program_detail", pk=cloned.pk)