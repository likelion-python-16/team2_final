from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

def healthz(_request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    # 앱 기본 라우터
    path("users/", include("users.urls")),
    path("goals/", include("goals.urls")),
    path("tasks/", include("tasks.urls")),
    path("intake/", include("intake.urls")),
    path("feedbacks/", include("feedbacks.urls")),
    path("api-auth/", include("rest_framework.urls")),

    # Django admin
    path("admin/", admin.site.urls),

    # OpenAPI schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),

    # Swagger UI
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # ReDoc
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Prometheus metrics (이미 django-prometheus 설치한 경우)
    path("", include("django_prometheus.urls")),

    # Health check
    path("healthz", healthz),
]
