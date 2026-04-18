from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
import nested_admin

from apps.models import (
    Plan, Program, WorkoutExercise, Week, Exercise,
)
from apps.models.workouts import HomeWorkout, GymWorkout, ProgressionSetting


# ─────────────────────────────────────────────
# 1. WorkoutExercise Inline
# ─────────────────────────────────────────────
class WorkoutExerciseInlineForm(forms.ModelForm):
    class Meta:
        model = WorkoutExercise
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["minutes"].required = False
        self.fields["recommended_weight"].required = False

    def clean(self):
        cleaned_data = super().clean()
        exercise = cleaned_data.get("exercise")
        minutes = cleaned_data.get("minutes")
        recommended_weight = cleaned_data.get("recommended_weight")

        if exercise:
            # Admin UX: vaqt/og'irlik kiritilmasa Exercise dan avtomatik to'ldiriladi.
            if minutes in (None, 0, 0.0, ""):
                cleaned_data["minutes"] = exercise.duration or 0
            if recommended_weight in (None, 0, 0.0, ""):
                cleaned_data["recommended_weight"] = exercise.recommended_weight or 0

        return cleaned_data


class WeekAdminForm(forms.ModelForm):
    generate_remaining_weeks = forms.BooleanField(
        required=False,
        label="Generate remaining weeks (up to week 6)",
        help_text="Belgilansa, joriy weekdan keyingi yetishmayotgan haftalar avtomatik yaratiladi.",
    )

    class Meta:
        model = Week
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        plan = cleaned_data.get("plan")
        week_number = cleaned_data.get("week_number")

        if plan and week_number is not None:
            qs = Week.objects.filter(plan=plan, week_number=week_number)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Bu plan uchun ushbu week allaqachon mavjud. Mavjud weekni edit qiling."
                )

        return cleaned_data


class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    form = WorkoutExerciseInlineForm
    extra = 1
    fields = ("exercise", "sets", "reps", "minutes", "recommended_weight", "order")
    verbose_name = "Mashq"
    verbose_name_plural = "Mashqlar"

    # Saqlanganda signal ishlaganini ko'rsatish uchun
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        return formset


# ─────────────────────────────────────────────
# 2. Workout Inline-lari (Week sahifasi uchun)
# ─────────────────────────────────────────────
class GymWorkoutInline(admin.StackedInline):
    model = GymWorkout
    extra = 0
    show_change_link = True  # "Mashqlarni qo'shish" havolasi
    exclude = ("rounds", "description", "description_uz", "description_ru")
    fields = (("day_number", "apply_to_all_weeks"), "title")
    verbose_name = "Gym kuni"
    verbose_name_plural = "Gym kunlari"

    # apply_to_all_weeks uchun yordam matni
    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        return fields


class HomeWorkoutInline(admin.StackedInline):
    model = HomeWorkout
    extra = 0
    show_change_link = True
    exclude = ("description", "description_uz", "description_ru")
    fields = (("day_number", "apply_to_all_weeks"), "rounds", "title")
    verbose_name = "Home kuni"
    verbose_name_plural = "Home kunlari"


class WorkoutExerciseNestedInline(nested_admin.NestedStackedInline):
    model = WorkoutExercise
    form = WorkoutExerciseInlineForm
    extra = 1
    fields = (
        "exercise",
        ("sets", "reps"),
        ("minutes", "recommended_weight"),
        "order",
    )
    sortable_field_name = "order"
    verbose_name = "Mashq"
    verbose_name_plural = "Mashqlar"


class GymWorkoutNestedInline(nested_admin.NestedStackedInline):
    model = GymWorkout
    extra = 0
    show_change_link = True
    exclude = ("rounds", "description", "description_uz", "description_ru")
    fields = (("day_number", "apply_to_all_weeks"), "title")
    verbose_name = "Gym kuni"
    verbose_name_plural = "Gym kunlari"
    inlines = [WorkoutExerciseNestedInline]


class HomeWorkoutNestedInline(nested_admin.NestedStackedInline):
    model = HomeWorkout
    extra = 0
    show_change_link = True
    exclude = ("description", "description_uz", "description_ru")
    fields = (("day_number", "apply_to_all_weeks"), "rounds", "title")
    verbose_name = "Home kuni"
    verbose_name_plural = "Home kunlari"
    inlines = [WorkoutExerciseNestedInline]


# ─────────────────────────────────────────────
# 3. Week Inline (Plan sahifasi uchun)
# ─────────────────────────────────────────────
class WeekInline(admin.TabularInline):
    model = Week
    extra = 0
    fields = ("week_number", "workout_count", "go_to_week")
    readonly_fields = ("workout_count", "go_to_week")
    can_delete = False
    ordering = ("week_number",)

    def workout_count(self, obj):
        if obj.id:
            count = obj.workouts.count()
            if count == 0:
                return format_html('<span style="color:#e74c3c;">0 kun</span>')
            return format_html('<span style="color:#27ae60;">✓ {} kun</span>', count)
        return "—"
    workout_count.short_description = "Kunlar"

    def go_to_week(self, obj):
        if obj.id:
            url = reverse('admin:apps_week_change', args=[obj.id])
            return format_html(
                '<a href="{}" style="'
                'background:#1a73e8;color:white;padding:4px 10px;'
                'border-radius:4px;text-decoration:none;font-size:12px;">'
                '→ Kunlarni boshqarish</a>',
                url
            )
        return "—"
    go_to_week.short_description = "Harakat"


# ─────────────────────────────────────────────
# 4. Week Admin
# ─────────────────────────────────────────────
@admin.register(Week)
class WeekAdmin(nested_admin.NestedModelAdmin):
    form = WeekAdminForm
    list_display = ("__str__", "plan_link", "week_number", "workout_summary", "exercise_total")
    list_filter = ("plan__program__workout_type", "plan__program", "plan")
    search_fields = ("plan__name", "plan__program__name")
    ordering = ("plan__program", "plan", "week_number")

    def has_add_permission(self, request):
        """
        Week'lar Plan yaratilganda avtomatik (1..6) yaratiladi.
        Qo'lda add qilish duplicate (plan, week_number) xatolariga olib keladi.
        """
        return False

    def get_inlines(self, request, obj):
        if obj:
            wtype = obj.plan.program.workout_type
            if wtype == "gym":
                return [GymWorkoutNestedInline]
            if wtype == "home":
                return [HomeWorkoutNestedInline]

        # Add form holatida plan query param bor bo'lsa, workout turini shundan aniqlaymiz.
        # Bu home plan tanlanganda ham to'g'ri inline ko'rsatishga yordam beradi.
        plan_id = request.GET.get("plan")
        if plan_id:
            try:
                wtype = Plan.objects.select_related("program").get(pk=plan_id).program.workout_type
                if wtype == "home":
                    return [HomeWorkoutNestedInline]
            except Plan.DoesNotExist:
                pass
        return [GymWorkoutNestedInline]

    def plan_link(self, obj):
        url = reverse('admin:apps_plan_change', args=[obj.plan.id])
        return format_html('<a href="{}">{}</a>', url, obj.plan.name)
    plan_link.short_description = "Plan"

    def workout_summary(self, obj):
        workouts = obj.workouts.all()
        if not workouts:
            return format_html('<span style="color:#e74c3c;">Kunlar yo\'q</span>')
        days = ", ".join([f"Kun {w.day_number}" for w in workouts])
        return format_html('<span style="color:#27ae60;">{}</span>', days)
    workout_summary.short_description = "Kunlar"

    def exercise_total(self, obj):
        total = sum(w.workout_exercises.count() for w in obj.workouts.all())
        if total == 0:
            return format_html('<span style="color:#e74c3c;">0 mashq</span>')
        return format_html('<b>{}</b> mashq', total)
    exercise_total.short_description = "Jami mashqlar"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if form.cleaned_data.get("generate_remaining_weeks"):
            created_count = 0
            for week_number in range(obj.week_number + 1, 7):
                _, created = Week.objects.get_or_create(plan=obj.plan, week_number=week_number)
                if created:
                    created_count += 1
            if created_count:
                messages.success(
                    request,
                    f"✓ {created_count} ta qolgan hafta avtomatik yaratildi."
                )

    def save_related(self, request, form, formsets, change):
        """
        Nested inline saqlashda Django/NestedAdmin default oqimini saqlaymiz.
        Shunda WorkoutExercise post_save signallari progression generatsiyasini
        odatdagidek ishga tushiradi.
        """
        super().save_related(request, form, formsets, change)

        week = form.instance
        if week.week_number != 1:
            return

        workouts = week.workouts.filter(apply_to_all_weeks=True)
        for workout in workouts:
            messages.info(
                request,
                f"✓ '{workout.title or f'Kun {workout.day_number}'}' saqlandi. "
                f"1-haftadagi mashqlar saqlanganda 2-6 haftalar progression bo'yicha yangilanadi."
            )


# ─────────────────────────────────────────────
# 5. GymWorkout Admin
# ─────────────────────────────────────────────
@admin.register(GymWorkout)
class GymWorkoutAdmin(admin.ModelAdmin):
    list_display = ("__str__", "week_link", "day_number", "exercise_count", "apply_to_all_weeks", "progression_status")
    list_filter = ("week__plan__program", "week__plan", "week__week_number", "apply_to_all_weeks")
    search_fields = ("title", "week__plan__name", "week__plan__program__name")
    exclude = ("rounds", "description", "description_uz", "description_ru")
    autocomplete_fields = ["week"]
    inlines = [WorkoutExerciseInline]
    ordering = ("week__plan__program", "week__plan", "week__week_number", "day_number")

    fieldsets = (
        (None, {
            "fields": ("week", ("day_number", "apply_to_all_weeks"), "title"),
        }),
        ("Qo'shimcha (ixtiyoriy)", {
            "fields": ("title_uz", "title_ru"),
            "classes": ("collapse",),
        }),
    )

    def week_link(self, obj):
        url = reverse('admin:apps_week_change', args=[obj.week.id])
        return format_html('<a href="{}">{}</a>', url, obj.week)
    week_link.short_description = "Hafta"

    def exercise_count(self, obj):
        count = obj.workout_exercises.count()
        if count == 0:
            return format_html('<span style="color:#e74c3c;">Mashq yo\'q!</span>')
        return format_html('<span style="color:#27ae60;">✓ {} ta</span>', count)
    exercise_count.short_description = "Mashqlar"

    def progression_status(self, obj):
        """2-6 haftalarga nusxa ko'chirilganmi?"""
        if obj.week.week_number != 1:
            return format_html('<span style="color:#888;">— ({}. hafta)</span>', obj.week.week_number)
        if not obj.apply_to_all_weeks:
            return format_html('<span style="color:#f39c12;">⚠ apply_to_all_weeks = False</span>')
        # 2-haftada shu kunning nusxasi bormi?
        from apps.models import Workout
        exists = Workout.objects.filter(
            week__plan=obj.week.plan,
            week__week_number=2,
            day_number=obj.day_number
        ).exists()
        if exists:
            return format_html('<span style="color:#27ae60;">✓ 2-6 haftalarda bor</span>')
        return format_html('<span style="color:#e74c3c;">✗ Hali nusxa yo\'q</span>')
    progression_status.short_description = "Progression"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.apply_to_all_weeks and obj.week.week_number == 1:
            messages.info(
                request,
                f"✓ Kun saqlandi. Endi mashq qo'shing — "
                f"saqlanganda 2-6 haftalarga avtomatik ko'chiriladi."
            )

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj_instance in instances:
            obj_instance.save()
        formset.save_m2m()
        # Signal ishlaganidan keyin xabar
        main_obj = form.instance
        if main_obj.apply_to_all_weeks and main_obj.week.week_number == 1:
            from apps.models import WorkoutExercise as WE
            generated = WE.objects.filter(
                source_week_one__workout__week__plan=main_obj.week.plan,
                workout__week__week_number__in=[2, 3, 4, 5, 6],
                workout__day_number=main_obj.day_number
            ).count()
            if generated > 0:
                messages.success(
                    request,
                    f"✓ Signal ishladi! {generated} ta mashq 2-6 haftalarga avtomatik generatsiya qilindi."
                )


# ─────────────────────────────────────────────
# 6. HomeWorkout Admin
# ─────────────────────────────────────────────
@admin.register(HomeWorkout)
class HomeWorkoutAdmin(admin.ModelAdmin):
    list_display = ("__str__", "week_link", "day_number", "rounds", "exercise_count", "apply_to_all_weeks")
    list_filter = ("week__plan__program", "week__plan", "week__week_number", "apply_to_all_weeks")
    search_fields = ("title", "week__plan__name")
    autocomplete_fields = ["week"]
    inlines = [WorkoutExerciseInline]
    ordering = ("week__plan__program", "week__plan", "week__week_number", "day_number")

    fieldsets = (
        (None, {
            "fields": ("week", ("day_number", "rounds", "apply_to_all_weeks"), "title"),
        }),
        ("Qo'shimcha (ixtiyoriy)", {
            "fields": ("title_uz", "title_ru"),
            "classes": ("collapse",),
        }),
    )

    def week_link(self, obj):
        url = reverse('admin:apps_week_change', args=[obj.week.id])
        return format_html('<a href="{}">{}</a>', url, obj.week)
    week_link.short_description = "Hafta"

    def exercise_count(self, obj):
        count = obj.workout_exercises.count()
        if count == 0:
            return format_html('<span style="color:#e74c3c;">Mashq yo\'q!</span>')
        return format_html('<span style="color:#27ae60;">✓ {} ta</span>', count)
    exercise_count.short_description = "Mashqlar"


# ─────────────────────────────────────────────
# 7. Plan Admin
# ─────────────────────────────────────────────
@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "program_link", "weeks_count", "week_fill_status", "is_premium")
    list_filter = ("program__workout_type", "program", "is_premium")
    search_fields = ("name", "program__name")
    autocomplete_fields = ["program", "progression_config"]
    inlines = [WeekInline]

    fieldsets = (
        (None, {"fields": ("program", "order", "is_premium")}),
        (_("Nomlar"), {"fields": ("name", "name_uz", "name_ru")}),
        (_("Progression sozlamalari"), {
            "fields": ("weeks_count", "progression_config"),
            "description": (
                "⚠️ Progression Config tanlangan bo'lsa, "
                "1-haftaga mashq qo'shilganda 2-6 haftalarga avtomatik hisoblanadi."
            ),
        }),
    )

    def program_link(self, obj):
        url = reverse('admin:apps_program_change', args=[obj.program.id])
        return format_html('<a href="{}">{}</a>', url, obj.program.name)
    program_link.short_description = "Program"

    def week_fill_status(self, obj):
        """Nechta haftada kun bor?"""
        weeks = obj.weeks.prefetch_related("workouts").all()
        filled = sum(1 for w in weeks if w.workouts.exists())
        total = weeks.count()
        if total == 0:
            return format_html('<span style="color:#e74c3c;">Haftalar yo\'q!</span>')
        color = "#27ae60" if filled == total else "#f39c12" if filled > 0 else "#e74c3c"
        return format_html(
            '<span style="color:{};">{}/{} hafta to\'ldirilgan</span>',
            color, filled, total
        )
    week_fill_status.short_description = "To'ldirilgan"


# ─────────────────────────────────────────────
# 8. Program Admin
# ─────────────────────────────────────────────
@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "workout_type", "level", "goal", "plan_count", "is_active", "is_premium")
    list_filter = ("workout_type", "level", "goal", "is_active", "is_premium")
    search_fields = ("name",)

    fieldsets = (
        (None, {"fields": ("name", "name_uz", "name_ru", "image")}),
        (_("Sozlamalar"), {"fields": ("workout_type", "level", "goal", "type", "is_active", "is_premium", "is_template")}),
        (_("Tavsif"), {"fields": ("description", "description_uz", "description_ru"), "classes": ("collapse",)}),
    )

    def plan_count(self, obj):
        count = obj.plans.count()
        if count == 0:
            return format_html('<span style="color:#e74c3c;">Plan yo\'q!</span>')
        return format_html('<span style="color:#27ae60;">✓ {} plan</span>', count)
    plan_count.short_description = "Planlar"


# ─────────────────────────────────────────────
# 9. ProgressionSetting Admin
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# 10. Standart Workout (fallback, kerak bo'lsa)
# ─────────────────────────────────────────────
@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ("id", "week", "day_number", "title", "apply_to_all_weeks")
    list_filter = ("week__plan__program", "week__week_number")
    inlines = [WorkoutExerciseInline]
    autocomplete_fields = ["week"]


from django.contrib import admin
from apps.models.workouts import ProgressionSetting


@admin.register(ProgressionSetting)
class ProgressionSettingAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "w2_weight_mult", "w3_weight_mult", "w4_weight_mult",
        "w5_weight_mult", "w6_deload_mult",
        "small_threshold", "small_boost",
    )
    search_fields = ("key",)
    
    fieldsets = (
        ("Kalit", {
            "fields": ("key",),
            "description": "Format: GoalGenderLevel — masalan: FLMaleBeginner",
        }),
        ("Weight multipliers (hafta bo'yicha)", {
            "fields": (
                ("w2_weight_mult", "w3_weight_mult", "w4_weight_mult"),
                ("w5_weight_mult", "w6_deload_mult"),
            ),
        }),
        ("Sets increment (base dan, + yoki -)", {
            "fields": (("set_w2", "set_w3", "set_w4", "set_w5", "set_w6"),),
        }),
        ("Reps increment (base dan, + yoki -)", {
            "fields": (("rep_w2", "rep_w3", "rep_w4", "rep_w5", "rep_w6"),),
        }),
        ("Kichik og'irlik chegarasi", {
            "fields": (("small_threshold", "small_boost"),),
            "description": (
                "Agar mashq og'irligi threshold dan kam bo'lsa, "
                "small_boost qo'shiladi (aks holda +2.5 kg)."
            ),
        }),
    )
