# team2_final/urls.py
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, JsonResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenVerifyView
)

from . import views
from .views import landing

# 분리 include용
from users import urls as users_urls
from users import views as users_views          # setup/profile은 users.views에서 가져옴
from tasks import urls as tasks_urls

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

def root_healthcheck(_request):
    return JsonResponse({"status": "ok", "message": "Workout & feedback API root"})

def api_docs(_request):
    doc_path = Path(settings.BASE_DIR) / "openapi.json"
    if not doc_path.exists():
        return JsonResponse({"detail": "openapi.json not found"}, status=404)
    return FileResponse(doc_path.open("rb"), content_type="application/json")

urlpatterns = [
    # ---------- 기본 페이지 ----------
    path("", landing, name="landing"),
    path("example/", views.example_view, name="example"),
    path("docs", api_docs, name="api_docs"),
    path("admin/", admin.site.urls),

    # Django 기본 로그인/로그아웃/비번재설정 뷰 (registration/* 템플릿)
    path("accounts/", include("django.contrib.auth.urls")),

    # ---------- 유저 관련 개별 페이지 ----------
    # /signup 은 로그인으로 리다이렉트(머지 회귀 방지)
    path("signup/", RedirectView.as_view(pattern_name="login", permanent=False)),
    # setup/profile 은 users 앱의 뷰로 연결
    path("setup/", users_views.setup_view, name="user_setup"),
    path("profile/", users_views.profile_view, name="user_profile"),

    # ---------- JWT ----------
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # ---------- API 라우트 (전부 /api/ 아래) ----------
    path("api/", include((users_urls.api_urlpatterns, "users_api"), namespace="users_api")),
    path("api/", include("goals.urls")),
    path("api/", include((tasks_urls.api_urlpatterns, "tasks_api"), namespace="tasks_api")),
    path("api/", include("intakes.urls")),
    path("api/", include("feedbacks.urls")),

    # ---------- 페이지 라우트 ----------
    # users: OAuth 등 페이지 경로 (네임스페이스 users)
    path("users/", include((users_urls.page_urlpatterns, "users"), namespace="users")),
    # tasks: 대시보드/워크아웃/밀 페이지 (네임스페이스 tasks)
    path("tasks/", include((tasks_urls.page_urlpatterns, "tasks"), namespace="tasks")),

    # ---------- 레거시/오타 경로 흡수 ----------
    # /task/... (단수) → /tasks/... (복수)
    re_path(r"^task/(?P<rest>.*)$", RedirectView.as_view(url="/tasks/%(rest)s", permanent=False)),
    # 과거 특정 오타(원하면 제거 가능)
    path("task/dashboard/", RedirectView.as_view(url="/tasks/dashboard/", permanent=False)),
    
    # /signup/은 항상 로그인으로 (이름 부여: user_signup)
    path(
        "signup/",
        RedirectView.as_view(pattern_name="login", permanent=False),
        name="user_signup",),
    
    # OpenAPI 스키마(JSON)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),

    # Swagger UI
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # Redoc UI
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    ]
