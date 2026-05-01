from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.models import WorkoutExercise
from apps.models.workouts import WorkoutType
from apps.services.programs import ProgramGenerationService


@receiver(post_save, sender=WorkoutExercise)
def auto_generate_workout_exercise_weeks(sender, instance, created, **kwargs):
	"""
	1-haftadagi seed mashq saqlanganda 2-6 haftalarga progression bilan
	avtomatik nusxa ko'chiradi.

	Shart: apply_to_all_weeks = True (workout darajasida)
	Gym va Home uchun alohida progression generators chaqiriladi.
	"""
	if not instance.is_week_one_seed:
		return
	
	# Workout (kun) dagi apply_to_all_weeks belgisini tekshirish
	if not instance.workout.apply_to_all_weeks:
		return
	
	# Workout type ga qarab alohida progression generator chaqirish
	workout_type = instance.workout.week.plan.program.workout_type
	
	if workout_type == WorkoutType.HOME:
		ProgramGenerationService.generate_home_progression_from_week_one(instance)
	else:
		# Gym workout - default progression
		ProgramGenerationService.generate_progression_from_week_one(instance)
