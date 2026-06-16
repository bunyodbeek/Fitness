"""ModelForms used by the panel CRUD pages."""
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.models import Exercise, Plan, Program, User, UserProfile, Week, Workout, WorkoutExercise
from apps.models.handbook import HandbookCategory, HandbookItem, HandbookSubCategory
from apps.models.payments import Subscription, SubscriptionPlan
from apps.models.workouts import HomeProgressionSetting, ProgressionSetting, WorkoutProgress


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            "name", "telegram_id", "gender", "birth_date", "weight", "height",
            "experience_level", "fitness_goal", "workout_days_per_week",
            "unit_system", "avatar", "onboarding_completed",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ["user", "plan", "is_active"]


class WorkoutProgressForm(forms.ModelForm):
    class Meta:
        model = WorkoutProgress
        fields = [
            "user", "workout", "status", "total_calories",
            "total_duration_seconds", "exercises_completed",
        ]


# ───────────────────────── Content: program hierarchy ─────────────────────────

class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = [
            "name", "name_uz", "name_ru",
            "description", "description_uz", "description_ru",
            "image", "workout_type", "level", "goal", "type",
            "is_active", "is_premium", "is_template", "is_individual", "is_one_time",
        ]


class PlanForm(forms.ModelForm):
    """Plan create/edit. Program is chosen here (Plans is its own section).

    Progression rule is NOT selected here anymore — it is picked later in the
    workout builder (per the program's mode: gym vs home).
    """
    class Meta:
        model = Plan
        fields = [
            "program", "name", "name_uz", "name_ru", "description",
            "order", "weeks_count", "is_premium", "is_4_week",
        ]


class WeekForm(forms.ModelForm):
    generate_remaining_weeks = forms.BooleanField(
        required=False,
        label=_("Generate remaining weeks (up to the plan's week count)"),
        help_text=_("If checked, the missing weeks after this one are created automatically."),
    )

    class Meta:
        model = Week
        fields = ["week_number"]


class WorkoutForm(forms.ModelForm):
    """Workout (day) create/edit (week is set from the URL)."""
    class Meta:
        model = Workout
        fields = ["day_number", "title", "title_uz", "title_ru", "rounds", "apply_to_all_weeks"]


class WorkoutExerciseForm(forms.ModelForm):
    """Exercise inside a workout (workout is set from the URL).

    Saving here triggers the existing progression signals (week-1 +
    apply_to_all_weeks generates weeks 2..N) — that logic is untouched.
    """
    class Meta:
        model = WorkoutExercise
        fields = ["exercise", "sets", "reps", "recommended_weight", "minutes", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["minutes"].required = False
        self.fields["recommended_weight"].required = False


# ───────────────────────── Content: exercise library ─────────────────────────

class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = [
            "name", "name_ru", "name_uz",
            "description", "description_ru", "description_uz",
            "primary_body_part", "thumbnail", "video",
            "calory", "duration", "recommended_weight", "workout_type",
        ]


# ───────────────────────── Content: progression rules ─────────────────────────

class ProgressionSettingForm(forms.ModelForm):
    """Gym progression (sets / reps / weight growth per week). Also used by
    custom programs (same rules as gym)."""
    class Meta:
        model = ProgressionSetting
        fields = [
            "key",
            "w2_weight_mult", "w3_weight_mult", "w4_weight_mult", "w5_weight_mult", "w6_deload_mult",
            "set_w2", "set_w3", "set_w4", "set_w5", "set_w6",
            "rep_w2", "rep_w3", "rep_w4", "rep_w5", "rep_w6",
            "small_threshold", "small_boost",
        ]


class HomeProgressionSettingForm(forms.ModelForm):
    """Home progression (rounds / time / rest growth per week)."""
    class Meta:
        model = HomeProgressionSetting
        fields = [
            "key",
            "round_w2", "round_w3", "round_w4",
            "duration_w2", "duration_w3", "duration_w4",
            "rest_between_rounds", "rest_w2", "rest_w3", "rest_w4",
        ]


# ───────────────────────── Content: handbook ─────────────────────────

class HandbookCategoryForm(forms.ModelForm):
    class Meta:
        model = HandbookCategory
        fields = [
            "title", "title_uz", "title_ru", "title_en",
            "description", "description_uz", "description_ru",
            "cover_image", "icon", "order", "is_active",
        ]


class HandbookSubCategoryForm(forms.ModelForm):
    """Subcategory (category set from the URL)."""
    class Meta:
        model = HandbookSubCategory
        fields = [
            "title", "title_uz", "title_ru", "title_en",
            "description", "description_uz", "description_ru",
            "image", "order", "is_active",
        ]


class HandbookItemForm(forms.ModelForm):
    class Meta:
        model = HandbookItem
        fields = [
            "category", "subcategory",
            "title", "title_uz", "title_ru", "title_en",
            "short_description", "description", "description_uz", "description_ru",
            "main_image", "video", "tags", "order", "is_active",
        ]


# ───────────────────────── Finance / system ─────────────────────────

class SubscriptionPlanForm(forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = ["period", "price_uzs", "price_usd", "is_popular", "is_active", "order"]


class AdminUserForm(forms.ModelForm):
    """Create/edit a staff user. Password is optional on edit."""
    password = forms.CharField(
        label=_("Password"), required=False, widget=forms.PasswordInput,
        help_text=_("Leave blank to keep the current password."),
    )

    class Meta:
        model = User
        fields = ["username", "email", "role", "is_staff", "is_superuser", "is_active"]

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user
