from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.models import Plan, WorkoutExercise
from apps.services.programs import ProgramGenerationService


@receiver(post_save, sender=Plan)
def auto_create_plan_weeks(sender, instance, created, **kwargs):
	"""Plan yaratilganda 6 hafta avtomatik yaratiladi."""
	if created:
		ProgramGenerationService.ensure_plan_weeks(instance)


@receiver(post_save, sender=WorkoutExercise)
def auto_generate_workout_exercise_weeks(sender, instance, created, **kwargs):
	"""
	1-haftadagi seed mashq saqlanganda 2-6 haftalarga progression bilan
	avtomatik nusxa ko'chiradi.

	Shart: apply_to_all_weeks = True (workout darajasida)
	"""
	if not instance.is_week_one_seed:
		return
	
	# Workout (kun) dagi apply_to_all_weeks belgisini tekshirish
	if not instance.workout.apply_to_all_weeks:
		return
	
	ProgramGenerationService.generate_progression_from_week_one(instance)

