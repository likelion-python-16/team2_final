# team2_final/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView

from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
)

from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenVerifyView
)

from .today_views import today_summary
from .healthz import healthz, simple_token
from . import views
from .views import landing

# 분리 include용
from users import urls as users_urls
from users import views as users_views
from tasks import urls as tasks_urls

# Public(AllowAny) 토큰 뷰
from .auth_views import (
    PublicTokenObtainPairView, PublicTokenRefreshView, PublicTokenVerifyView
)

urlpatterns = [
    # ---------- 헬스체크 / 오늘 요약 ----------
    path("healthz", healthz, name="healthz"),
    path("auth/simple-token", simple_token, name="simple_token"),
    path("api/today/", today_summary, name="today-summary"),

    # ---------- 기본 페이지 ----------
    path("", landing, name="landing"),
    path("example/", views.example_view, name="example"),

    # ---------- Admin / 계정 ----------
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),

    # ---------- 유저 개별 페이지 ----------
    path("setup/", users_views.setup_view, name="user_setup"),
    path("profile/", users_views.profile_view, name="user_profile"),
    path("signup/", RedirectView.as_view(pattern_name="login", permanent=False), name="user_signup"),

    # ---------- JWT (기존 경로) ----------
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # ---------- Public JWT (AllowAny 신규 경로) ----------
    path("auth/token/", PublicTokenObtainPairView.as_view(), name="public_token_obtain_pair"),
    path("auth/token/refresh/", PublicTokenRefreshView.as_view(), name="public_token_refresh"),
    path("auth/token/verify/", PublicTokenVerifyView.as_view(), name="public_token_verify"),

    # ---------- API 라우트(모두 /api/ 아래) ----------
    path("api/", include((users_urls.api_urlpatterns, "users_api"), namespace="users_api")),
    path("api/", include("goals.urls")),
    path("api/", include((tasks_urls.api_urlpatterns, "tasks_api"), namespace="tasks_api")),
    path("api/", include("intakes.urls")),
    path("api/", include("feedbacks.urls")),

    # ---------- 페이지 라우트 ----------
    path("users/", include((users_urls.page_urlpatterns, "users"), namespace="users")),
    path("tasks/", include((tasks_urls.page_urlpatterns, "tasks"), namespace="tasks")),

    # ---------- 레거시/오타 경로 흡수 ----------
    re_path(r"^task/(?P<rest>.*)$", RedirectView.as_view(url="/tasks/%(rest)s", permanent=False)),
    path("task/dashboard/", RedirectView.as_view(url="/tasks/dashboard/", permanent=False)),

    # ---------- OpenAPI / 문서 ----------
    path("openapi.json", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
