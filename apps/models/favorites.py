from apps.models.base import CreatedBaseModel
from django.db.models import (
    CASCADE,
    SET_NULL,
    BooleanField,
    CharField,
    FloatField,
    ForeignKey,
    IntegerField,
)
from django.utils.translation import gettext_lazy as _

class FavoriteCollection(CreatedBaseModel):
    user = ForeignKey('apps.UserProfile', CASCADE, related_name='favorite_collections')
    name = CharField(max_length=100, verbose_name="Collection Name")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Favorite Collection"
        verbose_name_plural = "Favorite Collections"
        unique_together = ['user', 'name']

    def __str__(self):
        return f"{self.user.name} - {self.name}"

    @property
    def exercise_count(self):
        return self.favorites.count()


class Favorite(CreatedBaseModel):
    user = ForeignKey('apps.UserProfile', CASCADE, related_name='favorites')
    exercise = ForeignKey('apps.Exercise', CASCADE, related_name='favorites')
    collection = ForeignKey('apps.FavoriteCollection', SET_NULL, null=True, blank=True, related_name='favorites')
    sets = IntegerField(default=3)
    reps = IntegerField(default=10)
    last_performed_weight = FloatField(null=True, blank=True)
    recommended_weight = FloatField(default=0)
    recommended_weight_week = IntegerField(default=1)
    progression_setting = ForeignKey("apps.ProgressionSetting", SET_NULL, null=True, blank=True, related_name="favorites")

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'exercise')
        verbose_name = _("Favorite")
        verbose_name_plural = _("Favorites")

    def __str__(self):
        return f"{self.user.name}"
    
    def save(self, *args, **kwargs):
        if self.last_performed_weight is not None:
            self.recommended_weight = self.last_performed_weight
        super().save(*args, **kwargs)

class FavoriteExercise(CreatedBaseModel):
    user = ForeignKey('apps.UserProfile', CASCADE, related_name='favorite_exercises')
    exercise = ForeignKey('apps.Exercise', CASCADE, related_name='favorited_by_users')

    class Meta:
        unique_together = ('user', 'exercise')
        ordering = ['-created_at']
        verbose_name = _("Favorite Exercise")
        verbose_name_plural = _("Favorite Exercises")

    def __str__(self):
        return f"{self.user} - {self.exercise}"


class FavoriteProgram(CreatedBaseModel):
    user = ForeignKey('apps.UserProfile', CASCADE, related_name='favorite_programs')
    program = ForeignKey('apps.Program', CASCADE, related_name='favorited_by_users')

    class Meta:
        unique_together = ('user', 'program')
        ordering = ['-created_at']
        verbose_name = _("Favorite Program")
        verbose_name_plural = _("Favorite Programs")

    def __str__(self):
        return f"{self.user} - {self.program}"


class UserCustomProgram(CreatedBaseModel):
    class GoalType:
        MUSCLE_GAIN = "mg"
        FAT_LOSS = "ft"
        RECOVERY = "rc"

        CHOICES = (
            (MUSCLE_GAIN, "Muscle Gain"),
            (FAT_LOSS, "Fat Loss"),
            (RECOVERY, "Recovery"),
        )

    user = ForeignKey("apps.UserProfile", CASCADE, related_name="custom_programs")
    name = CharField(max_length=100)
    goal = CharField(max_length=10, choices=GoalType.CHOICES)
    collection = ForeignKey("apps.FavoriteCollection", SET_NULL, null=True, blank=True)
    weeks = IntegerField(default=6)
    is_active = BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Custom Program")
        verbose_name_plural = _("Custom Programs")

    def __str__(self):
        return f"{self.user.name} - {self.name}"

    @property
    def total_exercises(self):
        if not self.collection_id:
            return 0
        return self.collection.exercise_count
