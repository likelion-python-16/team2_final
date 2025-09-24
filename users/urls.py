from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import UserViewSet

router = DefaultRouter()
# 사용자 CRUD + me/deactivate/reactivate 액션
router.register(r'users', UserViewSet, basename='users')

urlpatterns = [
    path("", include(router.urls)),
]
