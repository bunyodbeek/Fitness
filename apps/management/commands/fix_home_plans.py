from django.core.management.base import BaseCommand
from apps.models import Plan
from apps.models.workouts import WorkoutType
from apps.services.programs import ProgramGenerationService


class Command(BaseCommand):
    help = "Mavjud Home planlarni tuzatish"

    def handle(self, *args, **options):
        plans = Plan.objects.filter(program__workout_type=WorkoutType.HOME)
        for plan in plans:
            self.stdout.write(f"Fixing: {plan}")
            ProgramGenerationService.ensure_plan_weeks(plan)
            ProgramGenerationService.ensure_home_plan_integrity(plan)
            self.stdout.write(self.style.SUCCESS(f"  OK: {plan}"))
        self.stdout.write(self.style.SUCCESS("Done!"))
