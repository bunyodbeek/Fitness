from apps.models import Exercise
from apps.models.favorites import FavoriteCollection, Favorite, UserCustomProgram
from apps.services.workout_calculator import WorkoutCalculatorService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import ListView
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


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
        context['total_count'] = Favorite.objects.filter(user=user_profile).count()
        context['favorite_collections'] = FavoriteCollection.objects.filter(user=user_profile).order_by('-created_at')
        context['collections_count'] = context['favorite_collections'].count()
        context['custom_programs'] = UserCustomProgram.objects.filter(
            user=user_profile,
            is_active=True
        ).select_related('collection')
        favorites = Favorite.objects.filter(user=user_profile, collection__isnull=True).select_related('exercise')
        context['all_exercises'] = [fav.exercise for fav in favorites]
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        qs = qs.filter(user=user.profile, collection__isnull=True).select_related('exercise')
        return qs


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
            'body_part': exercise.body_part,
            'difficulty': exercise.difficulty,
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
                "body_part": exercise.body_part,
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
        collection_exercises = Exercise.objects.filter(favorites__collection=collection, favorites__user=user_profile).distinct()

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
        day_one = schedule[0]["days"][0] if schedule and schedule[0]["days"] else {"sets": 3, "reps": 10, "exercises": []}

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
                "total_exercises": len(exercises_data),
                "initial_exercise_index": 0,
                "initial_set": 1,
                "initial_completed": 0,
            },
        )
