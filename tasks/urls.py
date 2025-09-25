from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    ExerciseViewSet,
    TaskItemViewSet,
    WorkoutPlanViewSet,
    dashboard,
    meals,
    workouts,
)

router = DefaultRouter()
router.register(r'exercises', ExerciseViewSet, basename='exercise')
router.register(r'workoutplans', WorkoutPlanViewSet, basename='workoutplan')
router.register(r'taskitems', TaskItemViewSet, basename='taskitem')

# WorkoutLogViewSet이 있을 때만 등록 (개발 환경 차이 대비)
try:
    from .views import WorkoutLogViewSet  # noqa
    router.register(r'workoutlogs', WorkoutLogViewSet, basename='workoutlog')
except Exception:
    pass

# ✅ 테스트 호환용 alias: reverse("tasks-list") 등
router.register(r'tasks', TaskItemViewSet, basename='tasks')

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", dashboard, name="tasks_dashboard"),
    path("workouts/", workouts, name="tasks_workouts"),
    path("meals/", meals, name="tasks_meals"),
]
