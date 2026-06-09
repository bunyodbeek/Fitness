from django import forms
from django.contrib import admin, messages
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.models.favorites import Favorite, FavoriteExercise, FavoriteProgram, FavoriteCollection
from apps.models.payments import Subscription, SubscriptionPlan
from apps.models.users import UserProfile, UserProgram, WorkoutDay, UserProgramExercise


class MakePremiumForm(forms.Form):
    plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(is_active=True),
        label=_('Subscription Plan'),
    )


class SubscriptionInline(admin.TabularInline):
    model = Subscription
    extra = 0
    readonly_fields = ('plan', 'start_date', 'end_date', 'is_active', 'days_left')
    can_delete = False
    verbose_name_plural = _('Subscription')

    def days_left(self, obj):
        return obj.days_remaining()
    days_left.short_description = _('Days remaining')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'gender', 'age', 'weight', 'height', 'bmi', 'premium_badge']
    search_fields = ['name', 'user__username', 'user__email']
    readonly_fields = ['age', 'bmi', 'created_at', 'updated_at']
    inlines = [SubscriptionInline]
    actions = ['make_premium']

    @admin.display(boolean=True, description=_('Premium'))
    def premium_badge(self, obj):
        return obj.is_premium

    @admin.action(description=_('Grant premium subscription'))
    def make_premium(self, request, queryset):
        if 'apply' in request.POST:
            form = MakePremiumForm(request.POST)
            if form.is_valid():
                plan = form.cleaned_data['plan']
                count = 0
                for profile in queryset:
                    sub, created = Subscription.objects.get_or_create(
                        user=profile,
                        defaults={'plan': plan, 'end_date': plan.get_expiry_date(timezone.now())},
                    )
                    if not created:
                        sub.extend(plan)
                    count += 1
                self.message_user(
                    request,
                    _('%(count)d user(s) successfully granted premium.') % {'count': count},
                    messages.SUCCESS,
                )
                return
        else:
            form = MakePremiumForm()

        return render(request, 'admin/make_premium.html', {
            'form': form,
            'queryset': queryset,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
            'title': _('Grant premium subscription'),
        })


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