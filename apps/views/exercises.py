from apps.models import Exercise
from apps.models.exercises import MuscleGroup
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import get_language
from django.views.generic import DetailView, ListView, TemplateView

from apps.models.favorites import Favorite


def get_session_workout_type(request):
    workout_type = (request.session.get('workout_type') or Exercise.WorkoutType.GYM).lower()
    if workout_type not in {Exercise.WorkoutType.GYM, Exercise.WorkoutType.HOME}:
        workout_type = Exercise.WorkoutType.GYM
    return workout_type


from apps.views.partial import PartialTabMixin


class MuscleGroupListView(PartialTabMixin, TemplateView):
    template_name = 'exercises/body_parts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["body_parts"] = [
            {"value": choice.value, "label": choice.label}
            for choice in MuscleGroup
        ]
        return context


class ExercisesByMuscleView(ListView):
    queryset = Exercise.objects.order_by('id')
    template_name = 'exercises/exercise_list.html'
    context_object_name = 'exercises'

    def get_queryset(self):
        qs = super().get_queryset()
        muscle_name = (self.kwargs['muscle'] or "").strip().lower()
        qs = qs.filter(primary_body_part__iexact=muscle_name)
        self.muscle = muscle_name
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        lang = (get_language() or "en").split("-")[0]

        try:
            muscle_label = MuscleGroup(self.muscle).label
        except ValueError:
            muscle_label = self.muscle.capitalize()

        context['muscle'] = muscle_label
        context['body_part'] = {'name': muscle_label}

        user = self.request.user
        try:
            user_profile = user.profile
        except AttributeError:
            user_profile = None

        if user_profile:
            exercise_ids = [exercise.id for exercise in context['exercises']]
            favorite_ids = Favorite.objects.filter(
                user=user_profile, exercise_id__in=exercise_ids
            ).values_list('exercise_id', flat=True)
            for exercise in context['exercises']:
                exercise.is_favorited = exercise.id in favorite_ids
            context['collections'] = user_profile.favorite_collections.all()
        else:
            for exercise in context['exercises']:
                exercise.is_favorited = False

        return context

class ExerciseDetailView(LoginRequiredMixin, DetailView):
    model = Exercise

    def get_queryset(self):
        return Exercise.objects.all()
    template_name = 'exercises/exercise_detail.html'
    context_object_name = 'exercise'
    pk_url_kwarg = 'exercise_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language = get_language() or ""
        lang_code = language.split("-")[0]
        name_map = {
            "ru": self.object.name_ru,
            "uz": self.object.name_uz,
        }
        description_map = {
            "ru": self.object.description_ru,
            "uz": self.object.description_uz,
        }
        context["exercise_name"] = name_map.get(lang_code) or self.object.name
        context["exercise_description"] = description_map.get(lang_code) or self.object.description
        final_instructions_list = []
        if hasattr(self.object, 'instructions'):
            for instruction_obj in self.object.instructions.all():
                instruction_text = getattr(instruction_obj, 'text', None)
                if instruction_text:
                    lines = [
                        line.strip()
                        for line in instruction_text.splitlines()
                        if line.strip()
                    ]
                    final_instructions_list.extend(lines)

        context['instructions_list'] = final_instructions_list
        user = self.request.user
        try:
            user_profile = user.profile
        except AttributeError:
            user_profile = None
        if user_profile:
            context['is_favorited'] = Favorite.objects.filter(user=user_profile, exercise=self.object).exists()
            context['favorite_collections'] = user_profile.favorite_collections.all().order_by('-created_at')
        else:
            context['is_favorited'] = False
            context['favorite_collections'] = []
        return context
