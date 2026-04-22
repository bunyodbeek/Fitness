from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import HttpResponseBadRequest, Http404
from django.shortcuts import redirect, render, get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.models import Program, Plan, Week
from apps.models.workouts import Workout, WorkoutExercise, WorkoutProgress, WorkoutType


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
		return Program.objects.filter(is_active=True, workout_type=workout_type).prefetch_related('plans')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		active_type = self.active_workout_type()
		context['active_workout_type'] = active_type
		context['is_home_mode'] = active_type == WorkoutType.HOME
		return context


# --- 2. Programma ichidagi Planlar ---
class ProgramDetailView(DetailView):
	forced_workout_type = None
	
	model = Program
	template_name = 'workouts/edition_list.html'
	context_object_name = 'program'
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['plans'] = self.object.plans.all().order_by('order')
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
		context['weeks'] = self.object.weeks.all().order_by('week_number')
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
		return context


# --- 5. Kun tafsilotlari (Mashqlar ro'yxati va START tugmasi) ---
class WorkoutDetailView(DetailView):
	forced_workout_type = None
	
	model = Workout
	template_name = 'workouts/workout_detail.html'
	context_object_name = 'workout'
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		workout = self.object
		workout_type = get_session_workout_type(self.request)
		
		workout_exercises = WorkoutExercise.objects.filter(
			workout=workout,
			exercise__workout_type=workout_type,
		).select_related('exercise').order_by('order')
		
		context.update({
			'plan': workout.week.plan,
			'workout_exercises': workout_exercises,
			'total_exercises': workout_exercises.count(),
		})
		return context


# --- 6. Mashg'ulotni BOSHLASH (Active Workout) ---
class WorkoutStartView(LoginRequiredMixin, View):
	forced_workout_type = None
	
	def get(self, request, pk):
		workout = get_object_or_404(Workout, pk=pk)
		wtype = get_session_workout_type(request)
		
		workout_exercises = WorkoutExercise.objects.filter(
			workout=workout,
			exercise__workout_type=wtype
		).select_related('exercise').order_by('order')
		
		if not workout_exercises.exists():
			return render(request, 'error_page.html', {"error_message": "Mashqlar topilmadi."})
		
		# Avvalgi progressni tekshirish
		progress = WorkoutProgress.objects.filter(
			user=request.user.profile,
			workout=workout,
			status=WorkoutProgress.Status.IN_PROGRESS,
		).first()
		
		template = 'workouts/home_active_workout.html' if wtype == WorkoutType.HOME else 'workouts/active_workout.html'
		
		# ✅ Avval o'zgaruvchiga saqla
		exercises_data = self._prepare_exercises_data(
			workout_exercises,
			getattr(request, "LANGUAGE_CODE", "en")
		)
		return render(request, template, {
			"workout": workout,
			"exercises": self._prepare_exercises_data(workout_exercises, getattr(request, "LANGUAGE_CODE", "en")),
			"total_exercises": len(exercises_data),
			"initial_exercise_index": progress.current_exercise_index if progress else 0,
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
				"type": "cardio" if (wex.minutes or 0) > 0 else "strength",
				"image": ex.thumbnail.url if ex.thumbnail else None,
				"video": ex.video.url if ex.video else None,
				"description": getattr(ex, f"description_{lang_code}", None) or getattr(ex, "description", None) or "",
			})
		return data


class WorkoutCompleteView(LoginRequiredMixin, View):
	forced_workout_type = None
	template_name = "workouts/workout_complete.html"
	
	def get_template_name(self, request):
		return self.template_name
	
	def post(self, request, pk):
		workout = get_object_or_404(Workout, pk=pk, week__plan__program__workout_type=get_session_workout_type(request,
		                                                                                                       getattr(
			                                                                                                       self,
			                                                                                                       "forced_workout_type",
			                                                                                                       None)))
		
		try:
			total_calories = float(request.POST.get("total_calories", 0))
			total_duration = int(request.POST.get("total_duration", 0))
			exercises_completed = int(request.POST.get("exercises_completed", 0))
		except (ValueError, TypeError):
			return HttpResponseBadRequest("Invalid input data")
		
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
				"total_weight": 0
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
