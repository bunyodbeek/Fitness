from apps.views.exercises import ExerciseDetailView, ExercisesByMuscleView, MuscleGroupListView
from apps.views.favorite import FavoritesListView, ToggleFavoriteView
from apps.views.programs import CloneProgramView, CreateCustomProgramView, FirstLoginProgramAssignView
from apps.views.users import (
    OnboardingView,
    ProfileView,
    ProgressView,
    QuestionnaireSubmitAPIView,
    SettingsView,
    TelegramAuthAPIView,
    LanguageSelectionAPIView,
    WorkoutTypeSelectionView,
    UpdateProfileView,
)
from apps.views.workouts import (
    AnimationView,

    PlanWeeksView,
    ProgramDetailView,
    ProgramListView,
    WorkoutDetailView,
    WorkoutCompleteView,
    WorkoutStartView,
)
