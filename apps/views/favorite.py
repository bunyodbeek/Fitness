import json
import math

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import ListView, DetailView
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.models import Exercise, Plan, Program, Week, Workout, WorkoutExercise
from apps.models.favorites import FavoriteCollection, Favorite, UserCustomProgram, CustomProgramProgress
from apps.models.workouts import ProgressionSetting
from apps.services.programs import ProgramGenerationService
from apps.services.workout_calculator import WorkoutCalculatorService
from apps.workouts.recommendation import get_recommended_program


class FavoriteCollectionMixin:
	def _update_favorites(self, user, collection, exercise_ids):
		for ex_id in set(exercise_ids):
			exercise = get_object_or_404(Exercise, id=ex_id)
			favorite, created = Favorite.objects.get_or_create(
				user=user,
				exercise=exercise,
				defaults={"collection": collection}
			)
			if not created and favorite.collection is None:
				favorite.collection = collection
				favorite.save(update_fields=["collection"])


class FavoritesListView(LoginRequiredMixin, ListView):
	model = Favorite
	template_name = 'exercises/favorites_list.html'
	context_object_name = 'favorites'
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		user_profile = self.request.user.profile
		context['recommended_program'] = get_recommended_program(user_profile)
		context['total_count'] = Favorite.objects.filter(user=user_profile).count()
		context['favorite_collections'] = FavoriteCollection.objects.filter(user=user_profile).order_by('-created_at')
		context['collections_count'] = context['favorite_collections'].count()
		context['custom_programs'] = Program.objects.filter(
			type=Program.ProgramType.CUSTOM,
			created_by=user_profile,
			is_active=True,
		).prefetch_related('plans')
		
		# Favorite exercise ID'lari (⭐ state uchun)
		favorite_ids = set(
			Favorite.objects.filter(user=user_profile)
			.values_list('exercise_id', flat=True)
		)
		context['favorite_exercise_ids'] = favorite_ids
		
		# Barcha gym exercises (picker uchun)
		context['all_exercises'] = Exercise.objects.filter(
			workout_type='gym'
		).order_by('name')
		
		return context
	
	def get_queryset(self):
		return Favorite.objects.filter(
			user=self.request.user.profile,
		).select_related('exercise')

class ToggleFavoriteView(APIView):
	permission_classes = [IsAuthenticated]
	
	def post(self, request, exercise_id):
		exercise = get_object_or_404(Exercise, pk=exercise_id)
		user_profile = request.user.profile
		
		favorite, created = Favorite.objects.get_or_create(
			user=user_profile,
			exercise=exercise
		)
		
		if not created:
			favorite.delete()
			return Response({'success': True, 'status': 'removed'})
		
		thumbnail = exercise.thumbnail.url if getattr(exercise, "thumbnail", None) else None
		return Response({
			'success': True,
			'status': 'added',
			'favorite_id': favorite.id,
			'exercise_id': exercise.id,
			'exercise_name': exercise.name,
			'thumbnail': thumbnail,
			'body_part': str(exercise.primary_body_part) if exercise.primary_body_part else "",
			# 'difficulty': exercise.difficulty,
		})


class FavoriteToggleAPIView(GenericAPIView):
	permission_classes = [IsAuthenticated]
	
	def post(self, request, collection_id):
		exercise_id = request.data.get("exercise_id")
		if not exercise_id:
			return Response(
				{"message": "Mashq ID si yuborilmadi."},
				status=status.HTTP_400_BAD_REQUEST
			)
		
		user = request.user.profile
		collection = get_object_or_404(FavoriteCollection, id=collection_id, user=user)
		exercise = get_object_or_404(Exercise, id=exercise_id)
		
		qs = Favorite.objects.filter(user=user, collection=collection, exercise=exercise)
		
		if qs.exists():
			qs.delete()
			action = "removed"
			message = f'"{exercise.name}" mashqi "{collection.name}" toʻplamidan olib tashlandi.'
		else:
			obj, created = Favorite.objects.get_or_create(user=user, exercise=exercise)
			obj.collection = collection
			obj.save(update_fields=['collection'])
			
			action = "added"
			message = f'"{exercise.name}" mashqi "{collection.name}" toʻplamiga qoʻshildi.'
		
		return Response({
			"success": True,
			"action": action,
			"exercise_id": exercise.id,
			"collection_id": collection.id,
			"items_count": collection.exercise_count,
			"message": message,
		})


class UserCollectionsAPIView(APIView):
	permission_classes = [IsAuthenticated]
	
	def get(self, request):
		collections = FavoriteCollection.objects.filter(user=request.user.profile)
		data = [
			{
				"id": c.id,
				"name": c.name,
				"exercise_count": c.exercise_count,
			}
			for c in collections
		]
		return Response(data)


class CreateCollectionView(View):
	def post(self, request):
		name = request.POST.get("name")
		exercise_id = request.POST.get("exercise_id")
		exercise_ids = request.POST.getlist("exercise_ids[]")
		
		if not name:
			return JsonResponse(
				{"success": False, "error": "Collection nomi yuborilmadi"},
				status=status.HTTP_400_BAD_REQUEST
			)
		
		user = request.user.profile
		
		collection = FavoriteCollection.objects.create(
			user=user,
			name=name
		)
		
		all_exercise_ids = []
		
		if exercise_id:
			all_exercise_ids.append(int(exercise_id))
		
		for ex_id in exercise_ids:
			all_exercise_ids.append(int(ex_id))
		
		for ex_id in set(all_exercise_ids):
			exercise = get_object_or_404(Exercise, id=ex_id)
			
			favorite, created = Favorite.objects.get_or_create(
				user=user,
				exercise=exercise,
				defaults={"collection": collection}
			)
			
			if not created and favorite.collection is None:
				favorite.collection = collection
				favorite.save(update_fields=["collection"])
		
		return JsonResponse({
			"success": True,
			"collection_id": collection.id,
			"name": collection.name
		}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name='dispatch')
class CollectionUpdateView(View):
	def post(self, request, collection_id):
		user = request.user.profile
		collection = get_object_or_404(FavoriteCollection, id=collection_id, user=user)
		
		name = request.POST.get("name")
		exercise_ids = request.POST.getlist("exercise_ids[]")
		
		if name is not None or exercise_ids:
			if not name or not name.strip():
				return JsonResponse({
					"success": False,
					"error": "Collection nomi kiriting"
				}, status=status.HTTP_400_BAD_REQUEST)
			
			collection.name = name.strip()
			collection.save(update_fields=["name"])
			
			for ex_id in exercise_ids:
				if not ex_id.isdigit():
					continue
				exercise = get_object_or_404(Exercise, id=int(ex_id))
				favorite, created = Favorite.objects.get_or_create(
					user=user,
					exercise=exercise,
					defaults={"collection": collection}
				)
				if not created and favorite.collection != collection:
					favorite.collection = collection
					favorite.save(update_fields=["collection"])
			
			return JsonResponse({
				"success": True,
				"collection_id": collection.id,
				"name": collection.name,
				"exercise_ids": exercise_ids
			})
		
		else:
			exercise_ids = list(
				Favorite.objects.filter(collection=collection)
				.values_list('exercise_id', flat=True)
			)
			return JsonResponse({
				"success": True,
				"name": collection.name,
				"exercise_ids": exercise_ids
			})


class CollectionDeleteView(View):
	
	def post(self, request, collection_id):
		collection = get_object_or_404(FavoriteCollection, id=collection_id, user=request.user.profile)
		Favorite.objects.filter(user=request.user.profile, collection=collection).update(collection=None)
		collection.delete()
		
		return JsonResponse({
			"success": True,
			"message": "Collection o'chirildi"
		}, status=status.HTTP_200_OK)


class ExerciseRemoveFromCollection(View):
	
	def post(self, request, collection_id, favorited_id):
		user = request.user.profile
		collection = get_object_or_404(FavoriteCollection, id=collection_id, user=user)
		favorite = get_object_or_404(
			Favorite,
			user=user,
			exercise_id=favorited_id,
			collection=collection
		)
		exercise = favorite.exercise
		thumbnail = exercise.thumbnail.url if getattr(exercise, "thumbnail", None) else None
		
		favorite.collection = None
		favorite.save(update_fields=["collection"])
		
		return JsonResponse(
			{
				"success": True,
				"message": "Exercise collectiondan olib tashlandi",
				"favorite_id": favorite.id,
				"exercise_id": exercise.id,
				"exercise_name": exercise.name,
				"thumbnail": thumbnail,
				"body_part": str(exercise.primary_body_part) if exercise.primary_body_part else "",
				"difficulty": exercise.difficulty,
			},
			status=status.HTTP_200_OK
		)


class UserCustomProgramListView(LoginRequiredMixin, View):
	def get(self, request):
		user_profile = request.user.profile
		goal = (request.GET.get("goal") or "").strip().lower()
		collection_id = request.GET.get("collection_id")
		
		programs = UserCustomProgram.objects.filter(user=user_profile, is_active=True).select_related("collection")
		if goal in {"mg", "ft", "rc"}:
			programs = programs.filter(goal=goal)
		if collection_id and collection_id.isdigit():
			programs = programs.filter(collection_id=int(collection_id))
		
		return JsonResponse(
			{
				"success": True,
				"programs": [
					{
						"id": p.id,
						"name": p.name,
						"goal": p.goal,
						"goal_display": p.get_goal_display(),
						"total_exercises": p.total_exercises,
						"weeks": p.weeks,
						"collection_id": p.collection_id,
						"collection_name": p.collection.name if p.collection_id else "",
					}
					for p in programs
				],
			}
		)


class CreateCustomProgramView(LoginRequiredMixin, View):
	def post(self, request):
		user_profile = request.user.profile
		name = (request.POST.get("name") or "").strip()
		goal = (request.POST.get("goal") or "").strip().lower()
		collection_id = request.POST.get("collection_id")
		
		if not name:
			return JsonResponse({"success": False, "error": "Program name is required"}, status=400)
		if goal not in {"mg", "ft", "rc"}:
			return JsonResponse({"success": False, "error": "Invalid goal"}, status=400)
		if not collection_id or not str(collection_id).isdigit():
			return JsonResponse({"success": False, "error": "Collection is required"}, status=400)
		
		collection = get_object_or_404(FavoriteCollection, id=int(collection_id), user=user_profile)
		collection_exercises = Exercise.objects.filter(favorites__collection=collection,
		                                               favorites__user=user_profile).distinct()
		
		if not collection_exercises.exists():
			return JsonResponse({"success": False, "error": "Collection has no exercises"}, status=400)
		
		program = UserCustomProgram.objects.create(
			user=user_profile,
			name=name,
			goal=goal,
			collection=collection,
			weeks=6,
			is_active=True,
		)
		
		schedule = WorkoutCalculatorService.generate_program(collection_exercises, weeks=program.weeks, days_per_week=3)
		
		return JsonResponse(
			{
				"success": True,
				"program": {
					"id": program.id,
					"name": program.name,
					"goal": program.goal,
					"goal_display": program.get_goal_display(),
					"total_exercises": program.total_exercises,
					"weeks": program.weeks,
					"collection_id": program.collection_id,
					"collection_name": collection.name,
				},
				"schedule": schedule,
			},
			status=201,
		)


class CustomProgramStartView(LoginRequiredMixin, View):
	def get(self, request, pk):
		program = get_object_or_404(UserCustomProgram, pk=pk, user=request.user.profile, is_active=True)
		if not program.collection_id:
			return render(request, "error_page.html", {"error_message": "Collection topilmadi."})
		
		exercises_qs = Exercise.objects.filter(
			favorites__collection=program.collection,
			favorites__user=request.user.profile,
		).distinct()
		if not exercises_qs.exists():
			return render(request, "error_page.html", {"error_message": "Mashqlar topilmadi."})
		
		schedule = WorkoutCalculatorService.generate_program(exercises_qs, weeks=program.weeks, days_per_week=3)
		day_one = schedule[0]["days"][0] if schedule and schedule[0]["days"] else {"sets": 3, "reps": 10,
		                                                                           "exercises": []}
		
		lang_code = getattr(request, "LANGUAGE_CODE", "en")
		exercises_data = []
		for item in day_one["exercises"]:
			ex = exercises_qs.filter(id=item["exercise_id"]).first()
			if not ex:
				continue
			exercises_data.append(
				{
					"exercise_id": ex.id,
					"name": getattr(ex, f"name_{lang_code}", ex.name) or ex.name,
					"sets": day_one["sets"],
					"reps": day_one["reps"],
					"duration_minutes": 0,
					"rest_seconds": 60,
					"calories_per_minute": 5.0,
					"type": "strength",
					"image": ex.thumbnail.url if ex.thumbnail else None,
					"video": ex.video.url if ex.video else None,
				}
			)
		
		return render(
			request,
			"workouts/active_workout.html",
			{
				"workout": program,
				"exercises": exercises_data,
				"rest_seconds": 60,
				"calories_per_minute": 5.0,
				"total_exercises": len(exercises_data),
				"initial_exercise_index": 0,
				"initial_set": 1,
				"initial_completed": 0,
				"workout_complete_url": reverse("custom_program_complete", args=[program.pk]),
				"workout_start_url": reverse("custom_program_start", args=[program.pk]),
			},
		)


class CustomProgramCompleteView(LoginRequiredMixin, View):
	template_name = "workouts/workout_complete.html"
	
	@staticmethod
	def _safe_float(value, default=0.0):
		try:
			parsed = float(value)
		except (TypeError, ValueError):
			return default
		return parsed if math.isfinite(parsed) else default
	
	@staticmethod
	def _safe_int(value, default=0):
		try:
			parsed = int(float(value))
		except (TypeError, ValueError):
			return default
		return parsed if math.isfinite(parsed) else default
	
	def get(self, request, pk):
		program = get_object_or_404(UserCustomProgram, pk=pk, user=request.user.profile, is_active=True)
		return render(
			request,
			self.template_name,
			{
				"workout": program,
				"workout_summary": {
					"total_calories": 0,
					"duration_seconds": 0,
					"exercises_completed": 0,
				},
			},
		)
	
	def post(self, request, pk):
		program = get_object_or_404(UserCustomProgram, pk=pk, user=request.user.profile, is_active=True)
		
		total_calories = self._safe_float(request.POST.get("total_calories", 0))
		total_duration = self._safe_int(request.POST.get("total_duration", 0))
		exercises_completed = self._safe_int(request.POST.get("exercises_completed", 0))
		
		CustomProgramProgress.objects.create(
			user=request.user.profile,
			program=program,
			total_calories=total_calories,
			total_duration_seconds=total_duration,
			exercises_completed=exercises_completed,
		)
		
		return render(
			request,
			self.template_name,
			{
				"workout": program,
				"workout_summary": {
					"total_calories": total_calories,
					"duration_seconds": total_duration,
					"exercises_completed": exercises_completed,
					"total_reps": 0,
					"total_weight": 0,
				},
			},
		)



class CustomProgramCreateView(LoginRequiredMixin, View):
	template_name = "exercises/custom_program_create.html"
	
	def get(self, request):
		exercises = Exercise.objects.filter(workout_type='gym').order_by('name')
		return render(request, self.template_name, {'exercises': exercises})
	
	def post(self, request):
		try:
			data = json.loads(request.body)
		except Exception:
			return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
		
		name = (data.get("name") or "").strip()
		goal = (data.get("goal") or "").strip()
		days = data.get("days", [])
		
		if not name:
			return JsonResponse({"success": False, "error": "Name required"}, status=400)
		if goal not in dict(Program.Goal.choices):
			return JsonResponse({"success": False, "error": "Invalid goal"}, status=400)
		if not days:
			return JsonResponse({"success": False, "error": "At least 1 day required"}, status=400)
		
		user_profile = request.user.profile
		
		with transaction.atomic():
			program = Program.objects.create(
				name=name,
				goal=goal,
				type=Program.ProgramType.CUSTOM,
				created_by=user_profile,
				workout_type='gym',
				is_active=True,
				is_template=False,
			)

			progression, _ = ProgressionSetting.objects.get_or_create(
				key='default',
				defaults={
					'set_w2': 1, 'set_w3': 1, 'set_w4': 0, 'set_w5': 0, 'set_w6': 0,
					'rep_w2': 0, 'rep_w3': -1, 'rep_w4': 0, 'rep_w5': -1, 'rep_w6': -2,
				}
			)
			plan = Plan.objects.create(
				program=program,
				name=name,
				order=1,
				weeks_count=6,
				progression_config=progression,
			)

			ProgramGenerationService.ensure_plan_weeks(plan)
			week_one = Week.objects.get(plan=plan, week_number=1)

			for day_data in days:
				workout = Workout.objects.create(
					week=week_one,
					day_number=day_data["day_number"],
					title=day_data.get("title", f"Day {day_data['day_number']}"),
					apply_to_all_weeks=True,
				)
				for ex_data in day_data.get("exercises", []):
					exercise = Exercise.objects.filter(id=ex_data["exercise_id"]).first()
					if not exercise:
						continue
					WorkoutExercise.objects.create(
						workout=workout,
						exercise=exercise,
						sets=ex_data.get("sets", 3),
						reps=ex_data.get("reps", 10),
						recommended_weight=ex_data.get("weight", 0),
						order=ex_data.get("order", 1),
					)

			# Barcha kunlarning (Day1, Day2, ...) mashqlarini hafta 2-6 ga progression bilan ko'chirish
			ProgramGenerationService.regenerate_all_from_week_one(plan)
		
		return JsonResponse({
			"success": True,
			"program_id": program.id,
			"redirect_url": f"/{request.LANGUAGE_CODE}/favorites/custom-program/{program.id}/"
		}, status=201)


class CustomProgramDeleteView(LoginRequiredMixin, View):
	def post(self, request, pk):
		from apps.models import Program
		program = get_object_or_404(
			Program,
			pk=pk,
			type=Program.ProgramType.CUSTOM,
			created_by=request.user.profile,
		)
		program.delete()
		return JsonResponse({"success": True})


class CustomProgramDetailView(LoginRequiredMixin, DetailView):
	model = Program
	template_name = 'workouts/edition_list.html'
	context_object_name = 'program'
	
	def get_queryset(self):
		return Program.objects.filter(
			type=Program.ProgramType.CUSTOM,
			created_by=self.request.user.profile,
		)
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['plans'] = self.object.plans.all().order_by('order')
		context['is_home_mode'] = False
		
		context['is_custom'] = True
		return context


class CustomProgramEditView(LoginRequiredMixin, View):
	template_name = "exercises/custom_program_create.html"
	
	def get(self, request, pk):
		program = get_object_or_404(
			Program, pk=pk,
			type=Program.ProgramType.CUSTOM,
			created_by=request.user.profile,
		)
		exercises = Exercise.objects.filter(workout_type='gym').order_by('name')
		
		# Week 1 dan mavjud data olish
		plan = program.plans.first()
		existing_days = []
		if plan:
			week_one = plan.weeks.filter(week_number=1).first()
			if week_one:
				for workout in week_one.workouts.order_by('day_number'):
					day_exercises = []
					for we in workout.workout_exercises.select_related('exercise').order_by('order'):
						day_exercises.append({
							'id': we.exercise.id,
							'name': we.exercise.name,
							'muscle': str(we.exercise.primary_body_part),
							'thumb': we.exercise.thumbnail.url if we.exercise.thumbnail else '',
							'sets': we.sets,
							'reps': we.reps,
							'weight': we.recommended_weight or 0,
						})
					existing_days.append({
						'day_number': workout.day_number,
						'exercises': day_exercises,
					})
		
		import json
		return render(request, self.template_name, {
			'exercises': exercises,
			'program': program,
			'is_edit': True,
			'existing_days_json': json.dumps(existing_days),
			'existing_name': program.name,
			'existing_goal': program.goal,
			'existing_days_count': len(existing_days),
		})


class CustomProgramEditSaveView(LoginRequiredMixin, View):
	def post(self, request, pk):
		import json
		from django.db import transaction
		
		program = get_object_or_404(
			Program, pk=pk,
			type=Program.ProgramType.CUSTOM,
			created_by=request.user.profile,
		)
		
		try:
			data = json.loads(request.body)
		except Exception:
			return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
		
		name = (data.get("name") or "").strip()
		goal = (data.get("goal") or "").strip()
		days = data.get("days", [])
		
		if not name:
			return JsonResponse({"success": False, "error": "Name required"}, status=400)
		
		with transaction.atomic():
			program.name = name
			program.goal = goal
			program.save(update_fields=['name', 'goal'])

			plan = program.plans.first()
			if plan:
				week_one = plan.weeks.filter(week_number=1).first()
				if week_one:
					week_one.workouts.all().delete()

				plan.weeks.exclude(week_number=1).delete()
				ProgramGenerationService.ensure_plan_weeks(plan)
				week_one = plan.weeks.get(week_number=1)

				for day_data in days:
					workout = Workout.objects.create(
						week=week_one,
						day_number=day_data["day_number"],
						title=f"Day {day_data['day_number']}",
						apply_to_all_weeks=True,
					)
					for ex_data in day_data.get("exercises", []):
						exercise = Exercise.objects.filter(id=ex_data["exercise_id"]).first()
						if not exercise:
							continue
						WorkoutExercise.objects.create(
							workout=workout,
							exercise=exercise,
							sets=ex_data.get("sets", 3),
							reps=ex_data.get("reps", 10),
							recommended_weight=ex_data.get("weight", 0),
							order=ex_data.get("order", 1),
						)

				# Barcha kunlarning mashqlarini hafta 2-6 ga progression bilan ko'chirish
				ProgramGenerationService.regenerate_all_from_week_one(plan)
		
		return JsonResponse({
			"success": True,
			"redirect_url": f"/{request.LANGUAGE_CODE}/favorites/custom-program/{program.id}/"
		})