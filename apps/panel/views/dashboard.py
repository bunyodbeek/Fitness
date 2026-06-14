"""Dashboard — all figures are aggregated from the real database.

Activity metrics are derived from the workout-progress tables (the real,
populated source of user activity), not from any analytics log.
"""
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from apps.models import Program, User, UserProfile
from apps.models.payments import Payment, Subscription
from apps.models.workouts import UserWorkoutProgress, WorkoutProgress
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin

# Weekday short labels Mon..Sun (translatable)
_WEEKDAYS = [_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun")]


def _pct_change(current, previous):
    """Percent change vs a previous value, rounded to 1 decimal."""
    if previous:
        return round((current - previous) / previous * 100, 1)
    return 100.0 if current else 0.0


def _fmt_int(value):
    return f"{int(value or 0):,}".replace(",", " ")


def _active_user_ids(start_date, end_date):
    """Distinct UserProfile ids with any workout activity in [start, end] (date-inclusive)."""
    gym = set(
        WorkoutProgress.objects.filter(
            completed_at__date__gte=start_date, completed_at__date__lte=end_date
        ).values_list("user_id", flat=True)
    )
    home = set(
        UserWorkoutProgress.objects.filter(
            updated_at__date__gte=start_date, updated_at__date__lte=end_date
        ).values_list("user_id", flat=True)
    )
    return gym | home


def _activity_count(day):
    """Number of workout sessions (gym + home) on a given day."""
    gym = WorkoutProgress.objects.filter(completed_at__date=day).count()
    home = UserWorkoutProgress.objects.filter(updated_at__date=day).count()
    return gym + home


class DashboardView(StaffRequiredMixin, PanelContextMixin, TemplateView):
    template_name = "panel/dashboard.html"
    nav_active = "dashboard"
    page_title = _("Dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        month_start = today.replace(day=1)
        prev_month_end = month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)

        # ── Stat card 1: total users ──
        total_users = User.objects.count()
        new_this_month = User.objects.filter(date_joined__date__gte=month_start).count()
        new_prev_month = User.objects.filter(
            date_joined__date__gte=prev_month_start, date_joined__date__lt=month_start
        ).count()

        # ── Stat card 2: premium members (active + not expired = is_valid) ──
        premium_users = Subscription.objects.filter(is_active=True, end_date__gte=now).count()
        new_subs_month = Subscription.objects.filter(start_date__date__gte=month_start).count()
        new_subs_prev = Subscription.objects.filter(
            start_date__date__gte=prev_month_start, start_date__date__lt=month_start
        ).count()

        # ── Stat card 3: monthly revenue (UZS, completed) ──
        revenue_month = Payment.objects.filter(
            status=Payment.PaymentStatus.COMPLETED,
            currency=Payment.Currency.UZS,
            created_at__date__gte=month_start,
        ).aggregate(t=Sum("amount"))["t"] or 0
        revenue_prev = Payment.objects.filter(
            status=Payment.PaymentStatus.COMPLETED,
            currency=Payment.Currency.UZS,
            created_at__date__gte=prev_month_start,
            created_at__date__lt=month_start,
        ).aggregate(t=Sum("amount"))["t"] or 0

        # ── Stat card 4: today's active users (distinct users with a workout today) ──
        active_today = len(_active_user_ids(today, today))
        active_yesterday = len(_active_user_ids(yesterday, yesterday))

        context["stats"] = [
            {
                "label": _("Total users"),
                "value": _fmt_int(total_users),
                "change": _pct_change(new_this_month, new_prev_month),
                "icon": "users",
            },
            {
                "label": _("Premium members"),
                "value": _fmt_int(premium_users),
                "change": _pct_change(new_subs_month, new_subs_prev),
                "icon": "star",
            },
            {
                "label": _("Monthly revenue"),
                "value": f"{_fmt_int(revenue_month)} UZS",
                "change": _pct_change(float(revenue_month), float(revenue_prev)),
                "icon": "money",
            },
            {
                "label": _("Active today"),
                "value": _fmt_int(active_today),
                "change": _pct_change(active_today, active_yesterday),
                "icon": "activity",
            },
        ]

        # ── Weekly activity bar chart (Mon..Sun of current week) ──
        monday = today - timedelta(days=today.weekday())
        week_days = [monday + timedelta(days=i) for i in range(7)]
        day_counts = [_activity_count(d) for d in week_days]
        max_count = max(day_counts) if any(day_counts) else 1
        context["weekly_activity"] = [
            {
                "label": _WEEKDAYS[i],
                "value": day_counts[i],
                "height": round(day_counts[i] / max_count * 100) if max_count else 0,
                "is_today": week_days[i] == today,
            }
            for i in range(7)
        ]

        # ── Recent users ──
        context["recent_users"] = (
            UserProfile.objects.select_related("user").order_by("-created_at")[:6]
        )

        # ── Popular programs (by views) with progress bars ──
        programs = list(
            Program.objects.filter(is_active=True, is_one_time=False).order_by("-view_count")[:5]
        )
        max_views = max((p.view_count for p in programs), default=0) or 1
        context["popular_programs"] = [
            {
                "name": p.display_name,
                "views": p.view_count,
                "percent": round(p.view_count / max_views * 100) if max_views else 0,
            }
            for p in programs
        ]

        # ── Recent activity timeline (latest workout sessions) ──
        context["recent_activity"] = (
            WorkoutProgress.objects.select_related("user", "workout")
            .order_by("-completed_at")[:7]
        )
        return context
