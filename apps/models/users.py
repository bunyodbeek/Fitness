from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db.models import (
    CASCADE,
    BigIntegerField,
    BooleanField,
    CharField,
    DateField,
    DecimalField,
    ForeignKey,
    ImageField,
    IntegerField,
    OneToOneField,
    TextChoices, TextField, PositiveIntegerField, Model, DateTimeField,
)

from apps.models.base import CreatedBaseModel
from apps.models.managers import UserManager


class User(AbstractUser):
    class RoleType(TextChoices):
        ADMIN = 'admin', 'Admin'
        MODERATOR = 'moderator', 'Moderator'
        USER = 'user', 'User'

    role = CharField(max_length=20, choices=RoleType.choices, default=RoleType.USER)

    objects = UserManager()


class UserProfile(CreatedBaseModel):
    class Gender(TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'

    class UnitSystem(TextChoices):
        METRIC = 'metric', 'Metric'
        ENGLISH = 'english', 'English'

    class ExperienceLevel(TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        ADVANCED = 'advanced', 'Advanced'

    class FitnessGoal(TextChoices):
        BUILD_BODY = 'build_body', 'Build a great body'
        LOSE_WEIGHT = 'lose_weight', 'Lose weight'
        GAIN_MUSCLE = 'gain_muscle', 'Gain muscle'
        GET_SHAPE = 'get_shape', 'Get in shape'

    user = OneToOneField('apps.User', CASCADE, related_name='profile')
    telegram_id = BigIntegerField(unique=True, null=True, blank=True)
    name = CharField(max_length=100, default='User')
    avatar = ImageField(upload_to='avatars/', blank=True, null=True)
    gender = CharField(max_length=10, choices=Gender.choices, default=Gender.MALE)
    birth_date = DateField(null=True, blank=True)
    weight = DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    height = DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    experience_level = CharField(max_length=20, choices=ExperienceLevel.choices, blank=True)
    fitness_goal = CharField(max_length=20, choices=FitnessGoal.choices, blank=True)
    workout_days_per_week = IntegerField(null=True, blank=True)
    unit_system = CharField(max_length=10, choices=UnitSystem.choices, default=UnitSystem.METRIC)
    onboarding_completed = BooleanField(default=False)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.name}"

    @property
    def is_premium(self) -> bool:
        subscription = getattr(self, "subscription", None)
        return bool(subscription and subscription.is_active)

    @property
    def age(self):
        if self.birth_date:
            today = date.today()
            is_before_birthday = (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            return today.year - self.birth_date.year - int(is_before_birthday)
        return None

    @property
    def bmi(self):
        if self.weight and self.height:
            height_m = float(self.height) / 100
            return round(float(self.weight) / (height_m ** 2), 1)
        return None


class UserMotivation(CreatedBaseModel):
    class MotivationType(TextChoices):
        HEALTHY_LIFESTYLE = 'healthy_lifestyle', 'I want a healthy lifestyle'
        IMPROVE_PHYSIQUE = 'improve_physique', 'Improve my physique'
        GET_STRONGER = 'get_stronger', 'Get stronger every day'
        GOOD_CHALLENGE = 'good_challenge', 'I like a good challenge'

    user = ForeignKey('apps.UserProfile', CASCADE, related_name='motivations')
    motivation = CharField(max_length=30, choices=MotivationType.choices)

    class Meta:
        unique_together = ['user', 'motivation']
        verbose_name = "User Motivation"
        verbose_name_plural = "User Motivations"

    def __str__(self):
        return f"{self.user.name} - {self.get_motivation_display()}"



class UserProgram(CreatedBaseModel):
    user = ForeignKey('apps.UserProfile', CASCADE, related_name='program_assignments')
    program = ForeignKey('apps.Program', CASCADE, related_name='user_assignments')
    is_active = BooleanField(default=True)
    assigned_once = BooleanField(default=False)

    class Meta:
        verbose_name = "User Program"
        verbose_name_plural = "User Programs"

    def __str__(self):
        return f"{self.user.name} - {self.program.name}"


class WorkoutDay(Model):
    class CompleteStatus(TextChoices):
        NOT_STARTED = 'not_started', 'Not started'
        UNFINISHED = 'unfinished', 'Unfinished'
        COMPLETED = 'completed', 'Completed'

    program = ForeignKey('apps.UserProgram', CASCADE, related_name='workout_days')
    status = CharField(max_length=20, choices=CompleteStatus.choices, default=CompleteStatus.NOT_STARTED)
    order = PositiveIntegerField()
    title = CharField(max_length=100)
    body_part = CharField(max_length=100)
    completed_at = DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = ('program', 'order')

    def __str__(self):
        return f"day - {self.order} - {self.program}"


class UserProgramExercise(Model):
    day = ForeignKey('apps.WorkoutDay', CASCADE, related_name='exercises')
    exercise = ForeignKey('apps.Exercise', CASCADE)
    sets = PositiveIntegerField()
    reps = PositiveIntegerField()
