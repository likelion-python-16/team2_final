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

# -------------------------------
# 분리: API 라우트 / 페이지 라우트
# -------------------------------

# (선택) 페이지 네임스페이스 사용 시 필요
app_name = "tasks"

# API 라우트 모음 (/api/에 마운트 예정)
api_urlpatterns = [
    path("", include(router.urls)),
]

# 페이지 라우트 모음 (/tasks/에 마운트 예정)
# name을 네임스페이스-friendly하게 정리 (dashboard/workouts/meals)
page_urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("workouts/", workouts, name="workouts"),
    path("meals/", meals, name="meals"),
]

# 기존 호환을 위해 한 파일 내에서도 동작하도록 유지
urlpatterns = api_urlpatterns + page_urlpatterns