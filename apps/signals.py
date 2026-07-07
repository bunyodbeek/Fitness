from django.apps import apps as django_apps
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.models import WorkoutExercise
from apps.models.workouts import WorkoutType
from apps.services import image_optim
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


# ─────────────────────────────────────────────────────────────────────────────
# Upload-time WebP conversion for cover ImageFields (image_optim.WEBP_TARGETS).
# pre_save converts a freshly uploaded PNG/JPEG to the hero WebP; post_save writes
# the ≤400px thumb. Both are no-ops once the file is already .webp (idempotent),
# so ordinary re-saves cost nothing. Image optimisation never blocks a save.
# ─────────────────────────────────────────────────────────────────────────────
def _webp_fields_by_model():
	mapping = {}
	for app_label, model_name, field in image_optim.WEBP_TARGETS:
		try:
			model = django_apps.get_model(app_label, model_name)
		except LookupError:
			continue
		mapping.setdefault(model, []).append(field)
	return mapping


_WEBP_FIELDS = _webp_fields_by_model()


def _convert_hero_pre_save(sender, instance, **kwargs):
	for field in _WEBP_FIELDS.get(sender, ()):
		ff = getattr(instance, field, None)
		try:
			if ff and image_optim.is_convertible(ff.name):
				image_optim.replace_fieldfile_with_hero_webp(ff)
		except Exception:
			pass


def _ensure_thumb_post_save(sender, instance, **kwargs):
	for field in _WEBP_FIELDS.get(sender, ()):
		ff = getattr(instance, field, None)
		try:
			if ff and ff.name and ff.name.lower().endswith(".webp"):
				image_optim.ensure_thumb(ff)
		except Exception:
			pass


for _model in _WEBP_FIELDS:
	label = _model._meta.label
	pre_save.connect(_convert_hero_pre_save, sender=_model, dispatch_uid=f"webp_pre_{label}")
	post_save.connect(_ensure_thumb_post_save, sender=_model, dispatch_uid=f"webp_post_{label}")
