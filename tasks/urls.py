from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    ExerciseViewSet,
    TaskItemViewSet,
    WorkoutLogViewSet,
    WorkoutPlanViewSet,
    dashboard,
    meals,
    workouts,
)

router = DefaultRouter()
router.register(r'api/exercises', ExerciseViewSet, basename='exercise')
router.register(r'api/workoutplans', WorkoutPlanViewSet, basename='workoutplan')
router.register(r'api/taskitems', TaskItemViewSet, basename='taskitem')
router.register(r'api/workoutlogs', WorkoutLogViewSet, basename='workoutlog')

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", dashboard, name="tasks_dashboard"),
    path("workouts/", workouts, name="tasks_workouts"),
    path("meals/", meals, name="tasks_meals"),
]
