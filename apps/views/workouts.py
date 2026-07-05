import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F
from django.http import Http404
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _, get_language
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView
import math

from apps.models import Program, Plan, Week
from apps.models.workouts import Workout, WorkoutExercise, WorkoutProgress, WorkoutType
from apps.workouts.recommendation import get_recommended_program
from apps.utils.mixins import PremiumRequiredMixin


# ─────────────────────────────────────────────────────────────
# Programs-page (Mashg'ulotlar) shared context builder.
# Gym (ProgramListView) ham, Home (HomeProgramListView) ham
# bir xil `workouts/program_list.html` shablonidan foydalanadi.
# ─────────────────────────────────────────────────────────────

# Kategoriya tartibi + emoji + tagline (goal bo'yicha guruhlash uchun).
GOAL_CARDS = [
	(Program.Goal.MUSCLE_GAIN, "💪", _("Build size & strength")),
	(Program.Goal.FAT_LOSS, "🔥", _("Burn fat & get lean")),
	(Program.Goal.GENERAL, "⚡", _("Stay fit & healthy")),
	(Program.Goal.RECOMPOSITION, "🔄", _("Build muscle & burn fat")),
]


def _localized_workout_title(workout):
	"""Workout sarlavhasini aktiv tilga moslab qaytaradi, bo'sh bo'lsa 'Day N'."""
	lang = (get_language() or "en").split("-")[0]
	value = getattr(workout, f"title_{lang}", None) or workout.title
	if value:
		return value
	return _("Day %(n)d") % {"n": workout.day_number}


def _program_ordered_workouts(program):
	"""Birinchi plan bo'yicha (week_number, workout) ro'yxati — prefetch'dan foydalanadi."""
	plan = next(iter(program.plans.all()), None)
	if not plan:
		return None, []
	pairs = []
	for week in sorted(plan.weeks.all(), key=lambda w: w.week_number):
		for wo in sorted(week.workouts.all(), key=lambda w: (w.day_number, w.id)):
			pairs.append((week.week_number, wo))
	return plan, pairs


def compute_program_progress(program, completed_ids):
	"""
	Hero-kartochka uchun progress ma'lumotlari.
	completed_ids — foydalanuvchi tugatgan workout id'lari to'plami.
	"""
	plan, pairs = _program_ordered_workouts(program)
	total = len(pairs)
	if not plan or total == 0:
		return {
			"started": False, "percent": 0,
			"current_week": 1, "total_weeks": getattr(plan, "weeks_count", 6) if plan else 6,
			"next_workout_title": "",
		}
	done = sum(1 for _wn, wo in pairs if wo.id in completed_ids)
	total_weeks = plan.weeks_count or max((wn for wn, _ in pairs), default=6)
	# Birinchi tugallanmagan workout — "bugungi" mashg'ulot.
	next_pair = next(((wn, wo) for wn, wo in pairs if wo.id not in completed_ids), None)
	if next_pair:
		current_week, next_wo = next_pair
		next_title = _localized_workout_title(next_wo)
	else:
		current_week, next_title = total_weeks, ""
	return {
		"started": done > 0,
		"percent": int(round(done / total * 100)) if total else 0,
		"current_week": current_week,
		"total_weeks": total_weeks,
		"next_workout_title": next_title,
	}


def _all_workout_ids(program):
	return [
		wo.id
		for plan in program.plans.all()
		for week in plan.weeks.all()
		for wo in week.workouts.all()
	]


def _program_detail_url(program, workout_type):
	if workout_type == WorkoutType.HOME:
		return reverse("home_program_detail", args=[program.id])
	return reverse("gym_program_detail", args=[program.id])


def _workout_detail_url(workout, workout_type):
	if workout_type == WorkoutType.HOME:
		return reverse("home_workout_detail", args=[workout.id])
	return reverse("workout_detail", args=[workout.id])


def build_programs_page_context(request, workout_type):
	"""
	`workouts/program_list.html` uchun barcha kontekst:
	  - recommended_card  (hero, onboarding asosida, tugatilsa yashiriladi)
	  - one_time_cards    (bir martalik programmalar)
	  - categories        (goal bo'yicha guruhlangan, har birida popular_id)
	  - explore_programs  (grid/"plitka" rejimi uchun tekis ro'yxat)
	"""
	profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None

	completed_ids = set()
	if profile:
		completed_ids = set(
			WorkoutProgress.objects.filter(
				user=profile, status=WorkoutProgress.Status.COMPLETED,
			).values_list("workout_id", flat=True)
		)

	# ── Daraja (level) filtri: Beginner / Advanced dropdown ──
	valid_levels = {Program.Level.BEGINNER, Program.Level.ADVANCED}
	active_level = (request.GET.get("level") or "").lower().strip()
	if active_level not in valid_levels:
		active_level = ""

	# ── Explore (kategoriya + grid) uchun asosiy queryset ──
	explore_qs = (
		Program.objects.filter(
			is_active=True,
			workout_type=workout_type,
			type=Program.ProgramType.ADMIN,
			is_individual=False,
			is_one_time=False,
		)
		.prefetch_related("plans__weeks__workouts")
		.order_by("id")
	)
	if active_level:
		explore_qs = explore_qs.filter(level=active_level)

	# Tugatilgan programmalar ham ro'yxatda qoladi (yashirilmaydi).
	explore_programs = list(explore_qs)

	# ── Recommended hero ──
	# Tavsiya kartochkasi FAQAT gym rejimida ko'rsatiladi.
	# Home rejimida mos individual tavsiya programmasi ko'pincha bo'lmaydi va
	# (eski xulq-atvorda) gym programmasiga "home_program_detail" havolasi
	# yasalib, ochilganda 404 berardi. Shuning uchun home'da umuman ko'rsatmaymiz.
	recommended_card = None
	if workout_type == WorkoutType.GYM:
		recommended = get_recommended_program(profile, workout_type=workout_type) if profile else None
		# Tavsiya programmasi tanlangan rejimga MOS bo'lishi shart (404 oldini olish).
		if recommended and recommended.workout_type == workout_type and not recommended.is_one_time:
			rec_ids = _all_workout_ids(recommended)
			fully_completed = bool(rec_ids) and all(wid in completed_ids for wid in rec_ids)
			if not fully_completed:
				recommended_card = {
					"program": recommended,
					"url": _program_detail_url(recommended, workout_type),
					"progress": compute_program_progress(recommended, completed_ids),
				}

	# ── One-time cards ──
	one_time_cards = []
	one_time_qs = (
		Program.objects.filter(
			is_active=True, workout_type=workout_type, is_one_time=True,
		)
		.prefetch_related("plans__weeks__workouts")
		.order_by("id")
	)
	for program in one_time_qs:
		workout = program.first_workout
		if not workout:
			continue
		one_time_cards.append({
			"program": program,
			"url": _workout_detail_url(workout, workout_type),
		})

	# ── Categories (goal bo'yicha) + per-category popular ──
	by_goal = {}
	for program in explore_programs:
		by_goal.setdefault(program.goal, []).append(program)

	categories = []
	for goal_value, emoji, tagline in GOAL_CARDS:
		programs = by_goal.get(goal_value)
		if not programs:
			continue
		popular = max(programs, key=lambda p: p.view_count)
		popular_id = popular.id if popular.view_count > 0 else None
		# Grid ("list") rejimida ham "top" belgisini ko'rsatish uchun
		# har bir programmaga is_popular biriktiramiz.
		for p in programs:
			p.is_popular = popular_id is not None and p.id == popular_id
		categories.append({
			"goal": goal_value,
			"label": dict(Program.Goal.choices)[goal_value],
			"emoji": emoji,
			"tagline": tagline,
			"programs": programs,
			"popular_id": popular_id,
		})

	# Har bir programmaga detail URL va "tavsiya" belgisini biriktiramiz
	# (grid include va kategoriya kartochkalari shu obyektlardan foydalanadi).
	rec_id = recommended_card["program"].id if recommended_card else None
	for program in explore_programs:
		program.detail_url = _program_detail_url(program, workout_type)
		program.is_recommended = program.id == rec_id

	# Grid ("plitka") rejimi uchun: recommendedni birinchi qilib joylaymiz.
	grid_programs = list(explore_programs)
	if rec_id is not None:
		grid_programs.sort(key=lambda p: (p.id != rec_id, p.id))

	return {
		"active_workout_type": workout_type,
		"is_home_mode": workout_type == WorkoutType.HOME,
		"active_level": active_level,
		"level_choices": Program.Level.choices,
		"recommended_card": recommended_card,
		"one_time_cards": one_time_cards,
		"categories": categories,
		"explore_programs": grid_programs,
		# Grid rejimida "FOR YOU" badge ko'rsatish uchun:
		"recommended_program": recommended_card["program"] if recommended_card else None,
	}


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
class ProgramListView(TemplateView):
	forced_workout_type = None
	template_name = 'workouts/program_list.html'

	def active_workout_type(self):
		return get_session_workout_type(self.request, self.forced_workout_type)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update(build_programs_page_context(self.request, self.active_workout_type()))
		return context


# --- 2. Programma ichidagi Planlar ---
class ProgramDetailView(PremiumRequiredMixin, DetailView):
	forced_workout_type = None
	model = Program
	template_name = 'workouts/edition_list.html'
	context_object_name = 'program'
	
	def get_queryset(self):
		workout_type = get_session_workout_type(self.request, self.forced_workout_type)
		return Program.objects.filter(is_active=True, workout_type=workout_type).prefetch_related('plans')

	def get_object(self, queryset=None):
		program = super().get_object(queryset)
		# "POPULAR" badge uchun ochilishlar sonini atomik oshiramiz.
		Program.objects.filter(pk=program.pk).update(view_count=F('view_count') + 1)
		return program

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		active_type = self.object.workout_type
		context['plans'] = self.object.plans.filter(program__workout_type=active_type).order_by('order')
		context['active_workout_type'] = active_type
		context['is_home_mode'] = active_type == WorkoutType.HOME
		context['use_gym_urls'] = self.forced_workout_type == WorkoutType.GYM
		return context


class PlanWeeksView(PremiumRequiredMixin, DetailView):
	forced_workout_type = None
	model = Plan
	template_name = 'workouts/plan_weeks.html'
	context_object_name = 'plan'
	
	def get_queryset(self):
		w_type = get_session_workout_type(self.request, self.forced_workout_type)
		return Plan.objects.filter(program__workout_type=w_type)
	
	def premium_not_found_message(self, kwargs):
		w_type = get_session_workout_type(self.request, self.forced_workout_type)
		return f"IDsi {kwargs.get('pk')} bo'lgan plan tanlangan tur ({w_type}) uchun topilmadi."
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		active_type = self.object.program.workout_type
		context['weeks'] = self.object.weeks.all().order_by('week_number')
		context['active_workout_type'] = active_type
		context['is_home_mode'] = active_type == WorkoutType.HOME
		return context


class WeekDetailView(DetailView):
	forced_workout_type = None
	
	model = Week
	template_name = 'workouts/week_days.html'
	context_object_name = 'week'
	
	def get_queryset(self):
		w_type = get_session_workout_type(self.request, self.forced_workout_type)
		return Week.objects.filter(plan__program__workout_type=w_type)
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		active_type = self.object.plan.program.workout_type
		workouts = self.object.workouts.all().order_by('day_number').annotate(
			exercise_count=Count('workout_exercises')
		)
		
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


class WorkoutDetailView(DetailView):
	forced_workout_type = None
	
	model = Workout
	template_name = 'workouts/workout_detail.html'
	context_object_name = 'workout'
	
	def get_queryset(self):
		workout_type = get_session_workout_type(self.request, self.forced_workout_type)
		return Workout.objects.filter(week__plan__program__workout_type=workout_type).select_related(
			'week__plan__program')
	
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
		
		# Mushak guruhi (nom endi Exercise.display_name property orqali keladi)
		for item in workout_exercises:
			ex = item.exercise
			ex.display_body_part = ex.get_primary_body_part_display()
		
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
				"exercise_type": getattr(ex, 'exercise_type', '') or '',
				"duration_seconds": int(wex.duration_seconds) if getattr(wex, 'duration_seconds', None) is not None else None,
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
