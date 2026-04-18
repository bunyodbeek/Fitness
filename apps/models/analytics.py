from apps.models.base import CreatedBaseModel
from django.db.models import CASCADE, CharField, ForeignKey, JSONField, TextChoices
from django.utils.translation import gettext_lazy as _


class UserActivity(CreatedBaseModel):
    class EventChoices(TextChoices):
        BOT_STARTED = 'bot_started', _('Bot Started')
        ONBOARDING_COMPLETED = 'onboarding_completed', _('Onboarding Completed')
        WORKOUT_STARTED = 'workout_started', _('Workout Started')
        WORKOUT_COMPLETED = 'workout_completed', _('Workout Completed')
        EXERCISE_VIEWED = 'exercise_viewed', _('Exercise Viewed')
        EXERCISE_FAVOURITED = 'exercise_favourited', _('Exercise Favourited')
        SUBSCRIPTION_VIEWED = 'subscription_viewed', _('Subscription Viewed')
        PAYMENT_COMPLETED = 'payment_completed', _('Payment Completed')

    user = ForeignKey('apps.UserProfile', CASCADE, related_name='activities')
    event = CharField(max_length=50, choices=EventChoices.choices, default=EventChoices.BOT_STARTED)

    metadata = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _('UserActivity')
        verbose_name_plural = _('UserActivities')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.telegram_id} - {self.get_event_display()}"
