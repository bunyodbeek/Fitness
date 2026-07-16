"""ModelForms used by the panel CRUD pages."""
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.models import Exercise, Plan, Program, User, UserProfile, Week, Workout, WorkoutExercise
from apps.models.handbook import HandbookCategory, HandbookItem, HandbookSubCategory
from apps.models.payments import Subscription, SubscriptionPlan
from apps.models.workouts import DayTemplate, HomeProgressionSetting, ProgressionSetting, WorkoutProgress


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
    # NOTE: no ``is_premium`` — hierarchy programs are gated structurally
    # ("first plan's week 1 is free, everything else premium"), so the checkbox
    # is meaningless here. Only OneTimeProgramForm still exposes it.
    class Meta:
        model = Program
        fields = [
            "name", "name_uz", "name_ru",
            "description", "description_uz", "description_ru",
            "image", "workout_type", "level", "goal",
            "is_active",
        ]


class IndividualProgramForm(forms.ModelForm):
    """Individual (recommended) program. `is_individual` is forced in the view.
    Goal / level / workout_type drive the first-login recommendation match."""
    class Meta:
        model = Program
        fields = [
            "name", "name_uz", "name_ru",
            "description", "description_uz", "description_ru",
            "image", "workout_type", "level", "goal", "is_active",
        ]


class OneTimeProgramForm(forms.ModelForm):
    """One-time (single session) program — just a name + image. Exercises (with
    sets / reps / weight) are added afterwards in the builder; no plan/week/days."""
    class Meta:
        model = Program
        fields = [
            "name", "name_uz", "name_ru", "description",
            "image", "workout_type", "is_active", "is_premium",
        ]


class PlanForm(forms.ModelForm):
    """Plan create/edit. Program is chosen here (Plans is its own section).

    The progression rule is chosen here, right below the week count. Fill the one
    that matches the program's mode (Gym rule for gym programs, Home rule for home
    programs) — the week 2..N generator reads it when week-1 days are saved, so
    every day in every week gets its progressed copy automatically.

    ``difficulty`` (beginner/advanced) selects which start weight/time each
    exercise contributes; changing it later recomputes the stored weekly values.
    """
    class Meta:
        model = Plan
        fields = [
            "program", "name", "name_uz", "name_ru", "description",
            "order", "weeks_count", "difficulty",
            "progression_config", "home_progression_config",
            "is_4_week",
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
    """Workout (day) create/edit (week is set from the URL).

    `day_number` is auto-assigned (next free day) and `apply_to_all_weeks` is set
    automatically for week-1 days, so admins can add as many days as they want.
    """
    class Meta:
        model = Workout
        fields = ["title", "title_uz", "title_ru", "rounds"]


class WorkoutExerciseForm(forms.ModelForm):
    """Exercise inside a workout (workout is set from the URL).

    Saving here triggers the existing progression signals (week-1 +
    apply_to_all_weeks generates weeks 2..N) — that logic is untouched.
    """
    class Meta:
        model = WorkoutExercise
        fields = ["exercise", "sets", "reps", "recommended_weight", "minutes", "order", "is_weight_manual"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["minutes"].required = False
        self.fields["recommended_weight"].required = False
        self.fields["is_weight_manual"].required = False
        self.fields["is_weight_manual"].label = _(
            "Manual weight — keep this value on difficulty change / regeneration"
        )
        self.fields["is_weight_manual"].help_text = _(
            "Auto-enabled when you change the weight. Untick (without changing "
            "the weight) to hand it back to automatic calculation."
        )


# ───────────────────────── Content: pre-made days ─────────────────────────

class DayTemplateForm(forms.ModelForm):
    """Pre-made day (standalone). Type (gym/home) decides which inputs the
    builder shows and which plans it can later be attached to. Exercises are
    added afterwards in the builder."""
    class Meta:
        model = DayTemplate
        fields = ["name", "name_uz", "name_ru", "workout_type"]


# ───────────────────────── Content: exercise library ─────────────────────────

class ExerciseForm(forms.ModelForm):
    # Progression fields (below) apply to GYM exercises only. HOME exercises hide
    # them (JS) and the values are cleared on save.
    PROGRESSION_FIELDS = [
        "exercise_type",
        "start_weight_beginner", "start_weight_advanced",
        "weekly_weight_increment_beginner", "weekly_weight_increment_advanced",
        "start_time_beginner", "start_time_advanced",
        "weekly_time_increment_beginner", "weekly_time_increment_advanced",
    ]

    class Meta:
        model = Exercise
        fields = [
            "name", "name_ru", "name_uz",
            "description", "description_ru", "description_uz",
            "primary_body_part", "thumbnail", "video",
            "calory", "duration", "workout_type",
            "exercise_type",
            "start_weight_beginner", "start_weight_advanced",
            "weekly_weight_increment_beginner", "weekly_weight_increment_advanced",
            "start_time_beginner", "start_time_advanced",
            "weekly_time_increment_beginner", "weekly_time_increment_advanced",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `start_weight_beginner` keeps the legacy DB verbose ("Recommended
        # weight (W1)") so the rename stayed a clean RenameField — relabel here.
        self.fields["start_weight_beginner"].label = _("Start weight — beginner (kg)")
        # Progression is validated conditionally in clean(), so nothing is
        # required at the widget level.
        for name in self.PROGRESSION_FIELDS:
            self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        workout_type = cleaned.get("workout_type")
        exercise_type = cleaned.get("exercise_type")

        weight_fields = [
            "start_weight_beginner", "start_weight_advanced",
            "weekly_weight_increment_beginner", "weekly_weight_increment_advanced",
        ]
        time_fields = [
            "start_time_beginner", "start_time_advanced",
            "weekly_time_increment_beginner", "weekly_time_increment_advanced",
        ]

        if workout_type == Exercise.WorkoutType.GYM:
            if exercise_type == Exercise.ExerciseType.REPS_BASED:
                for name in weight_fields:
                    if cleaned.get(name) in (None, ""):
                        self.add_error(name, _("Required for reps-based exercises."))
            elif exercise_type == Exercise.ExerciseType.TIME_BASED:
                for name in time_fields:
                    if cleaned.get(name) in (None, ""):
                        self.add_error(name, _("Required for time-based exercises."))
        else:
            # HOME exercises don't use progression — clear it out.
            cleaned["exercise_type"] = ""
            for name in weight_fields[1:] + time_fields:
                cleaned[name] = None

        # `start_weight_beginner` is NOT NULL in the DB (renamed from
        # recommended_weight); never let a blank submission save None.
        if cleaned.get("start_weight_beginner") in (None, ""):
            cleaned["start_weight_beginner"] = 0

        return cleaned


# ───────────────────────── Content: progression rules ─────────────────────────

class ProgressionSettingForm(forms.ModelForm):
    """Gym progression (sets / reps growth per week). Weight/time growth now
    lives on the Exercise itself. Also used by custom programs (same rules)."""
    class Meta:
        model = ProgressionSetting
        fields = [
            "key",
            "set_w2", "set_w3", "set_w4", "set_w5", "set_w6",
            "rep_w2", "rep_w3", "rep_w4", "rep_w5", "rep_w6",
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
