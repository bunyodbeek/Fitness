from apps.models import Exercise, ExerciseInstruction
from apps.models.exercises import MuscleGroup
from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class ExerciseInstructionInline(admin.TabularInline):
    model = ExerciseInstruction
    extra = 1


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "workout_type", "name_ru", "name_uz", "primary_body_part", "calory")
    list_filter = ("workout_type", "primary_body_part")
    search_fields = ("name", "name_ru", "name_uz")
    fieldsets = (
        (None, {
            "fields": (
                "workout_type",
                "primary_body_part",
                "calory",
                "duration",
                "recommended_weight",
            )
        }),
        (_("Titles"), {
            "fields": ("name", "name_uz", "name_ru")
        }),
        (_("Descriptions"), {
            "fields": (
                "description",
                "description_uz",
                "description_ru",
            )
        }),
        (_("Media"), {
            "fields": ("thumbnail", "video")
        }),
    )
    inlines = [ExerciseInstructionInline]

    @staticmethod
    def _normalize_muscle_group(raw_value):
        if not raw_value:
            return ""

        normalized = str(raw_value).strip()
        if normalized.lower().startswith("musclegroup."):
            normalized = normalized.split(".", 1)[1]

        return normalized.strip()

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        normalized_group = self._normalize_muscle_group(request.GET.get("muscle_group"))
        if normalized_group:
            queryset = queryset.filter(primary_body_part__iexact=normalized_group)

        return queryset, use_distinct
