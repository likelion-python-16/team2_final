# tasks/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from . import api_views  # Today Summary / Recommendations / Insights 최소 API 뷰

# -------------------------------------------------------------------
# DRF Router (뷰셋들)
# -------------------------------------------------------------------
router = DefaultRouter()
router.register(r"exercises", views.ExerciseViewSet, basename="exercise")
router.register(r"workoutplans", views.WorkoutPlanViewSet, basename="workoutplan")
router.register(r"taskitems", views.TaskItemViewSet, basename="taskitem")

# 선택적: WorkoutLogViewSet 이 있을 때만 등록 (개발 환경 차이 대비)
try:
    # views 모듈에 정의되어 있으면 등록
    _wlv = getattr(views, "WorkoutLogViewSet", None)
    if _wlv:
        router.register(r"workoutlogs", _wlv, basename="workoutlog")
except Exception:
    pass

# 테스트/호환용 별칭 (reverse("tasks-list") 등)
router.register(r"tasks", views.TaskItemViewSet, basename="tasks")

# -------------------------------------------------------------------
# 페이지 라우트 (템플릿 렌더)
# -------------------------------------------------------------------
app_name = "tasks"

page_urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("workouts/", views.workouts, name="workouts"),
    path("meals/", views.meals, name="meals"),
]

# -------------------------------------------------------------------
# API 라우트 (여기엔 'api/' 접두사를 넣지 않는다)
# 루트 urls.py에서 `path("api/", include(...))`로 마운트
# -------------------------------------------------------------------
api_urlpatterns = [
    path("", include(router.urls)),  # /exercises, /workoutplans, /taskitems, /workoutlogs?, /tasks(alias)
    path("fixtures/exercises/", views.fixtures_exercises, name="fixtures-exercises"),

    # ✅ Today 패널용 최소 API
    # GET /api/workoutplans/summary/?date=YYYY-MM-DD[&workout_plan=<id>]
    path("workoutplans/summary/", api_views.WorkoutSummaryView.as_view(), name="workout-summary"),

    # GET /api/recommendations/?date=YYYY-MM-DD[&workout_plan=<id>]
    path("recommendations/", api_views.RecommendationsView.as_view(), name="recommendations"),

    # GET /api/insights/today/?date=YYYY-MM-DD[&workout_plan=<id>]
    path("insights/today/", api_views.TodayInsightsView.as_view(), name="today-insights"),
]

# -------------------------------------------------------------------
# 기본 export: 페이지 라우트만 노출
# (API는 루트 urls.py에서 api_urlpatterns 를 별도 include)
# -------------------------------------------------------------------
urlpatterns = page_urlpatterns
