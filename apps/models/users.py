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
from django.utils.translation import gettext_lazy as _

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
        MALE   = 'male',   _('Male')
        FEMALE = 'female', _('Female')

    class UnitSystem(TextChoices):
        METRIC  = 'metric',  _('Metric')
        ENGLISH = 'english', _('English')

    class ExperienceLevel(TextChoices):
        BEGINNER = 'beginner', _('Beginner')
        ADVANCED = 'advanced', _('Advanced')

    class FitnessGoal(TextChoices):
        BUILD_BODY  = 'build_body',  _('Build a great body')
        LOSE_WEIGHT = 'lose_weight', _('Lose weight')
        GAIN_MUSCLE = 'gain_muscle', _('Gain muscle')
        GET_SHAPE   = 'get_shape',   _('Get in shape')

    user         = OneToOneField('apps.User', CASCADE, related_name='profile')
    telegram_id  = BigIntegerField(unique=True, null=True, blank=True)
    name         = CharField(_('Name'), max_length=100, default='User')
    avatar       = ImageField(_('Avatar'), upload_to='avatars/', blank=True, null=True)
    gender       = CharField(_('Gender'), max_length=10, choices=Gender.choices, default=Gender.MALE)
    birth_date   = DateField(_('Birth date'), null=True, blank=True)
    weight       = DecimalField(_('Weight'), max_digits=5, decimal_places=1, null=True, blank=True)
    height       = DecimalField(_('Height'), max_digits=5, decimal_places=1, null=True, blank=True)
    experience_level     = CharField(_('Experience level'), max_length=20, choices=ExperienceLevel.choices, blank=True)
    fitness_goal         = CharField(_('Fitness goal'), max_length=20, choices=FitnessGoal.choices, blank=True)
    workout_days_per_week = IntegerField(_('Workout days per week'), null=True, blank=True)
    unit_system          = CharField(_('Unit system'), max_length=10, choices=UnitSystem.choices, default=UnitSystem.METRIC)
    onboarding_completed = BooleanField(_('Onboarding completed'), default=False)

    class Meta:
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')

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
        HEALTHY_LIFESTYLE = 'healthy_lifestyle', _('I want a healthy lifestyle')
        IMPROVE_PHYSIQUE  = 'improve_physique',  _('Improve my physique')
        GET_STRONGER      = 'get_stronger',      _('Get stronger every day')
        GOOD_CHALLENGE    = 'good_challenge',    _('I like a good challenge')

    user       = ForeignKey('apps.UserProfile', CASCADE, related_name='motivations')
    motivation = CharField(_('Motivation'), max_length=30, choices=MotivationType.choices)

    class Meta:
        unique_together = ['user', 'motivation']
        verbose_name = _('User Motivation')
        verbose_name_plural = _('User Motivations')

    def __str__(self):
        return f"{self.user.name} - {self.get_motivation_display()}"


class UserProgram(CreatedBaseModel):
    user          = ForeignKey('apps.UserProfile', CASCADE, related_name='program_assignments')
    program       = ForeignKey('apps.Program', CASCADE, related_name='user_assignments')
    is_active     = BooleanField(_('Is active'), default=True)
    assigned_once = BooleanField(_('Assigned once'), default=False)

    class Meta:
        verbose_name = _('User Program')
        verbose_name_plural = _('User Programs')

    def __str__(self):
        return f"{self.user.name} - {self.program.name}"


class WorkoutDay(Model):
    class CompleteStatus(TextChoices):
        NOT_STARTED = 'not_started', _('Not started')
        UNFINISHED  = 'unfinished',  _('Unfinished')
        COMPLETED   = 'completed',   _('Completed')

    program      = ForeignKey('apps.UserProgram', CASCADE, related_name='workout_days')
    status       = CharField(_('Status'), max_length=20, choices=CompleteStatus.choices, default=CompleteStatus.NOT_STARTED)
    order        = PositiveIntegerField(_('Order'))
    title        = CharField(_('Title'), max_length=100)
    body_part    = CharField(_('Body part'), max_length=100)
    completed_at = DateTimeField(_('Completed at'), auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = ('program', 'order')

    def __str__(self):
        return f"day - {self.order} - {self.program}"


class UserProgramExercise(Model):
    day      = ForeignKey('apps.WorkoutDay', CASCADE, related_name='exercises')
    exercise = ForeignKey('apps.Exercise', CASCADE)
    sets     = PositiveIntegerField(_('Sets'))
    reps     = PositiveIntegerField(_('Reps'))