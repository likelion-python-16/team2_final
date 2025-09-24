from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, JsonResponse
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenVerifyView
)
from . import views
from .views import landing
from users.views import signup_view, setup_view, profile_view


def root_healthcheck(_request):
    """루트 요청에 대한 간단한 상태 정보 반환"""

    return JsonResponse({
        "status": "ok",
        "message": "Workout & feedback API root",
    })


def api_docs(_request):
    """프로젝트 루트의 openapi.json을 원본 그대로 반환"""

    doc_path = Path(settings.BASE_DIR) / "openapi.json"
    if not doc_path.exists():
        return JsonResponse({"detail": "openapi.json not found"}, status=404)

    return FileResponse(doc_path.open("rb"), content_type="application/json")


urlpatterns = [
    path("", landing, name="landing"),
    path("example/", views.example_view, name="example"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("docs", api_docs, name="api_docs"),
    path("admin/", admin.site.urls),

    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    path("signup/", signup_view, name="user_signup"),
    path("setup/", setup_view, name="user_setup"),
    path("profile/", profile_view, name="user_profile"),

    path("api/", include("users.urls")),
    path("api/", include("goals.urls")),
    path("api/", include("tasks.urls")),
    path("api/", include("intakes.urls")),
    path("api/", include("feedbacks.urls")),
]
