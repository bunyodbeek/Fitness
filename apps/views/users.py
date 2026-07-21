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
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import activate, get_language
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.generic import TemplateView, UpdateView, View
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.forms import UserProfileForm
from apps.models import User, UserMotivation, UserProfile
from apps.models.favorites import CustomProgramProgress
from apps.models.payments import Subscription, Payment, SubscriptionPlan
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

        is_edit = str(data.get('edit', '')).lower() in ('1', 'true', 'yes')

        existing_profile = UserProfile.objects.filter(telegram_id=telegram_id).first()
        if existing_profile:
            # Re-taking the questionnaire from the profile page: persist the new
            # answers (weight, experience, goal, days, gender) and rebuild the
            # recommended/auto program so it matches the updated profile.
            if is_edit:
                profile = self.create_or_update_profile(existing_profile.user, data)
                try:
                    from apps.services.programs import UserProgramService
                    UserProgramService.reassign_auto_program(profile)
                except Exception:
                    print(traceback.format_exc())
                request.session['show_recommendation_once'] = True
                login(request, existing_profile.user)
                return Response({
                    'success': True,
                    'redirect_url': reverse('animation'),
                    'message': 'Profile updated',
                })

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

    def _is_edit_mode(self, request):
        # `?edit=1` lets an already-onboarded user re-take the questionnaire
        # (from the "Recommended program" button on the profile page).
        return request.GET.get('edit') in ('1', 'true', 'yes')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not self._is_edit_mode(request):
            profile = UserProfile.objects.filter(user=request.user).first()
            if profile and profile.onboarding_completed:
                return redirect('animation')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['edit_mode'] = self._is_edit_mode(self.request)
        return context


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

        # One-time Premium gift the user may have already sent — drives the gift
        # card CTA under the subscription box. Only a paid (available/claimed)
        # gift is surfaced; an unpaid draft still routes to the purchase page.
        from apps.models.payments import PremiumGift
        gift = PremiumGift.objects.filter(sender=profile).first()
        context['gift'] = gift if (gift and gift.is_used) else None

        # Unread admin chat replies → profile header bell + Help card badge.
        from apps.models import SupportMessage
        context['chat_unread'] = SupportMessage.objects.filter(
            user=profile, is_from_admin=True, is_read=False,
        ).count()
        return context


class HelpChatView(LoginRequiredMixin, View):
    """Two-way Help/support chat. The user sends messages here; admin replies
    (sent from the panel "Chat" section) appear back in this thread. The page
    polls ``?after=<id>`` (AJAX) to pull new admin replies live."""
    template_name = 'users/help.html'

    @staticmethod
    def _serialize(msg):
        return {
            'id': msg.id,
            'text': msg.text,
            'is_admin': msg.is_from_admin,
            'time': timezone.localtime(msg.created_at).strftime('%H:%M'),
            'image': msg.image.url if msg.image else '',
            'thumb': msg.thumbnail.url if msg.thumbnail else (msg.image.url if msg.image else ''),
        }

    @staticmethod
    def _unread(profile):
        from apps.models import SupportMessage
        return SupportMessage.objects.filter(
            user=profile, is_from_admin=True, is_read=False,
        ).count()

    def get(self, request):
        from apps.models import SupportMessage
        profile = request.user.profile

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Count-only mode (used by the profile bell to poll the badge).
            if request.GET.get('count'):
                return JsonResponse({'ok': True, 'count': self._unread(profile)})

            qs = SupportMessage.objects.filter(user=profile)
            after = request.GET.get('after')
            if after and str(after).isdigit():
                qs = qs.filter(id__gt=int(after))
            messages_list = list(qs.order_by('created_at'))
            # Only mark admin replies read when the user is scrolled to the bottom.
            if request.GET.get('atbottom') == '1':
                SupportMessage.objects.filter(
                    user=profile, is_from_admin=True, is_read=False,
                ).update(is_read=True)
            return JsonResponse({
                'ok': True,
                'messages': [self._serialize(m) for m in messages_list],
                'unread': self._unread(profile),
            })

        messages_list = list(
            SupportMessage.objects.filter(user=profile).order_by('created_at')
        )
        # Opening the page marks everything read.
        SupportMessage.objects.filter(
            user=profile, is_from_admin=True, is_read=False,
        ).update(is_read=True)
        return render(request, self.template_name, {
            'chat_messages': [self._serialize(m) for m in messages_list],
        })

    def post(self, request):
        from apps.models import SupportMessage
        profile = request.user.profile
        text = (request.POST.get('text') or '').strip()
        upload = request.FILES.get('image')

        if not text and not upload:
            return JsonResponse({'ok': False, 'error': 'empty',
                                 'message': _("Please type a message.")}, status=400)

        image_content = image_name = thumb_content = thumb_name = None
        if upload:
            from django.core.exceptions import ValidationError
            from apps.services.support_images import process_chat_image
            try:
                image_content, image_name, thumb_content, thumb_name = process_chat_image(upload)
            except ValidationError as exc:
                return JsonResponse({'ok': False, 'error': 'image',
                                     'message': str(exc.messages[0])}, status=400)

        msg = SupportMessage(user=profile, text=text[:2000], is_from_admin=False)
        if image_content:
            msg.image.save(image_name, image_content, save=False)
            msg.thumbnail.save(thumb_name, thumb_content, save=False)
        msg.save()
        return JsonResponse({'ok': True, 'message': self._serialize(msg)})


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

        # Statistics are a premium feature. Free users may only view *today's*
        # stats; any other period (week/month/year/all) is locked behind premium.
        is_premium = profile.is_premium
        stats_locked = (not is_premium) and period != 'today'
        context['is_premium'] = is_premium
        context['stats_locked'] = stats_locked
        context['period'] = period
        if stats_locked:
            # Don't compute or reveal the real numbers — render the paywall only.
            context['profile'] = profile
            return context

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
class ChangeLanguageView(LoginRequiredMixin, View):
    """Language switch endpoint. The old full-page selector is gone — language is
    now chosen from a bottom-sheet modal on the Settings page — so GET (and the
    invalid-code path) just bounce back to Settings. The POST mechanism itself is
    unchanged: set session + cookie, activate, redirect to Settings."""

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse('settings'))

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

            return HttpResponseRedirect(reverse('settings'))


# Payment.status → coarse UI bucket used by the template (icon / colour / filter).
_PAYMENT_UI_STATUS = {
    Payment.PaymentStatus.COMPLETED: 'success',
    Payment.PaymentStatus.PENDING: 'pending',
    Payment.PaymentStatus.PROCESSING: 'pending',
    Payment.PaymentStatus.FAILED: 'failed',
}


class ManageSubscriptionView(LoginRequiredMixin, TemplateView):
    """Premium → transaction history. Non-premium → the buy-premium page.

    Payment history used to be a separate (dead) menu item in settings; it now
    lives here.
    """
    template_name = 'users/manage_subscription.html'

    def dispatch(self, request, *args, **kwargs):
        # Only premium users see the subscription/transaction screen; everyone
        # else is sent to the paywall to buy premium first.
        if not request.user.profile.is_premium:
            return redirect('premium')
        return super().dispatch(request, *args, **kwargs)

    # Transaction history is shown in cumulative pages of this size. "Load more"
    # is a plain ?page=N link (full reload) — no AJAX pattern exists in the app.
    PAGE_SIZE = 5

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile

        subscription = (
            Subscription.objects.filter(user=profile)
            .select_related('plan')
            .order_by('-id')
            .first()
        )

        payments_qs = (
            Payment.objects.filter(user=profile)
            .select_related('plan')
            .order_by('-created_at')
        )
        total_count = payments_qs.count()
        total_paid = payments_qs.filter(
            status=Payment.PaymentStatus.COMPLETED
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Cumulative pagination: page 1 → first 5, page 2 → first 10, …
        try:
            page = max(1, int(self.request.GET.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        visible_count = page * self.PAGE_SIZE

        payments = list(payments_qs[:visible_count])
        for payment in payments:
            payment.ui_status = _PAYMENT_UI_STATUS.get(payment.status, 'pending')

        next_payment_date = subscription.end_date if subscription and subscription.is_active else None

        days_remaining = 0
        if next_payment_date:
            delta = (next_payment_date.date() - timezone.localdate()).days
            days_remaining = max(delta, 0)

        # Available packages the user can switch/upgrade to. The one matching the
        # current subscription is flagged so the template can mark it "Current".
        current_plan_id = subscription.plan_id if subscription else None
        available_plans = []
        for plan in SubscriptionPlan.objects.filter(is_active=True).order_by('order', 'price_uzs'):
            available_plans.append({
                'id': plan.id,
                'period_display': plan.get_period_display(),
                'months': plan.months,
                'price_uzs': plan.price_uzs,
                'is_popular': plan.is_popular,
                'is_current': plan.id == current_plan_id,
            })

        # One-time Premium gift the user may have already sent (drives the gift
        # card CTA / status). Only a paid (available/claimed) gift is shown.
        from apps.models.payments import PremiumGift
        gift = PremiumGift.objects.filter(sender=profile).first()
        if gift and not gift.is_used:
            gift = None

        context.update({
            'subscription': subscription,
            'current_plan': subscription.plan if subscription else None,
            'gift': gift,
            'available_plans': available_plans,
            'payments': payments,
            'total_paid': total_paid,
            'payment_count': total_count,
            'has_more': total_count > visible_count,
            'next_page': page + 1,
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