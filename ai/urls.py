from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import AIViewSet

router = DefaultRouter()
router.register(r"", AIViewSet, basename="ai")

urlpatterns = router.urls
