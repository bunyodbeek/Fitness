from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from apps.models.workouts import Edition, Program, Workout, WorkoutType, UserWorkoutProgress
from apps.services import UserProgramService


def get_active_mode(request):
    workout_type = (request.session.get('workout_type') or WorkoutType.GYM).lower()
    if workout_type not in {WorkoutType.GYM, WorkoutType.HOME}:
        return WorkoutType.GYM
    return workout_type


class WorkoutModeSwitchView(View):
    def get(self, request, workout_type):
        if workout_type not in {WorkoutType.GYM, WorkoutType.HOME}:
            return HttpResponseBadRequest("Invalid mode")

        request.session['workout_type'] = workout_type
        request.session.modified = True

        if workout_type == WorkoutType.HOME:
            return redirect('home_program_list')
        return redirect('gym_program_list')



class HomeProgramListView(ListView):
    template_name = 'workouts/program_list.html'
    context_object_name = 'programs'

    def get_queryset(self):
        return Program.objects.filter(is_active=True, workout_type=WorkoutType.HOME).prefetch_related('plans')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Plan orqali workoutlarni olish
        workouts = Workout.objects.filter(week__plan__program__in=self.object_list).prefetch_related('workout_exercises')
        context['workouts'] = workouts
        context['total_days'] = workouts.values('day_number').distinct().count()
        context['active_workout_type'] = WorkoutType.HOME
        return context



class HomeProgramDetailView(DetailView):
    model = Program
    template_name = 'home/edition_list.html'
    context_object_name = 'program'

    def get_queryset(self):
        return Program.objects.filter(workout_type=WorkoutType.HOME).prefetch_related('plans')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plans'] = self.object.plans.all()
        return context


class HomePlanWeeksView(DetailView):
    model = Edition
    template_name = 'home/plan_weeks.html'
    context_object_name = 'plan'

    def get_queryset(self):
        return Edition.objects.filter(program__workout_type=WorkoutType.HOME).select_related('program')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workouts = Workout.objects.filter(week__plan=self.object).order_by('day_number').prefetch_related('workout_exercises')
        context['workouts'] = workouts
        context['total_weeks'] = workouts.count()
        return context

class HomeWorkoutDetailView(LoginRequiredMixin, DetailView):
    model = Workout
    template_name = 'home/workout_detail.html'
    context_object_name = 'workout'

    def get_queryset(self):
        return Workout.objects.filter(week__plan__program__workout_type=WorkoutType.HOME).select_related(
            'week__plan__program'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workout = self.object
        workout_exercises = list(
            workout.workout_exercises.select_related('exercise').filter(
                exercise__workout_type=WorkoutType.HOME
            ).order_by('order', 'id')
        )
        progress, _ = UserWorkoutProgress.objects.get_or_create(
            user=self.request.user.profile,
            workout=workout,
        )

        current_index = max(progress.current_order - 1, 0)
        current_exercise = workout_exercises[current_index] if workout_exercises and current_index < len(workout_exercises) else None

        context.update({
            'workout_exercises': workout_exercises,
            'exercise_count': len(workout_exercises),
            'progress': progress,
            'current_exercise': current_exercise,
            'is_home_mode': get_active_mode(self.request) == WorkoutType.HOME,
        })
        return context


class HomeWorkoutDoneView(LoginRequiredMixin, View):
    def post(self, request, pk):
        workout = get_object_or_404(
            Workout.objects.select_related('week__plan__program'),
            pk=pk,
            week__plan__program__workout_type=WorkoutType.HOME,
        )
        exercise_count = workout.workout_exercises.filter(exercise__workout_type=WorkoutType.HOME).count()
        if exercise_count == 0:
            return HttpResponseBadRequest("No exercises in workout")

        with transaction.atomic():
            progress, _ = UserWorkoutProgress.objects.select_for_update().get_or_create(
                user=request.user.profile,
                workout=workout,
            )

            if progress.is_finished:
                return redirect('home_workout_detail', pk=workout.pk)

            progress.current_order += 1
            if progress.current_order > exercise_count:
                progress.current_order = 1
                progress.current_round += 1

            if progress.current_round > workout.rounds:
                progress.is_finished = True
                progress.current_round = workout.rounds
                progress.current_order = exercise_count

            progress.save(update_fields=['current_round', 'current_order', 'is_finished', 'updated_at'])

        return redirect('home_workout_detail', pk=workout.pk)

class CloneProgramToCustomView(LoginRequiredMixin, View):
    def post(self, request, program_id):
        source_program = get_object_or_404(Program, id=program_id)
        # Service orqali klonlash (sozlamalari bilan birga)
        new_custom_program = UserProgramService.clone_program_for_user(
            source_program=source_program,
            user_profile=request.user.profile,
            name=f"My {source_program.name}"
        )
        return redirect('my_custom_programs_list')