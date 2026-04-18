from apps.models.favorites import Favorite, FavoriteExercise, FavoriteProgram
from apps.models.users import  UserProfile
from apps.models.favorites import FavoriteCollection
from django.contrib import admin

from apps.models.users import UserProgram, WorkoutDay, UserProgramExercise


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'gender', 'age', 'weight', 'height', 'bmi']
    search_fields = ['name', 'user__username', 'user__email']
    readonly_fields = ['age', 'bmi', 'created_at', 'updated_at']


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'exercise', 'sets', 'reps', 'last_performed_weight', 'recommended_weight', 'progression_setting']


@admin.register(FavoriteCollection)
class FavoriteCollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'exercise_count', 'created_at']
    list_filter = ['created_at']


@admin.register(FavoriteExercise)
class FavoriteExerciseAdmin(admin.ModelAdmin):
    list_display = ["user", "exercise", "created_at"]
    search_fields = ["user__name", "exercise__name"]


@admin.register(FavoriteProgram)
class FavoriteProgramAdmin(admin.ModelAdmin):
    list_display = ["user", "program", "created_at"]
    search_fields = ["user__name", "program__name"]


@admin.register(UserProgram)
class UserProgramAdmin(admin.ModelAdmin):
    list_display = ['user', 'program', 'assigned_once', 'is_active']

@admin.register(WorkoutDay)
class WorkoutDayAdmin(admin.ModelAdmin):
    list_display = ['program', 'order', 'body_part']

@admin.register(UserProgramExercise)
class UserProgramExerciseAdmin(admin.ModelAdmin):
    list_display = ['day', 'exercise']
