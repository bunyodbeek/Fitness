# apps/models/__init__.py

from apps.models.exercises import Exercise, ExerciseInstruction
from apps.models.users import (
	User,
	UserProfile,  # Added
	UserMotivation,  # Added
	UserProgram,
	WorkoutDay,  # Added
	UserProgramExercise  # Added
)
from apps.models.workouts import (
	Plan,
	Week,
	Workout,
	WorkoutExercise,
	Program,
	
)

# If you have a favorites.py, add it here:
# from apps.models.favorites import Favorite, FavoriteExercise, FavoriteProgram
