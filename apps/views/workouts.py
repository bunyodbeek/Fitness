import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render, get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView
import math

from apps.models import Program, Plan, Week
from apps.models.workouts import Workout, WorkoutExercise, WorkoutProgress, WorkoutType
from apps.workouts.recommendation import get_recommended_program


def get_session_workout_type(request, forced_type=None):
	if forced_type in {WorkoutType.GYM, WorkoutType.HOME}:
		request.session['workout_type'] = forced_type
		request.session.modified = True
		return forced_type
	
	requested_type = (request.GET.get('type') or '').lower().strip()
	if requested_type in {WorkoutType.GYM, WorkoutType.HOME}:
		request.session['workout_type'] = requested_type
		request.session.modified = True
		return requested_type
	
	workout_type = (request.session.get('workout_type') or WorkoutType.GYM).lower()
	if workout_type not in {WorkoutType.GYM, WorkoutType.HOME}:
		workout_type = WorkoutType.GYM
	return workout_type


class AnimationView(TemplateView):
	template_name = 'animation.html'


# --- 1. Programmalar Ro'yxati ---
class ProgramListView(ListView):
	forced_workout_type = None
	queryset = Program.objects.filter(is_active=True).prefetch_related('plans')
	template_name = 'workouts/program_list.html'
	context_object_name = 'programs'
	forced_workout_type = None
	
	def active_workout_type(self):
		return get_session_workout_type(self.request, self.forced_workout_type)
	
	def get_queryset(self):
		workout_type = self.active_workout_type()
		qs = Program.objects.filter(is_active=True, workout_type=workout_type).prefetch_related('plans__weeks__workouts')
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

		recommended = get_recommended_program(profile, workout_type=workout_type)
		if recommended:
			filtered_programs.sort(key=lambda p: (p.id != recommended.id, p.id))
		return filtered_programs
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		active_type = self.active_workout_type()
		recommended = get_recommended_program(self.request.user.profile, workout_type=active_type) \
			if self.request.user.is_authenticated and hasattr(self.request.user, "profile") else None
		if recommended and all(p.id != recommended.id for p in context.get("programs", [])):
			recommended = None
		context['active_workout_type'] = active_type
		context['is_home_mode'] = active_type == WorkoutType.HOME
		context['recommended_program'] = recommended
		context['show_recommendation_once'] = bool(self.request.session.pop('show_recommendation_once', False))
		return context


# --- 2. Programma ichidagi Planlar ---
class ProgramDetailView(DetailView):
	forced_workout_type = None
	
	model = Program
	template_name = 'workouts/edition_list.html'
	context_object_name = 'program'

	def get_queryset(self):
		workout_type = get_session_workout_type(self.request, self.forced_workout_type)
		return Program.objects.filter(is_active=True, workout_type=workout_type).prefetch_related('plans')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		active_type = self.object.workout_type
		context['plans'] = self.object.plans.filter(program__workout_type=active_type).order_by('order')
		context['active_workout_type'] = active_type
		context['is_home_mode'] = active_type == WorkoutType.HOME
		return context


# --- 3. Plan ichidagi 6 ta HAFTA (Week List) ---
class PlanWeeksView(DetailView):
	forced_workout_type = None
	model = Plan
	template_name = 'workouts/plan_weeks.html'
	context_object_name = 'plan'
	
	def get_queryset(self):
		w_type = get_session_workout_type(self.request, self.forced_workout_type)
		
	
		return Plan.objects.filter(program__workout_type=w_type)
	
	def get(self, request, *args, **kwargs):
		# Bu yerda try-except qo'shsak xatoni aniqroq ko'ramiz
		try:
			return super().get(request, *args, **kwargs)
		except Http404:
			# Agar plan topilmasa, bazada bunaqa id va turdagi plan borligini tekshiring
			raise Http404(
				f"IDsi {kwargs.get('pk')} bo'lgan plan tanlangan tur ({get_session_workout_type(request, self.forced_workout_type)}) uchun topilmadi.")
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		# Plan ichidagi hamma haftalarni chiqaramiz
		active_type = self.object.program.workout_type
		context['weeks'] = self.object.weeks.all().order_by('week_number')
		context['active_workout_type'] = active_type
		context['is_home_mode'] = active_type == WorkoutType.HOME
		return context


# --- 4. Hafta ichidagi KUNLAR (Day List) ---
class WeekDetailView(DetailView):
	forced_workout_type = None
	
	model = Week
	template_name = 'workouts/week_days.html'  # Yangi template yaratishingiz kerak
	context_object_name = 'week'
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		# Shu haftaga tegishli hamma kunlarni olish
		active_type = self.object.plan.program.workout_type
		workouts = self.object.workouts.all().order_by('day_number').annotate(
			exercise_count=Count('workout_exercises')
		)
		
		# Qaysi kunlar bajarilganini aniqlash
		profile = getattr(self.request.user, 'profile', None)
		completed_ids = set()
		if profile:
			completed_ids = set(WorkoutProgress.objects.filter(
				user=profile,
				status=WorkoutProgress.Status.COMPLETED,
				workout__week=self.object
			).values_list('workout_id', flat=True))
		
		context['workouts'] = workouts
		context['completed_workout_ids'] = completed_ids
		context['active_workout_type'] = active_type
		context['is_home_mode'] = active_type == WorkoutType.HOME
		return context


# --- 5. Kun tafsilotlari (Mashqlar ro'yxati va START tugmasi) ---
class WorkoutDetailView(DetailView):
	forced_workout_type = None
	
	model = Workout
	template_name = 'workouts/workout_detail.html'
	context_object_name = 'workout'

	def get_queryset(self):
		workout_type = get_session_workout_type(self.request, self.forced_workout_type)
		return Workout.objects.filter(week__plan__program__workout_type=workout_type).select_related('week__plan__program')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		workout = self.object
		week_workouts = list(workout.week.workouts.all().order_by('day_number', 'id'))
		total_days = len(week_workouts)
		current_day = next((idx for idx, w in enumerate(week_workouts, start=1) if w.id == workout.id), 1)
		prev_workout = week_workouts[current_day - 2] if current_day > 1 else None
		next_workout = week_workouts[current_day] if current_day < total_days else None
		
		workout_exercises = WorkoutExercise.objects.filter(
			workout=workout,
		).select_related('exercise').order_by('order')
		
		active_type = workout.week.plan.program.workout_type

		context.update({
			'plan': workout.week.plan,
			'week': workout.week,
			'current_day': current_day,
			'total_days': total_days,
			'day_range': range(1, total_days + 1),
			'prev_workout': prev_workout,
			'next_workout': next_workout,
			'workout_exercises': workout_exercises,
			'total_exercises': workout_exercises.count(),
			'active_workout_type': active_type,
			'is_home_mode': active_type == WorkoutType.HOME,
		})
		return context


# --- 6. Mashg'ulotni BOSHLASH (Active Workout) ---
class WorkoutStartView(LoginRequiredMixin, View):
	forced_workout_type = None
	
	def get(self, request, pk):
		workout = get_object_or_404(Workout, pk=pk)
		wtype = (
			self.forced_workout_type
			or workout.week.plan.program.workout_type
			or get_session_workout_type(request)
		)
		
		workout_exercises = WorkoutExercise.objects.filter(
			workout=workout
		).select_related('exercise').order_by('order')
		
		if not workout_exercises.exists():
			return render(request, 'error_page.html', {"error_message": "Mashqlar topilmadi."})
		
		# Avvalgi progressni tekshirish
		progress = WorkoutProgress.objects.filter(
			user=request.user.profile,
			workout=workout,
			status=WorkoutProgress.Status.IN_PROGRESS,
		).first()
		
		template = 'workouts/active_workout.html'
		
		# ✅ Avval o'zgaruvchiga saqla
		exercises_data = self._prepare_exercises_data(
			workout_exercises,
			getattr(request, "LANGUAGE_CODE", "en")
		)
		return render(request, template, {
			"workout": workout,
			"exercises_json": json.dumps(exercises_data),
			"total_exercises": len(exercises_data),
			"initial_exercise_index": progress.current_exercise_index if progress else 0,
			"workout_complete_url": (
				f"/{getattr(request, 'LANGUAGE_CODE', 'en')}/gym/workout/{workout.pk}/complete/"
				if wtype == WorkoutType.GYM
				else f"/{getattr(request, 'LANGUAGE_CODE', 'en')}/workout/{workout.pk}/complete/"
			),
			"workout_start_url": (
				f"/{getattr(request, 'LANGUAGE_CODE', 'en')}/gym/workout/{workout.pk}/start/"
				if wtype == WorkoutType.GYM
				else f"/{getattr(request, 'LANGUAGE_CODE', 'en')}/workout/{workout.pk}/start/"
			),
		})
	
	def _prepare_exercises_data(self, workout_exercises, lang_code="en"):
		data = []
		for wex in workout_exercises:
			ex = wex.exercise
			
			name = None
			for field in [f"name_{lang_code}", "name_en", "name"]:
				name = getattr(ex, field, None)
				if name:
					break
			
			data.append({
				"exercise_id": ex.id,
				"name": name or "Exercise",
				"sets": max(wex.sets, 1),
				"reps": max(wex.reps, 1),
				"duration_minutes": float(wex.minutes or 0),
				"rest_seconds": int(getattr(wex, 'rest_seconds', 60)),
				"calories_per_minute": float(getattr(wex, 'calories_per_minute', 5.0)),
				"type": "cardio" if (wex.minutes or 0) > 0 and (wex.sets or 1) <= 1 else "strength",
				"recommended_weight": float(getattr(wex, 'recommended_weight', 0)),
				"image": ex.thumbnail.url if ex.thumbnail else None,
				"video": ex.video.url if ex.video else None,
				"description": getattr(ex, f"description_{lang_code}", None) or getattr(ex, "description", None) or "",
			})
		return data


class WorkoutCompleteView(LoginRequiredMixin, View):
	forced_workout_type = None
	template_name = "workouts/workout_complete.html"

	@staticmethod
	def _safe_float(value, default=0.0):
		try:
			parsed = float(value)
		except (ValueError, TypeError):
			return default
		return parsed if math.isfinite(parsed) else default

	@staticmethod
	def _safe_int(value, default=0):
		try:
			parsed = int(float(value))
		except (ValueError, TypeError):
			return default
		return parsed if math.isfinite(parsed) else default
	
	def get_template_name(self, request):
		return self.template_name
	
	def post(self, request, pk):
		workout = get_object_or_404(Workout, pk=pk, week__plan__program__workout_type=get_session_workout_type(request,
		                                                                                                       getattr(
			                                                                                                       self,
			                                                                                                       "forced_workout_type",
			                                                                                                       None)))
		
		total_calories = self._safe_float(request.POST.get("total_calories", 0))
		total_duration = self._safe_int(request.POST.get("total_duration", 0))
		exercises_completed = self._safe_int(request.POST.get("exercises_completed", 0))
		total_weight = self._safe_float(request.POST.get("total_weight", 0))
		
		WorkoutProgress.objects.filter(
			user=request.user.profile,
			workout=workout,
			status=WorkoutProgress.Status.IN_PROGRESS,
		).delete()
		
		WorkoutProgress.objects.create(
			user=request.user.profile,
			workout=workout,
			total_calories=total_calories,
			total_duration_seconds=total_duration,
			exercises_completed=exercises_completed,
			status=WorkoutProgress.Status.COMPLETED,
		)
		
		return render(request, self.get_template_name(request), {
			"workout": workout,
			"workout_summary": {
				"total_calories": total_calories,
				"duration_seconds": total_duration,
				"exercises_completed": exercises_completed,
				"total_reps": 0,
				"total_weight": total_weight
			}
		})
	
	def get(self, request, pk):
		workout = get_object_or_404(Workout, pk=pk, week__plan__program__workout_type=get_session_workout_type(request,
		                                                                                                       getattr(
			                                                                                                       self,
			                                                                                                       "forced_workout_type",
			                                                                                                       None)))
		return render(request, self.get_template_name(request), {"workout": workout})

#
# class MyTrainerView(LoginRequiredMixin, TemplateView):
#     template_name = 'my_trainer/my_trainer.html'
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         profile = self.request.user.profile
#         user_program = UserProgram.objects.filter(user=profile, is_active=True).last()
#
#         if not user_program:
#             context['workout_days'] = []
#             context['completed_count'] = 0
#             context['workouts_this_week'] = 0
#             context['active_weeks'] = 0
#             return context
#
#         workout_days = WorkoutDay.objects.filter(program=user_program)
#         completed_count = workout_days.filter(status='completed').count()
#
#         today = timezone.now().date()
#         start_of_week = today - timezone.timedelta(days=today.weekday())
#         end_of_week = start_of_week + timezone.timedelta(days=6)
#         workouts_this_week = workout_days.filter(status='completed', completed_at__date__gte=start_of_week,
#                                                  completed_at__date__lte=end_of_week).count()
#
#         active_weeks = (workout_days.count() + 6) // 7
#
#         context['workout_days'] = workout_days
#         context['completed_count'] = completed_count
#         context['workouts_this_week'] = workouts_this_week
#         context['active_weeks'] = active_weeks
#         context['user'] = profile
#         return context

#
# class MyTrainerWorkoutDaysView(LoginRequiredMixin, TemplateView):
#     template_name = 'my_trainer/my_trainer_days.html'
#
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         profile = self.request.user.profile
#
#         user_program = UserProgram.objects.filter(user=profile, is_active=True).first()
#         if user_program:
#             workout_days = WorkoutDay.objects.filter(program=user_program).prefetch_related(
#                 'exercises', 'exercises__exercise'
#             ).order_by('order')
#             context['workout_days'] = workout_days
#         else:
#             context['workout_days'] = []
#
#         return context
#
#
# class MyTrainerWorkoutStartView(LoginRequiredMixin, View):
#     template_name = 'my_trainer/my_trainer_start.html'
#
#     def get(self, request, day, *args, **kwargs):
#         profile = request.user.profile
#
#         user_program = get_object_or_404(UserProgram, user=profile, is_active=True)
#
#         workout_day = get_object_or_404(WorkoutDay, program=user_program, order=day)
#
#         exercises_queryset = UserProgramExercise.objects.filter(day=workout_day)
#
#         if not exercises_queryset.exists():
#             raise Http404("Bu kunda hech qanday mashq mavjud emas.")
#
#         current_exercise = exercises_queryset.first()
#
#         context = {
#             'current_exercise': current_exercise,
#             'exercises': {
#                 'sets': current_exercise.sets,
#                 'reps': current_exercise.reps,
#             },
#             'workout_day': workout_day,
#         }
#
#         return render(request, self.template_name, context)
