from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExerciseViewSet, WorkoutPlanViewSet, TaskItemViewSet, WorkoutLogViewSet

router = DefaultRouter()
router.register(r'api/exercises', ExerciseViewSet, basename='exercise')
router.register(r'api/workoutplans', WorkoutPlanViewSet, basename='workoutplan')
router.register(r'api/taskitems', TaskItemViewSet, basename='taskitem')
router.register(r'api/workoutlogs', WorkoutLogViewSet, basename='workoutlog')

urlpatterns = [path('', include(router.urls))]