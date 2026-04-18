from django.core.exceptions import ValidationError
from django.db.models import (
	CASCADE,
	SET_NULL,
	BooleanField,
	CharField,
	FloatField,
	ForeignKey,
	ImageField,
	IntegerField,
	Model,
	TextChoices,
	TextField, PositiveIntegerField,
)
from django.db.models.fields import DateTimeField
from django.utils.translation import gettext_lazy as _

from apps.models.base import CreatedBaseModel


class WorkoutType(TextChoices):
	GYM = "gym", "Gym"
	HOME = "home", "Home"


class Program(CreatedBaseModel):
	class ProgramType(TextChoices):
		ADMIN = "admin", "Admin"
		AUTO = "auto", "Auto"
		CUSTOM = "custom", "Custom"
	
	name = CharField(max_length=200)  # Bu name_en bo'lib xizmat qiladi
	name_uz = CharField(max_length=200, blank=True)
	name_ru = CharField(max_length=200, blank=True)
	
	description = TextField(blank=True)  # Bu description_en
	description_uz = TextField(blank=True)
	description_ru = TextField(blank=True)
	
	class Level(TextChoices):
		BEGINNER = "beginner", "Beginner"
		INTERMEDIATE = "intermediate", "Intermediate"
		ADVANCED = "advanced", "Advanced"
	
	class Goal(TextChoices):
		FAT_LOSS = "fat_loss", "Fat loss"
		MUSCLE_GAIN = "muscle_gain", "Muscle gain"
		RECOMPOSITION = "recomposition", "Recomposition"
		GENERAL = "general", "General fitness"
	
	type = CharField(max_length=20, choices=ProgramType.choices, default=ProgramType.ADMIN)
	created_by = ForeignKey("apps.UserProfile", SET_NULL, null=True, blank=True, related_name="created_programs")
	level = CharField(max_length=20, choices=Level.choices, default=Level.BEGINNER)
	goal = CharField(max_length=20, choices=Goal.choices, default=Goal.GENERAL)
	is_template = BooleanField(default=True)
	
	# Backward-compatible fields kept for current templates/admin screens
	image = ImageField(upload_to="programs/", blank=True, null=True)
	is_active = BooleanField(default=True)
	is_premium = BooleanField(_("Premium"), default=False)
	workout_type = CharField(max_length=10, choices=WorkoutType.choices, default=WorkoutType.GYM)
	
	class Meta:
		verbose_name = "Program"
		verbose_name_plural = "Programs"
	
	def __str__(self):
		return self.name
	
	@property
	def title(self):
		return self.name


class Plan(CreatedBaseModel):
	program = ForeignKey("apps.Program", CASCADE, related_name="plans")
	name = CharField(max_length=200)
	name_uz = CharField(max_length=200, blank=True)
	name_ru = CharField(max_length=200, blank=True)
	
	description = TextField(blank=True)  # Bu description_en
	description_uz = TextField(blank=True)
	description_ru = TextField(blank=True)
	order = IntegerField(default=1)
	weeks_count = IntegerField(default=6)
	is_premium = BooleanField(default=False, verbose_name="Premium Plan")
	progression_config = ForeignKey(
		"apps.ProgressionSetting",
		SET_NULL,
		null=True,
		blank=True,
		verbose_name="Progression Rules"
	)
	
	class Meta:
		ordering = ["order", "id"]
		verbose_name = "Plan"
		verbose_name_plural = "Plans"
	
	def __str__(self):
		return f"{self.program.name} - {self.name}"
	
	def clean(self):
		if self.weeks_count != 6:
			raise ValidationError("Plan must contain exactly 6 weeks.")


class Edition(Plan):
	class Meta:
		proxy = True
		verbose_name = "Plan"
		verbose_name_plural = "Plans"


class GymPlan(Edition):
	class Meta:
		proxy = True
		verbose_name = "Gym Plan"
		verbose_name_plural = "Gym Plans"


class HomePlan(Edition):
	class Meta:
		proxy = True
		verbose_name = "Home Plan"
		verbose_name_plural = "Home Plans"


class Week(Model):
	plan = ForeignKey("apps.Plan", CASCADE, related_name="weeks")
	week_number = IntegerField()
	
	class Meta:
		ordering = ["week_number"]
		unique_together = ("plan", "week_number")
	
	def clean(self):
		if self.week_number < 1 or self.week_number > 6:
			raise ValidationError("Week number must be between 1 and 6.")
	
	# MODEL ICHIGA OLINDI
	@property
	def display_name(self):
		return f"Week {self.week_number}"
	
	def __str__(self):
		return f"{self.plan.name} - Week {self.week_number}"


class Workout(CreatedBaseModel):
	week = ForeignKey("apps.Week", CASCADE, related_name="workouts")
	day_number = IntegerField(default=1)
	title = CharField(max_length=255, blank=True, null=True)
	title_uz = CharField(max_length=255, blank=True, null=True)
	title_ru = CharField(max_length=255, blank=True, null=True)
	
	description = TextField(blank=True, default="")
	description_uz = TextField(blank=True, default="")
	description_ru = TextField(blank=True, default="")
	
	rounds = IntegerField(default=1)
	
	# SIZ SO'RAGAN GALOCHKA:
	# Bu faqat 1-haftadagi mashg'ulotlar uchun ishlatiladi
	apply_to_all_weeks = BooleanField(
		default=False,
		verbose_name="Apply to all 6 weeks",
		help_text="Belgilansa, ushbu kun mashqlari 2-6 haftalarga progression bilan nusxalanadi."
	)
	
	class Meta:
		verbose_name = "Workout"
		verbose_name_plural = "Workouts"
		ordering = ["day_number", "id"]
	
	def __str__(self):
		return f"{self.week} - {self.title or f'Day {self.day_number}'}"


class GymWorkout(Workout):
	class Meta:
		proxy = True
		verbose_name = "Gym Workout"
		verbose_name_plural = "Gym Workouts"


class HomeWorkout(Workout):
	class Meta:
		proxy = True
		verbose_name = "Home Workout"
		verbose_name_plural = "Home Workouts"


class ProgressionSetting(Model):
	"""
	Google Sheets SETTINGS tabiga to'liq mos keladi.
	KEY = goal + gender + level  (masalan: "FLMaleBeginner")
	"""
	key = CharField(max_length=64, unique=True)
	
	# Weight multipliers (har hafta uchun alohida)
	w2_weight_mult = FloatField(default=1.06, verbose_name="W2 weight multiplier")
	w3_weight_mult = FloatField(default=1.12, verbose_name="W3 weight multiplier")
	w4_weight_mult = FloatField(default=1.18, verbose_name="W4 weight multiplier")
	w5_weight_mult = FloatField(default=1.22, verbose_name="W5 weight multiplier")
	w6_deload_mult = FloatField(default=0.85, verbose_name="W6 deload multiplier")
	
	# Sets increment (har hafta uchun alohida)
	set_w2 = IntegerField(default=1, verbose_name="Sets +/- W2")
	set_w3 = IntegerField(default=1, verbose_name="Sets +/- W3")
	set_w4 = IntegerField(default=0, verbose_name="Sets +/- W4")
	set_w5 = IntegerField(default=0, verbose_name="Sets +/- W5")
	set_w6 = IntegerField(default=0, verbose_name="Sets +/- W6 (deload)")
	
	# Reps increment (har hafta uchun alohida)
	rep_w2 = IntegerField(default=0, verbose_name="Reps +/- W2")
	rep_w3 = IntegerField(default=-1, verbose_name="Reps +/- W3")
	rep_w4 = IntegerField(default=0, verbose_name="Reps +/- W4")
	rep_w5 = IntegerField(default=-1, verbose_name="Reps +/- W5")
	rep_w6 = IntegerField(default=-2, verbose_name="Reps +/- W6 (deload)")
	
	# Small weight threshold va boost (Sheets col 17, 18)
	small_threshold = FloatField(default=25.0, verbose_name="Small weight threshold (kg)")
	small_boost = FloatField(default=5.0, verbose_name="Small weight boost (kg)")
	
	class Meta:
		verbose_name = "Progression Setting"
		verbose_name_plural = "Progression Settings"
	
	def __str__(self):
		return self.key


class WorkoutExercise(Model):
	workout = ForeignKey("apps.Workout", CASCADE, related_name="workout_exercises")
	exercise = ForeignKey("apps.Exercise", CASCADE, related_name="workout_exercises")
	sets = IntegerField(default=0)
	reps = IntegerField(default=0)
	recommended_weight = FloatField(default=0, null=True, blank=True)
	order = IntegerField(default=0)
	minutes = PositiveIntegerField(
		default=0,
		blank=True,
		null=True,
		verbose_name="Davomiyligi (minutda)"
	)
	source_week_one = ForeignKey("self", SET_NULL, null=True, blank=True, related_name="generated_weeks")
	
	class Meta:
		ordering = ["order", "id"]
	
	def __str__(self):
		return f"{self.workout} - {self.exercise}"
	
	@property
	def is_week_one_seed(self):
		return self.workout.week.week_number == 1 and self.source_week_one_id is None


class WorkoutProgress(Model):
	class Status(TextChoices):
		IN_PROGRESS = "in_progress", _("In progress")
		COMPLETED = "completed", _("Completed")
	
	user = ForeignKey("apps.UserProfile", on_delete=CASCADE)
	workout = ForeignKey("apps.Workout", on_delete=CASCADE)
	total_calories = FloatField(default=0)
	total_duration_seconds = IntegerField(default=0)
	exercises_completed = IntegerField(default=0)
	status = CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
	current_exercise_index = IntegerField(default=0)
	current_set = IntegerField(default=1)
	updated_at = DateTimeField(auto_now=True)
	completed_at = DateTimeField(auto_now_add=True)
	
	def __str__(self):
		return f"{self.user} - {self.workout} progress"


class UserWorkoutProgress(Model):
	user = ForeignKey("apps.UserProfile", on_delete=CASCADE, related_name="home_workout_progresses")
	workout = ForeignKey("apps.Workout", on_delete=CASCADE, related_name="user_progresses")
	current_round = IntegerField(default=1)
	current_order = IntegerField(default=1)
	is_finished = BooleanField(default=False)
	updated_at = DateTimeField(auto_now=True)
	
	class Meta:
		unique_together = ("user", "workout")
	
	def __str__(self):
		return f"{self.user} - {self.workout} home progress"

