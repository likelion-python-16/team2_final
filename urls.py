from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    # Root → Swagger UI
    path("", RedirectView.as_view(pattern_name="swagger-ui", permanent=False), name="root"),

    # App routers
    path("api/users/", include("users.urls")),
    path("api/goals/", include("goals.urls")),
    path("api/tasks/", include("tasks.urls")),
    path("api/intake/", include("intake.urls")),
    path("api/feedbacks/", include("feedbacks.urls")),

    path("api-auth/", include("rest_framework.urls")),

    # Django admin
    path("admin/", admin.site.urls),

    # OpenAPI schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),

    # Swagger UI
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # ReDoc
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Prometheus metrics
    path("", include("django_prometheus.urls")),

    # Health check
    path("healthz", healthz),
]
