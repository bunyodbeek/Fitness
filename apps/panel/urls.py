"""Custom admin panel URLs (namespace: ``panel``).

Mounted under ``/manage/`` (inside i18n_patterns) in root.urls.
"""
from django.urls import path

from apps.panel.views.auth import PanelLoginView, PanelLogoutView
from apps.panel.views.dashboard import DashboardView
from apps.panel.views import users as u
from apps.panel.views import subscriptions as sub
from apps.panel.views import tracking as tr
from apps.panel.views import programs as pr
from apps.panel.views import exercises as ex
from apps.panel.views import handbook as hb
from apps.panel.views import payments as pay
from apps.panel.views import reports as rep
from apps.panel.views import settings as st
from apps.panel.views import admins as adm

app_name = "panel"

urlpatterns = [
    # Auth
    path("login/", PanelLoginView.as_view(), name="login"),
    path("logout/", PanelLogoutView.as_view(), name="logout"),

    # Dashboard
    path("", DashboardView.as_view(), name="dashboard"),

    # Users
    path("users/", u.UserListView.as_view(), name="users"),
    path("users/add/", u.UserCreateView.as_view(), name="user_add"),
    path("users/<int:pk>/edit/", u.UserUpdateView.as_view(), name="user_edit"),
    path("users/<int:pk>/delete/", u.UserDeleteView.as_view(), name="user_delete"),

    # Subscriptions
    path("subscriptions/", sub.SubscriptionListView.as_view(), name="subscriptions"),
    path("subscriptions/add/", sub.SubscriptionCreateView.as_view(), name="subscription_add"),
    path("subscriptions/<int:pk>/edit/", sub.SubscriptionUpdateView.as_view(), name="subscription_edit"),
    path("subscriptions/<int:pk>/delete/", sub.SubscriptionDeleteView.as_view(), name="subscription_delete"),

    # Tracking
    path("tracking/", tr.TrackingListView.as_view(), name="tracking"),
    path("tracking/add/", tr.TrackingCreateView.as_view(), name="tracking_add"),
    path("tracking/<int:pk>/edit/", tr.TrackingUpdateView.as_view(), name="tracking_edit"),
    path("tracking/<int:pk>/delete/", tr.TrackingDeleteView.as_view(), name="tracking_delete"),

    # Programs (standalone CRUD — creating a program ends the flow)
    path("programs/", pr.ProgramListView.as_view(), name="programs"),
    path("programs/add/", pr.ProgramCreateView.as_view(), name="program_add"),
    path("programs/<int:pk>/edit/", pr.ProgramUpdateView.as_view(), name="program_edit"),
    path("programs/<int:pk>/delete/", pr.ProgramDeleteView.as_view(), name="program_delete"),

    # Plans (own section: Plan -> Week -> Workout -> WorkoutExercise)
    path("plans/", pr.PlanListView.as_view(), name="plans"),
    path("plans/add/", pr.PlanCreateView.as_view(), name="plan_add"),
    path("plans/<int:pk>/", pr.PlanDetailView.as_view(), name="plan_detail"),
    path("plans/<int:pk>/edit/", pr.PlanUpdateView.as_view(), name="plan_edit"),
    path("plans/<int:pk>/delete/", pr.PlanDeleteView.as_view(), name="plan_delete"),
    path("plans/<int:plan_pk>/weeks/add/", pr.WeekCreateView.as_view(), name="week_add"),
    path("weeks/<int:pk>/", pr.WeekDetailView.as_view(), name="week_detail"),
    path("weeks/<int:pk>/delete/", pr.WeekDeleteView.as_view(), name="week_delete"),
    path("weeks/<int:week_pk>/workouts/add/", pr.WorkoutCreateView.as_view(), name="workout_add"),
    path("workouts/<int:pk>/", pr.WorkoutDetailView.as_view(), name="workout_detail"),
    path("workouts/<int:pk>/edit/", pr.WorkoutUpdateView.as_view(), name="workout_edit"),
    path("workouts/<int:pk>/delete/", pr.WorkoutDeleteView.as_view(), name="workout_delete"),
    path("workouts/<int:workout_pk>/exercises/add/", pr.WorkoutExerciseCreateView.as_view(), name="we_add"),
    path("workout-exercises/<int:pk>/edit/", pr.WorkoutExerciseUpdateView.as_view(), name="we_edit"),
    path("workout-exercises/<int:pk>/delete/", pr.WorkoutExerciseDeleteView.as_view(), name="we_delete"),

    # Exercises
    path("exercises/", ex.ExerciseListView.as_view(), name="exercises"),
    path("exercises/add/", ex.ExerciseCreateView.as_view(), name="exercise_add"),
    path("exercises/<int:pk>/edit/", ex.ExerciseUpdateView.as_view(), name="exercise_edit"),
    path("exercises/<int:pk>/delete/", ex.ExerciseDeleteView.as_view(), name="exercise_delete"),

    # Handbook
    path("handbook/", hb.HandbookListView.as_view(), name="handbook"),
    path("handbook/categories/add/", hb.CategoryCreateView.as_view(), name="category_add"),
    path("handbook/categories/<int:pk>/", hb.CategoryDetailView.as_view(), name="category_detail"),
    path("handbook/categories/<int:pk>/edit/", hb.CategoryUpdateView.as_view(), name="category_edit"),
    path("handbook/categories/<int:pk>/delete/", hb.CategoryDeleteView.as_view(), name="category_delete"),
    path("handbook/categories/<int:category_pk>/subcategories/add/", hb.SubCategoryCreateView.as_view(), name="subcat_add"),
    path("handbook/subcategories/<int:pk>/", hb.SubCategoryDetailView.as_view(), name="subcat_detail"),
    path("handbook/subcategories/<int:pk>/edit/", hb.SubCategoryUpdateView.as_view(), name="subcat_edit"),
    path("handbook/subcategories/<int:pk>/delete/", hb.SubCategoryDeleteView.as_view(), name="subcat_delete"),
    path("handbook/items/add/", hb.ItemCreateView.as_view(), name="item_add"),
    path("handbook/items/<int:pk>/edit/", hb.ItemUpdateView.as_view(), name="item_edit"),
    path("handbook/items/<int:pk>/delete/", hb.ItemDeleteView.as_view(), name="item_delete"),

    # Payments
    path("payments/", pay.PaymentListView.as_view(), name="payments"),
    path("payments/<int:pk>/", pay.PaymentDetailView.as_view(), name="payment_detail"),

    # Reports
    path("reports/", rep.ReportsView.as_view(), name="reports"),

    # Settings (subscription tariffs)
    path("settings/", st.SettingsListView.as_view(), name="settings"),
    path("settings/tariffs/add/", st.TariffCreateView.as_view(), name="settings_plan_add"),
    path("settings/tariffs/<int:pk>/edit/", st.TariffUpdateView.as_view(), name="settings_plan_edit"),
    path("settings/tariffs/<int:pk>/delete/", st.TariffDeleteView.as_view(), name="settings_plan_delete"),

    # Admins (staff users)
    path("admins/", adm.AdminListView.as_view(), name="admins"),
    path("admins/add/", adm.AdminCreateView.as_view(), name="admin_add"),
    path("admins/<int:pk>/edit/", adm.AdminUpdateView.as_view(), name="admin_edit"),
    path("admins/<int:pk>/delete/", adm.AdminDeleteView.as_view(), name="admin_delete"),
]
