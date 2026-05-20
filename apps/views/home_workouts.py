# ============================================================
# apps/views/home_workouts.py — TO'LIQ FAYL
# ============================================================

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.models.workouts import Plan, Program, Workout, WorkoutType, UserWorkoutProgress, WorkoutProgress, HomeWorkout, \
	HomeProgressionSetting
from apps.services import UserProgramService
from apps.services.programs import ProgramGenerationService
from apps.workouts.recommendation import get_recommended_program
from apps.utils.home_progression import calculate_home_week_exercise
from apps.views.workouts import WorkoutCompleteView


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
		qs = Program.objects.filter(
			is_active=True, workout_type=WorkoutType.HOME
		).prefetch_related('plans__weeks__workouts')
		if not self.request.user.is_authenticated or not hasattr(self.request.user, "profile"):
			return qs
		
		profile = self.request.user.profile
		completed_workout_ids = set(
			WorkoutProgress.objects.filter(
				user=profile,
				status=WorkoutProgress.Status.COMPLETED,
			).values_list("workout_id", flat=True)
		)
		
		filtered_programs = []
		for program in qs:
			workout_ids = [
				w.id
				for plan in program.plans.all()
				for week in plan.weeks.all()
				for w in week.workouts.all()
			]
			if workout_ids and all(wid in completed_workout_ids for wid in workout_ids):
				continue
			filtered_programs.append(program)
		
		recommended = get_recommended_program(profile, workout_type=WorkoutType.HOME)
		if recommended:
			filtered_programs.sort(key=lambda p: (p.id != recommended.id, p.id))
		return filtered_programs
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['active_workout_type'] = WorkoutType.HOME
		context['is_home_mode'] = True
		recommended = (
			get_recommended_program(self.request.user.profile, workout_type=WorkoutType.HOME)
			if self.request.user.is_authenticated and hasattr(self.request.user, "profile")
			else None
		)
		if recommended and all(p.id != recommended.id for p in context.get("programs", [])):
			recommended = None
		context['recommended_program'] = recommended
		context['show_recommendation_once'] = bool(self.request.session.pop('show_recommendation_once', False))
		return context


class HomeProgramDetailView(DetailView):
	model = Program
	template_name = 'home/edition_list.html'
	context_object_name = 'program'
	
	def get_queryset(self):
		return Program.objects.filter(
			is_active=True
		).prefetch_related('plans')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['plans'] = self.object.plans.filter(program__workout_type='home').order_by('order')
		context['is_home_mode'] = True
		return context


class HomePlanWeeksView(DetailView):
	"""
	Plan → Weeks ro'yxati.
	Gym dagi PlanWeeksView bilan bir xil logika.
	"""
	model = Plan
	template_name = 'home/plan_weeks.html'
	context_object_name = 'plan'
	
	def get_queryset(self):
		return Plan.objects.filter(
			program__workout_type=WorkoutType.HOME
		).select_related('program')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		ProgramGenerationService.ensure_home_plan_integrity(self.object)
		# weeks — gym dagi plan_weeks.html bilan bir xil context key
		self.request.session['workout_type'] = WorkoutType.HOME
		self.request.session.modified = True
		weeks = self.object.weeks.prefetch_related('workouts').order_by('week_number')
		workouts = []
		for week in weeks:
			for wo in week.workouts.all().order_by('day_number'):
				workouts.append(wo)
		completed_ids = set()
		context['workouts'] = workouts
		context['completed_workout_ids'] = completed_ids
		context['total_weeks'] = weeks.count()
		context['weeks'] = weeks
		context['active_workout_type'] = WorkoutType.HOME
		context['is_home_mode'] = True
		return context


class HomeWorkoutDetailView(LoginRequiredMixin, DetailView):
	"""
	Workout (kun) tafsilotlari + progress.
	"""
	model = Workout
	template_name = 'workouts/home_workout_detail.html'
	context_object_name = 'workout'
	
	def get_queryset(self):
		return Workout.objects.filter(
			week__plan__program__workout_type=WorkoutType.HOME
		).select_related('week__plan__program')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		workout = self.object
		
		workout_exercises = list(
			workout.workout_exercises
			.select_related('exercise')
			.order_by('order', 'id')
		)
		
		progress, _ = UserWorkoutProgress.objects.get_or_create(
			user=self.request.user.profile,
			workout=workout,
		)
		
		current_index = max(progress.current_order - 1, 0)
		current_exercise = (
			workout_exercises[current_index]
			if workout_exercises and current_index < len(workout_exercises)
			else None
		)
		
		setting = HomeProgressionSetting.objects.first() or HomeProgressionSetting.objects.create(key="default")
		week_number = workout.week.week_number
		exercises = []
		rounds = workout.rounds
		rest_seconds = setting.rest_between_rounds
		for wex in workout_exercises:
			calc = calculate_home_week_exercise(workout.rounds, int((wex.minutes or 0) * 60), week_number, setting)
			rounds = calc["rounds"]
			rest_seconds = calc["rest_seconds"]
			exercises.append({
				"name": wex.exercise.name,
				"name_uz": wex.exercise.name_uz,
				"name_ru": wex.exercise.name_ru,
				"image": wex.exercise.thumbnail,
				"duration_seconds": calc["duration_seconds"],
				"order": wex.order,
			})
		total_time_seconds = rounds * sum(x["duration_seconds"] for x in exercises) + max(0, rounds - 1) * rest_seconds
		context.update({
			"workout": workout,
			"exercises": exercises,
			"rounds": rounds,
			"rest_seconds": rest_seconds,
			"total_time_seconds": total_time_seconds,
			"week_number": week_number,
			'progress': progress,
			'current_round': progress.current_round,
			'current_order': progress.current_order,
			'plan': workout.week.plan,
			'week': workout.week,
		})
		return context


class HomeWorkoutDoneView(LoginRequiredMixin, View):
	"""
	Bitta exercise tugatilganda chaqiriladi.
	Logika:
	  - current_order oshadi
	  - Barcha exercise tugasa → round tugaydi, current_order = 1
	  - Barcha round tugasa → is_finished = True
	"""
	
	def post(self, request, pk):
		workout = get_object_or_404(
			Workout.objects.select_related('week__plan__program'),
			pk=pk,
			week__plan__program__workout_type=WorkoutType.HOME,
		)
		
		exercise_count = workout.workout_exercises.count()
		
		if exercise_count == 0:
			return HttpResponseBadRequest("No exercises in workout")
		
		with transaction.atomic():
			progress, _ = UserWorkoutProgress.objects.select_for_update().get_or_create(
				user=request.user.profile,
				workout=workout,
			)
			
			if progress.is_finished:
				return redirect('home_workout_detail', pk=workout.pk)
			
			# Keyingi exercise ga o'tish
			progress.current_order += 1
			
			# Bir round tugadi
			if progress.current_order > exercise_count:
				progress.current_order = 1
				progress.current_round += 1
			
			# Barcha roundlar tugadi
			if progress.current_round > workout.rounds:
				progress.is_finished = True
				progress.current_round = workout.rounds
				progress.current_order = exercise_count
			
			progress.save(update_fields=[
				'current_round', 'current_order',
				'is_finished', 'updated_at'
			])
		
		return redirect('home_workout_detail', pk=workout.pk)


# Bu classni apps/views/home_workouts.py ga qo'shing
# (boshqa importlar allaqachon bor)

from django.db.models import Count
from apps.models import Week  # import qo'shing


class HomeWeekDetailView(DetailView):
	model = Week
	template_name = 'workouts/week_days.html'
	context_object_name = 'week'
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		workouts = self.object.workouts.all().order_by('day_number').annotate(
			exercise_count=Count('workout_exercises')
		)
		
		# Home mode da UserWorkoutProgress orqali completed kunlarni aniqlaymiz
		completed_ids = set()
		if self.request.user.is_authenticated:
			from apps.models.workouts import UserWorkoutProgress
			completed_ids = set(
				UserWorkoutProgress.objects.filter(
					user=self.request.user.profile,
					is_finished=True,
					workout__week=self.object,
				).values_list('workout_id', flat=True)
			)
		
		context['workouts'] = workouts
		context['completed_workout_ids'] = completed_ids
		context['is_home_mode'] = True
		return context

class HomeWorkoutCompleteView(LoginRequiredMixin, View):
    template_name = "workouts/home_workout_complete.html"

    def post(self, request, pk):
        workout = get_object_or_404(
            HomeWorkout.objects.select_related("week__plan__program"),
            pk=pk,
            week__plan__program__workout_type=WorkoutType.HOME,
        )
        total_calories = float(request.POST.get("total_calories", 0) or 0)
        total_duration = int(float(request.POST.get("total_duration", 0) or 0))

        UserWorkoutProgress.objects.filter(
            user=request.user.profile,
            workout=workout,
        ).update(is_finished=True, current_round=workout.rounds)

        return render(request, self.template_name, {
            "workout": workout,
            "workout_summary": {
                "total_calories": total_calories,
                "duration_seconds": total_duration,
                "exercises_completed": workout.workout_exercises.count() * workout.rounds,
                "total_weight": 0,
            }
        })

    def get(self, request, pk):
        workout = get_object_or_404(
            HomeWorkout.objects.select_related("week__plan__program"), pk=pk
        )
        return render(request, self.template_name, {"workout": workout})

class HomeSessionView(LoginRequiredMixin, TemplateView):
	template_name = "workouts/home_session.html"
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		workout = get_object_or_404(HomeWorkout.objects.select_related("week__plan__program"), pk=self.kwargs["pk"])
		
		progress, created = UserWorkoutProgress.objects.get_or_create(user=self.request.user.profile, workout=workout)
		if not created:
			progress.current_round = 1
			progress.current_order = 1
			progress.save(update_fields=['current_round', 'current_order', 'updated_at'])
		
		setting = HomeProgressionSetting.objects.first() or HomeProgressionSetting.objects.create(key="default")
		week_number = workout.week.week_number
		workout_exercises = workout.workout_exercises.select_related("exercise").order_by("order", "id")
		exercises = []
		rounds = workout.rounds
		rest_seconds = setting.rest_between_rounds
		for wex in workout_exercises:
			calc = calculate_home_week_exercise(workout.rounds, int((wex.minutes or 0) * 60), week_number, setting)
			rounds = calc["rounds"];
			rest_seconds = calc["rest_seconds"]
			exercises.append(
				{"name": wex.exercise.name, "name_uz": wex.exercise.name_uz, "name_ru": wex.exercise.name_ru,
				 "image": wex.exercise.thumbnail, "duration_seconds": calc["duration_seconds"], "order": wex.order,
				 "description": wex.exercise.description or ""})
		total_time_seconds = rounds * sum(x["duration_seconds"] for x in exercises) + max(0, rounds - 1) * rest_seconds
		context.update({"workout": workout, "exercises": exercises, "rounds": rounds, "rest_seconds": rest_seconds,
		                "total_time_seconds": total_time_seconds, "week_number": week_number, "current_round": 1,
		                "current_order": 1})
		return context
