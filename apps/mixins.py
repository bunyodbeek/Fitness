from apps.models.workouts import WorkoutType
from apps.views.home_workouts import get_active_mode

class ModeFilterMixin:

    def active_mode(self):
        return get_active_mode(self.request)

    def program_filter_kwargs(self):
        return {"workout_type": self.active_mode()}