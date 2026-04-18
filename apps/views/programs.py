import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from apps.models import Program
# views/programs.py da:
from apps.services.programs import UserProgramService

class FirstLoginProgramAssignView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        assignment = UserProgramService.assign_auto_program_once(profile)
        if not assignment:
            return JsonResponse({"detail": "No matching admin program found."}, status=404)

        return JsonResponse(
            {
                "user_program_id": assignment.id,
                "program_id": assignment.program_id,
                "program_name": assignment.program.name,
                "is_active": assignment.is_active,
            }
        )


class CloneProgramView(LoginRequiredMixin, View):
    def post(self, request, program_id, *args, **kwargs):
        profile = request.user.profile
        source = Program.objects.get(id=program_id)
        payload = json.loads(request.body.decode("utf-8") or "{}")
        custom_name = payload.get("name")
        cloned = UserProgramService.clone_program_for_user(
            source_program=source,
            user_profile=profile,
            name=custom_name,
        )
        return JsonResponse({"program_id": cloned.id, "name": cloned.name, "type": cloned.type}, status=201)


class CreateCustomProgramView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        payload = json.loads(request.body.decode("utf-8") or "{}")

        program = Program.objects.create(
            name=payload["name"],
            type=Program.ProgramType.CUSTOM,
            created_by=profile,
            level=payload.get("level", Program.Level.BEGINNER),
            goal=payload.get("goal", Program.Goal.GENERAL),
            is_template=False,
            description=payload.get("description", ""),
            workout_type=payload.get("workout_type", "gym"),
        )
        return JsonResponse({"program_id": program.id, "name": program.name, "type": program.type}, status=201)
