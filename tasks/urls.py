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
router.register(r'exercises', ExerciseViewSet, basename='exercise')
router.register(r'workoutplans', WorkoutPlanViewSet, basename='workoutplan')
router.register(r'taskitems', TaskItemViewSet, basename='taskitem')
router.register(r'workoutlogs', WorkoutLogViewSet, basename='workoutlog')

# ✅ 테스트 호환용 alias: /api/tasks/ → TaskItemViewSet에 매핑
router.register(r'tasks',        TaskItemViewSet,    basename='tasks')

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", dashboard, name="tasks_dashboard"),
    path("workouts/", workouts, name="tasks_workouts"),
    path("meals/", meals, name="tasks_meals"),
]
