from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GoalViewSet, DailyGoalViewSet, GoalProgressViewSet

router = DefaultRouter()
router.register(r'api/goals', GoalViewSet)
router.register(r'api/dailygoals', DailyGoalViewSet)
router.register(r'api/progress', GoalProgressViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
