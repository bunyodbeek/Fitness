from django.urls import path

from apps.models.workouts import WorkoutType
from apps.bot.bot_view import TelegramWebhookView
from apps.views import (
	
	ExerciseDetailView,
	ExercisesByMuscleView,
	FavoritesListView,
	MuscleGroupListView,
	OnboardingView,
	PlanWeeksView,
	ProfileView,
	ProgramDetailView,
	ProgramListView,
	ProgressView,
	QuestionnaireSubmitAPIView,
	SettingsView,
	LanguageSelectionAPIView,
	TelegramAuthAPIView,
	ToggleFavoriteView,
	UpdateProfileView,
	WorkoutTypeSelectionView,
	WorkoutCompleteView,
	WorkoutDetailView,
	WorkoutStartView,
	FirstLoginProgramAssignView,
	CloneProgramView,
	CreateCustomProgramView, AnimationView,
)
from apps.views.favorite import (
	CollectionDeleteView,
	CollectionUpdateView,
	CreateCollectionView,
	FavoriteToggleAPIView,
	ExerciseRemoveFromCollection,
    UserCollectionsAPIView,
    UserCustomProgramListView,
    CreateCustomProgramView as FavoritesCreateCustomProgramView,
    CustomProgramStartView,
    CustomProgramCompleteView,
)
from apps.views.users import (
	AdminAnalyticsView,
	ChangeLanguageView,
	ManageSubscriptionView,
	PaymentHistoryView,
)
from apps.views.home_workouts import (
	HomeProgramListView,
	HomeWorkoutDoneView,
	HomeWorkoutCompleteView,
	WorkoutModeSwitchView, HomeSessionView, HomeWeekDetailView,
)

from apps.views.handbook import (
	HandbookCategoryListView,
	HandbookSubCategoryListView,
	HandbookItemListView,
	HandbookItemDetailView,
	HandbookSearchView,
	HandbookByCategoryView,
)
from apps.views.workouts import WeekDetailView

urlpatterns = [
	path('', AnimationView.as_view(), name='animation'),
	
	# API endpoints
	path('api/questionnaire/submit/', QuestionnaireSubmitAPIView.as_view(), name='questionnaire_submit'),
	path('api/telegram-auth/', TelegramAuthAPIView.as_view(), name='telegram_auth'),
	path('api/language/select/', LanguageSelectionAPIView.as_view(), name='language_select'),
	path('api/workout-type/select/', WorkoutTypeSelectionView.as_view(), name='workout_type_select'),
	path('miniapp/questionnaire/', OnboardingView.as_view(), name='onboarding'),
	
	# Exercises
	path('exercises/', MuscleGroupListView.as_view(), name='muscle_groups'),
	path('exercises/<str:muscle>/', ExercisesByMuscleView.as_view(), name='exercises_by_muscle'),
	path('exercises/detail/<int:exercise_id>/', ExerciseDetailView.as_view(), name='exercise_detail'),
	path('exercises/favorite/toggle/<int:exercise_id>/', ToggleFavoriteView.as_view(), name='toggle_favorite'),
	
	# User profile & settings
	path('users/profile/', ProfileView.as_view(), name='user_profile'),
	path('user/progress/', ProgressView.as_view(), name='user_progress'),
	path('users/profile/update/', UpdateProfileView.as_view(), name='profile_update'),
	path('users/settings/', SettingsView.as_view(), name='settings'),
	path('users/subscription/', ManageSubscriptionView.as_view(), name='manage_subscription'),
	path('users/payments/', PaymentHistoryView.as_view(), name='payment_history'),
	path('change/language/', ChangeLanguageView.as_view(), name='change_language'),
	
	# Program assignment/customization
	path('api/programs/assign-first-login/', FirstLoginProgramAssignView.as_view(), name='assign_first_login_program'),
	path('api/programs/<int:program_id>/clone/', CloneProgramView.as_view(), name='clone_program'),
	path('api/programs/custom/create/', CreateCustomProgramView.as_view(), name='create_custom_program'),
	
	# Workout programs (default + gym scoped)
	path('workout/', ProgramListView.as_view(), name='program_list'),
	path('program/<int:pk>/', ProgramDetailView.as_view(), name='program_detail'),
	path('plan/<int:pk>/', PlanWeeksView.as_view(), name='plan_weeks'),
	path('edition/<int:pk>/', PlanWeeksView.as_view(), name='edition_detail'),
	path('week/<int:pk>/', WeekDetailView.as_view(), name='week_detail'),
	path('workout/<int:pk>/', WorkoutDetailView.as_view(), name='workout_detail'),
	path('workout/<int:pk>/start/', WorkoutStartView.as_view(), name='workout_start'),
	path('workout/<int:pk>/complete/', WorkoutCompleteView.as_view(), name='workout_complete'),
	
	path('gym/programs/', ProgramListView.as_view(forced_workout_type=WorkoutType.GYM), name='gym_program_list'),
	path('gym/program/<int:pk>/', ProgramDetailView.as_view(forced_workout_type=WorkoutType.GYM),
	     name='gym_program_detail'),
	path('gym/plan/<int:pk>/', PlanWeeksView.as_view(forced_workout_type=WorkoutType.GYM), name='gym_plan_weeks'),
	path('gym/workout/<int:pk>/', WorkoutDetailView.as_view(forced_workout_type=WorkoutType.GYM),
	     name='gym_workout_detail'),
	path('gym/workout/<int:pk>/start/', WorkoutStartView.as_view(forced_workout_type=WorkoutType.GYM),
	     name='gym_workout_start'),
	path('gym/workout/<int:pk>/complete/', WorkoutCompleteView.as_view(forced_workout_type=WorkoutType.GYM),
	     name='gym_workout_complete'),
	
	# Home mode
	path('mode/<str:workout_type>/', WorkoutModeSwitchView.as_view(), name='workout_mode_switch'),
	path('home/programs/', HomeProgramListView.as_view(), name='home_program_list'),
	path('home/program/<int:pk>/', ProgramDetailView.as_view(forced_workout_type=WorkoutType.HOME), name='home_program_detail'),
	path('home/plan/<int:pk>/', PlanWeeksView.as_view(forced_workout_type=WorkoutType.HOME), name='home_plan_weeks'),
	path('home/week/<int:pk>/', HomeWeekDetailView.as_view(), name='home_week_detail'),
	path('home/workout/<int:pk>/', WorkoutDetailView.as_view(forced_workout_type=WorkoutType.HOME), name='home_workout_detail'),
	path('home/workouts/<int:pk>/', WorkoutDetailView.as_view(forced_workout_type=WorkoutType.HOME), name='home_workout_detail_legacy'),
	path('home/workout/<int:pk>/done/', HomeWorkoutDoneView.as_view(), name='home_workout_done'),
	path('home/workout/<int:pk>/session/', HomeSessionView.as_view(), name='home_workout_session'),
	path('home/workout/<int:pk>/complete/', HomeWorkoutCompleteView.as_view(), name='home_workout_complete'),
	path('home/workouts/<int:pk>/done/', HomeWorkoutDoneView.as_view(), name='home_workout_done_legacy'),
	
	# HANDBOOK - yangi qo'shildi (My Trainer o'rniga)
	path('handbook/', HandbookCategoryListView.as_view(), name='handbook_home'),
	path('handbook/search/', HandbookSearchView.as_view(), name='handbook_search'),
	path('handbook/category/<slug:category_slug>/all/', HandbookByCategoryView.as_view(), name='handbook_category_all'),
	path('handbook/<slug:category_slug>/', HandbookSubCategoryListView.as_view(), name='handbook_subcategories'),
	path('handbook/<slug:category_slug>/<slug:subcategory_slug>/', HandbookItemListView.as_view(),
	     name='handbook_items'),
	path('handbook/<slug:category_slug>/<slug:subcategory_slug>/<slug:item_slug>/', HandbookItemDetailView.as_view(),
	     name='handbook_item_detail'),
	
	# Bot webhook
	path("bot/webhook/", TelegramWebhookView.as_view(), name="telegram_webhook"),
	
	# Admin panel
	path('panel/', AdminAnalyticsView.as_view(), name='admin_page'),
	
	path('favorites/', FavoritesListView.as_view(), name='favorite_list_page'),
	path('favorites/collection/<int:collection_id>/toggle/', FavoriteToggleAPIView.as_view(), name='favorite-toggle'),
    path('api/collections/', UserCollectionsAPIView.as_view(), name='user_collections_api'),
	path("create/collection/", CreateCollectionView.as_view(), name="favorites"),
	path('collection/delete/<int:collection_id>/', CollectionDeleteView.as_view(), name="collection_delete"),
	path('collection/update/<int:collection_id>/', CollectionUpdateView.as_view(), name="collection_update"),
	path('collection/remove-exercise/<int:collection_id>/<int:favorited_id>/', ExerciseRemoveFromCollection.as_view(),
	     name="exercise_remove"),
    path('favorites/programs/', UserCustomProgramListView.as_view(), name='user_custom_program_list'),
    path('favorites/programs/create/', FavoritesCreateCustomProgramView.as_view(), name='favorites_create_custom_program'),
    path('favorites/programs/<int:pk>/start/', CustomProgramStartView.as_view(), name='custom_program_start'),
    path('favorites/programs/<int:pk>/complete/', CustomProgramCompleteView.as_view(), name='custom_program_complete'),

]
