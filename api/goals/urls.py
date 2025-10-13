from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import GoalViewSet, DailyGoalViewSet, GoalProgressViewSet

router = DefaultRouter()
router.register(r"goals", GoalViewSet, basename="goal")
router.register(r"dailygoals", DailyGoalViewSet, basename="dailygoal")
router.register(r"goalprogress", GoalProgressViewSet, basename="goalprogress")

urlpatterns = [
    path("", include(router.urls)),
]