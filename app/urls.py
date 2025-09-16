from django.urls import path, include
from django.apps import AppConfig
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import (
    UserViewSet, GoalViewSet, TaskViewSet,
    FoodViewSet, IntakeViewSet, FeedbackViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'goals', GoalViewSet, basename='goals')
router.register(r'tasks', TaskViewSet, basename='tasks')
router.register(r'foods', FoodViewSet, basename='foods')
router.register(r'intake', IntakeViewSet, basename='intake')
router.register(r'feedbacks', FeedbackViewSet, basename='feedbacks')

urlpatterns = [
    path('', include(router.urls)),

    # OpenAPI 스키마 & Swagger UI
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"
    
    def ready(self):
        # signals가 있으면 여기서만 import 하세요.
        # from . import signals  # 예시
        pass