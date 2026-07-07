import json
import traceback
from datetime import timedelta
import math

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.db.models.aggregates import Sum
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import activate, get_language
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.generic import TemplateView, UpdateView
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.forms import UserProfileForm
from apps.models import User, UserMotivation, UserProfile
from apps.models.favorites import CustomProgramProgress
from apps.models.payments import Subscription, Payment
from apps.models.workouts import WorkoutProgress, WorkoutType
from apps.services.program_progression import create_onboarding_program
from apps.utils.telegram_webapp import parse_init_data
from apps.utils.tlg_bot import bot_send_message




class WorkoutTypeSelectionView(APIView):
    def post(self, request, *args, **kwargs):
        workout_type = (request.data.get('workout_type') or '').strip().lower()
        valid_types = {WorkoutType.GYM, WorkoutType.HOME}

        if workout_type not in valid_types:
            return Response({'success': False, 'error': 'Invalid workout type'}, status=status.HTTP_400_BAD_REQUEST)

        request.session['workout_type'] = workout_type
        request.session.modified = True
        return Response({'success': True, 'workout_type': workout_type})


class LanguageSelectionAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        language = (request.data.get('language') or '').strip().lower()
        valid_codes = [code for code, _ in settings.LANGUAGES]

        if language not in valid_codes:
            return Response({'success': False, 'error': 'Invalid language'}, status=status.HTTP_400_BAD_REQUEST)

        request.session['django_language'] = language
        request.session.modified = True
        activate(language)

        response = Response({'success': True, 'language': language})
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
        return response

class QuestionnaireSubmitAPIView(APIView):
    def get_or_update_user(self, telegram_id, first_name, last_name):

        user, created = User.objects.get_or_create(
            username=f"telegram_{telegram_id}",
            defaults={'first_name': first_name, 'last_name': last_name}
        )

        if not created:
            user.first_name = first_name
            user.last_name = last_name
            user.save()

        return user, created

    def create_or_update_profile(self, user, data):

        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'telegram_id': data.get('telegram_id'),
                'name': data.get('first_name', 'User')
            }
        )

        profile.telegram_id = data.get('telegram_id')
        profile.telegram_username = data.get('username', '')
        profile.name = data.get('first_name', profile.name or 'User')
        profile.gender = data.get('gender', 'male')
        profile.experience_level = data.get('experience', 'beginner')
        profile.fitness_goal = data.get('goal', 'build_body')
        profile.workout_days_per_week = int(data.get('days', 3))
        profile.weight = float(data.get('weight', 63))
        profile.onboarding_completed = True

        self.save_avatar_if_exists(profile, data.get('photo_url'))
        profile.save()

        return profile

    def save_avatar_if_exists(self, profile, photo_url):

        if not photo_url:
            return

        try:
            response = requests.get(photo_url, timeout=5)
            if response.status_code == 200:
                profile.avatar.save(
                    f"{profile.telegram_id}.jpg",
                    ContentFile(response.content),
                    save=False
                )
        except Exception as e:
            print(f"Avatar save error: {e}")

    def save_motivations(self, profile, motivations):

        UserMotivation.objects.filter(user=profile).delete()
        for m in motivations:
            UserMotivation.objects.create(user=profile, motivation=m)

    def post(self, request, *args, **kwargs):
        data = request.data
        if data is None:
            return Response({'success': False, 'error': 'Noto‘g‘ri JSON format'}, status=400)

        workout_type = (data.get('workout_type') or request.session.get('workout_type') or WorkoutType.GYM).lower()
        if workout_type not in {WorkoutType.GYM, WorkoutType.HOME}:
            workout_type = WorkoutType.GYM
        request.session['workout_type'] = workout_type

        telegram_id = data.get('telegram_id')
        # Frontend telegram_id bera olmasa — imzolangan init_data'dan ajratamiz.
        if not telegram_id:
            verified = parse_init_data(data.get('init_data') or '')
            if verified:
                telegram_id = verified['telegram_id']
                # Telegramdan kelgan ishonchli ma'lumotlar bilan to'ldiramiz.
                data = data.copy() if hasattr(data, 'copy') else dict(data)
                data['telegram_id'] = telegram_id
                data.setdefault('first_name', verified.get('first_name') or 'User')
                data.setdefault('last_name', verified.get('last_name') or '')
                data.setdefault('username', verified.get('username') or '')
                data.setdefault('photo_url', verified.get('photo_url') or '')

        if not telegram_id:
            return Response({'success': False, 'error': 'Telegram ID topilmadi'}, status=400)

        existing_profile = UserProfile.objects.filter(telegram_id=telegram_id).first()
        if existing_profile:
            if not existing_profile.onboarding_completed:
                existing_profile.onboarding_completed = True
                existing_profile.save(update_fields=['onboarding_completed'])
                request.session['show_recommendation_once'] = True
            login(request, existing_profile.user)
            return Response({
                'success': True,
                'redirect_url': reverse('animation'),
                'message': 'User already exists'
            })

        try:

            user, is_new = self.get_or_update_user(
                telegram_id,
                data.get('first_name', 'User'),
                data.get('last_name', '')
            )

            profile = self.create_or_update_profile(user, data)
            create_onboarding_program(profile)
            request.session['show_recommendation_once'] = True

            self.save_motivations(profile, data.get('motivation', []))

            login(request, user)
            bot_send_message(
                telegram_id,
                "🎉 **Ro‘yxatdan o‘tish muvaffaqiyatli yakunlandi!** 🎉\n\n"
                "Sizning ma’lumotlaringiz saqlandi:\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Foydalanuvchi: {self.request.user.profile.name}\n"
                f"🆔 ID: {self.request.user.id}\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "💪 **Endi siz bizning Fitness Platformamizning to‘liq a’zosiz!**\n"
                "Sizga quyidagilar ochildi:\n"
                "• 🏋️‍♂️ Shaxsiy mashg‘ulotlar\n"
                "• 📅 Kunlik darslar rejalari\n"
                "• 🍎 Sog‘lom ovqatlanish bo‘yicha maslahatlar\n"
                "• 📊 Progress kuzatuv statistikasi\n\n"
                "🔥 *Bugun boshlang — ertangi kuningizni kuchliroq qiling!* 🏆"
            )

            return Response({
                'success': True,
                'message': "Ma'lumotlar saqlandi",
                'redirect_url': reverse('animation'),
                'is_new_user': is_new,
                'user_id': user.id,
                'profile_id': profile.id,
                'telegram_id': telegram_id
            })
        except Exception as e:
            print(traceback.format_exc())
            return Response({'success': False, 'error': str(e)}, status=500)


class TelegramAuthAPIView(APIView):

    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            telegram_id = data.get('telegram_id')

            # Frontend telegram_id bera olmasa — imzolangan init_data'dan ajratamiz.
            if not telegram_id:
                verified = parse_init_data(data.get('init_data') or '')
                if verified:
                    telegram_id = verified['telegram_id']

            if not telegram_id:
                return Response({'success': False, 'error': 'Telegram ID not found'},
                                status=status.HTTP_400_BAD_REQUEST)

            profile = UserProfile.objects.filter(telegram_id=telegram_id).first()

            if profile:
                user = profile.user
                login(request, user)

                return Response({
                    'success': True,
                    'redirect': reverse_lazy('animation'),
                    'onboarding_completed': profile.onboarding_completed,
                    'user_id': user.id
                })

            return Response({
                'success': True,
                'redirect': reverse_lazy('onboarding'),
                'onboarding_completed': False,
                'is_new_user': True
            })

        except Exception as e:
            print(traceback.format_exc())
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class OnboardingView(TemplateView):
    template_name = 'miniapp/questionarrie.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = UserProfile.objects.filter(user=request.user).first()
            if profile and profile.onboarding_completed:
                return redirect('animation')
        return super().dispatch(request, *args, **kwargs)


from apps.views.partial import PartialTabMixin


class ProfileView(PartialTabMixin, LoginRequiredMixin, TemplateView):
    template_name = 'users/profile_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        context['user_profile'] = profile

        # Obuna holati va qolgan kunlar (profil kartochkasi uchun)
        subscription = getattr(profile, 'subscription', None)
        is_active = bool(subscription and subscription.is_valid)
        context['subscription_active'] = is_active
        context['days_remaining'] = subscription.days_remaining() if is_active else 0
        return context


class UpdateProfileView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'users/profile_update.html'
    success_url = reverse_lazy('user_profile')

    def get_object(self, queryset=None):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'users/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        subscription = Subscription.objects.filter(user=profile).first()
        if subscription:
            days_remaining = subscription.days_remaining()
            total_days = subscription.total_days()
            if total_days > 0:
                subscription_progress = int((days_remaining / total_days) * 100)
            else:
                subscription_progress = 0
        else:
            days_remaining = 0
            subscription_progress = 0

        context['days_remaining'] = days_remaining
        context['subscription_progress'] = subscription_progress
        return context


class ProgressView(LoginRequiredMixin, TemplateView):
    template_name = 'users/progress.html'

    @staticmethod
    def _finite_number(value, default=0.0):
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return parsed if math.isfinite(parsed) else default

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = (self.request.GET.get('period', 'week') or 'week').strip().lower()
        if period not in {'today', 'week', 'month', 'year', 'all'}:
            period = 'week'

        profile, _created = UserProfile.objects.get_or_create(user=self.request.user)
        workout_progress_qs = WorkoutProgress.objects.filter(
            user=profile,
            status=WorkoutProgress.Status.COMPLETED,
        ).select_related('workout')
        custom_progress_qs = CustomProgramProgress.objects.filter(
            user=profile,
        ).select_related('program')

        now = timezone.now()
        today = timezone.localdate()

        if period == 'today':
            workout_progress_qs = workout_progress_qs.filter(completed_at__date=today)
            custom_progress_qs = custom_progress_qs.filter(created_at__date=today)
        elif period == 'week':
            since = now - timedelta(days=7)
            workout_progress_qs = workout_progress_qs.filter(completed_at__gte=since)
            custom_progress_qs = custom_progress_qs.filter(created_at__gte=since)
        elif period == 'month':
            since = now - timedelta(days=30)
            workout_progress_qs = workout_progress_qs.filter(completed_at__gte=since)
            custom_progress_qs = custom_progress_qs.filter(created_at__gte=since)
        elif period == 'year':
            since = now - timedelta(days=365)
            workout_progress_qs = workout_progress_qs.filter(completed_at__gte=since)
            custom_progress_qs = custom_progress_qs.filter(created_at__gte=since)

        workout_totals = workout_progress_qs.aggregate(
            total_calories=Sum('total_calories'),
            total_duration=Sum('total_duration_seconds'),
            total_exercises=Sum('exercises_completed'),
        )
        custom_totals = custom_progress_qs.aggregate(
            total_calories=Sum('total_calories'),
            total_duration=Sum('total_duration_seconds'),
            total_exercises=Sum('exercises_completed'),
        )
        total_workouts = workout_progress_qs.count() + custom_progress_qs.count()
        total_calories = int(
            self._finite_number(workout_totals['total_calories']) + self._finite_number(custom_totals['total_calories'])
        )
        total_exercises = int(
            self._finite_number(workout_totals['total_exercises']) + self._finite_number(custom_totals['total_exercises'])
        )
        total_duration = (
            self._finite_number(workout_totals['total_duration']) + self._finite_number(custom_totals['total_duration'])
        )
        total_hours = round(total_duration / 3600, 1)

        # ===== CHART: oxirgi 7 kun, har bir metrika (period filtridan mustaqil) =====
        start_of_week = today - timedelta(days=6)
        daily_workouts = []
        daily_calories = []
        daily_hours = []

        for day_offset in range(7):
            day = start_of_week + timedelta(days=day_offset)

            w_qs = WorkoutProgress.objects.filter(
                user=profile, status=WorkoutProgress.Status.COMPLETED,
                completed_at__date=day,
            )
            c_qs = CustomProgramProgress.objects.filter(
                user=profile, created_at__date=day,
            )

            count = w_qs.count() + c_qs.count()

            cals = (
                self._finite_number(w_qs.aggregate(s=Sum('total_calories'))['s'])
                + self._finite_number(c_qs.aggregate(s=Sum('total_calories'))['s'])
            )
            secs = (
                self._finite_number(w_qs.aggregate(s=Sum('total_duration_seconds'))['s'])
                + self._finite_number(c_qs.aggregate(s=Sum('total_duration_seconds'))['s'])
            )

            daily_workouts.append(count)
            daily_calories.append(int(cals))
            daily_hours.append(round(secs / 3600, 1))

        def to_series(values):
            mx = max(values) if values else 0
            return [
                {'value': v, 'percentage': int((v / mx) * 100) if mx else 0}
                for v in values
            ]

        chart_data = {
            'workouts': to_series(daily_workouts),
            'calories': to_series(daily_calories),
            'hours': to_series(daily_hours),
        }

        # ===== Recent workouts =====
        recent_items = []

        for progress in workout_progress_qs.order_by('-completed_at')[:5]:
            workout = progress.workout
            workout_name = workout.title or f"{_('Day')} {workout.day_number}"
            recent_items.append({
                'name': workout_name,
                'date': timezone.localtime(progress.completed_at).strftime('%b %d, %H:%M'),
                'exercises': int(self._finite_number(progress.exercises_completed)),
                'duration': int(self._finite_number(progress.total_duration_seconds) / 60),
                'calories': int(self._finite_number(progress.total_calories)),
                'sort_dt': progress.completed_at,
            })

        for progress in custom_progress_qs.order_by('-created_at')[:5]:
            recent_items.append({
                'name': progress.program.name,
                'date': timezone.localtime(progress.created_at).strftime('%b %d, %H:%M'),
                'exercises': int(self._finite_number(progress.exercises_completed)),
                'duration': int(self._finite_number(progress.total_duration_seconds) / 60),
                'calories': int(self._finite_number(progress.total_calories)),
                'sort_dt': progress.created_at,
            })

        recent_items = sorted(recent_items, key=lambda x: x['sort_dt'], reverse=True)[:5]
        recent_workouts = [{k: v for k, v in item.items() if k != 'sort_dt'} for item in recent_items]

        body_measurements = []
        if profile.weight:
            body_measurements.append({
                'icon': '⚖️',
                'name': _('Weight'),
                'date': timezone.localdate().strftime('%b %d'),
                'value': f"{profile.weight} кг",
                'change': '',
                'change_type': 'neutral',
            })

        context.update({
            'profile': profile,
            'period': period,
            'total_workouts': total_workouts,
            'total_calories': total_calories,
            'total_hours': total_hours,
            'total_exercises': total_exercises,
            'chart_data': chart_data,
            'body_measurements': body_measurements,
            'recent_workouts': recent_workouts,
        })
        return context



class AdminAnalyticsView(TemplateView):
    template_name = "admin_page/admin.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        last_30_days = today - timedelta(days=30)

        # --- Users ---
        total_users = User.objects.count()

        premium_users = Subscription.objects.filter(
            is_active=True
        ).values('user').distinct().count()

        free_users = total_users - premium_users

        today_registrations = User.objects.filter(
            date_joined__date=today
        ).count()

        # --- User growth (last 30 days) ---
        last_month_users = User.objects.filter(
            date_joined__date__lt=last_30_days
        ).count()

        if last_month_users > 0:
            user_growth = round(
                ((total_users - last_month_users) / last_month_users) * 100, 1
            )
        else:
            user_growth = 0

        # --- Conversion rate ---
        conversion_rate = round(
            (premium_users / total_users) * 100, 1
        ) if total_users > 0 else 0

        # --- Revenue ---
        monthly_revenue = Payment.objects.filter(
            created_at__date__gte=start_of_month,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0

        monthly_data = self.get_monthly_users()
        revenue_data = self.get_monthly_revenue()
        # weekly_activity = self.get_weekly_activity()

        # # --- Recent activity ---
        # recent_activities = ActivityLog.objects.select_related(
        #     'user'
        # ).order_by('-created_at')[:10]

        context.update({
            "total_users": total_users,
            "free_users": free_users,
            "premium_users": premium_users,
            "premium_count": premium_users,
            "free_count": free_users,
            "inactive_count": 0,

            "today_registrations": today_registrations,
            "user_growth": user_growth,
            "conversion_rate": conversion_rate,
            "monthly_revenue": monthly_revenue,

            "monthly_data": json.dumps(monthly_data),
            "revenue_data": json.dumps(revenue_data),
            # "weekly_activity": json.dumps(weekly_activity),

            # "recent_activities": [
            #     {
            #         "username": a.user.username,
            #         "user_initials": a.user.username[:2].upper(),
            #         "action": a.action,
            #         "time": timezone.localtime(a.created_at).strftime("%H:%M")
            #     }
            #     for a in recent_activities
            # ]
        })

        return context

    # ---------- Helpers ----------

    def get_monthly_users(self):
        data = []
        for i in range(11, -1, -1):
            month = timezone.now() - timedelta(days=i * 30)
            count = User.objects.filter(
                date_joined__year=month.year,
                date_joined__month=month.month
            ).count()
            data.append(count)
        return data

    def get_monthly_revenue(self):
        data = []
        for i in range(11, -1, -1):
            month = timezone.now() - timedelta(days=i * 30)
            total = Payment.objects.filter(
                created_at__year=month.year,
                created_at__month=month.month,
                status='completed'
            ).aggregate(sum=Sum('amount'))['sum'] or 0
            data.append(total)
        return data

    # def get_weekly_activity(self):
    #     data = []
    #     for i in range(6, -1, -1):
    #         day = timezone.now().date() - timedelta(days=i)
    #         count = ActivityLog.objects.filter(
    #             created_at__date=day
    #         ).count()
    #         data.append(count)
    #     return data


@method_decorator(csrf_protect, name='dispatch')
class ChangeLanguageView(LoginRequiredMixin, TemplateView):
    template_name = 'users/language.html'

    def _get_language_context(self):

        current_language = get_language()
        available_languages = []

        for code, name in settings.LANGUAGES:
            available_languages.append({
                'code': code,
                'name': str(name)
            })

        return {
            'current_language': current_language,
            'available_languages': available_languages,
        }

    def get(self, request, *args, **kwargs):

        context = self._get_language_context()
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):

        new_language_code = request.POST.get('language')
        valid_codes = [lang[0] for lang in settings.LANGUAGES]

        if new_language_code and new_language_code in valid_codes:

            request.session['django_language'] = new_language_code

            activate(new_language_code)

            messages.success(request, _("Language saved successfully!"))

            response = HttpResponseRedirect(reverse('settings'))

            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, new_language_code)

            return response
        else:
            messages.error(request, _("Selected language doesn't exist."))

            context = self._get_language_context()
            return render(request, self.template_name, context)


class ManageSubscriptionView(LoginRequiredMixin, TemplateView):
    template_name = 'users/manage_subscription.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = (
            Subscription.objects.filter(user=self.request.user)
            .select_related('plan')
            .order_by('-id')
            .first()
        )
        payment_history = Payment.objects.filter(user=self.request.user).order_by('-created_at')
        last_payment = payment_history.first()
        next_payment_date = subscription.end_date if subscription and subscription.is_active else None

        days_remaining = 0
        if next_payment_date:
            delta = (next_payment_date - timezone.localdate()).days
            days_remaining = max(delta, 0)

        context.update({
            'subscription': subscription,
            'last_payment': last_payment,
            'next_payment_date': next_payment_date,
            'days_remaining': days_remaining,
        })
        return context


class PaymentHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'users/payment_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment_history = Payment.objects.filter(user=self.request.user).order_by('-created_at')
        total_paid = payment_history.filter(status='success').aggregate(total=Sum('amount'))['total'] or 0
        context.update({
            'payment_history': payment_history,
            'payment_count': payment_history.count(),
            'total_paid': total_paid,
        })
        return context