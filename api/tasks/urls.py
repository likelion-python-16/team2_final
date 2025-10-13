# tasks/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'exercises', views.ExerciseViewSet, basename='exercise')
router.register(r'workoutplans', views.WorkoutPlanViewSet, basename='workoutplan')
router.register(r'taskitems', views.TaskItemViewSet, basename='taskitem')

# WorkoutLogViewSet 이 있을 때만 등록
try:
    router.register(r'workoutlogs', views.WorkoutLogViewSet, basename='workoutlog')
except Exception:
    pass

# 테스트/호환용 별칭
router.register(r'tasks', views.TaskItemViewSet, basename='tasks')

# 페이지 네임스페이스
app_name = "tasks"

# ✅ API 패턴 (여기에 'api/' 접두사를 넣지 마세요!)
api_urlpatterns = [
    path("", include(router.urls)),  # /exercises, /workoutplans, /taskitems, ...
    path("fixtures/exercises/", views.fixtures_exercises, name="fixtures-exercises"),
]

# ✅ 페이지 패턴
page_urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("workouts/", views.workouts, name="workouts"),
    path("meals/", views.meals, name="meals"),
]

# ✅ 기본 export: 페이지 라우트만 노출
# (API는 루트 urls.py에서 `api/`에 마운트하도록 분리)
urlpatterns = page_urlpatterns
