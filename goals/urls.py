from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GoalViewSet, DailyGoalViewSet, GoalProgressViewSet

router = DefaultRouter()
router.register(r'goals', GoalViewSet, basename='goals')
router.register(r'dailygoals', DailyGoalViewSet, basename='dailygoals')
router.register(r'progress', GoalProgressViewSet, basename='progress')

urlpatterns = [
    path('', include(router.urls)),
]
