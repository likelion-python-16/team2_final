from rest_framework.routers import SimpleRouter
from .views import GoalViewSet, DailyGoalViewSet, GoalProgressViewSet 

router = SimpleRouter()
router.register("goals", GoalViewSet)
router.register("daily-goals", DailyGoalViewSet)
router.register("goal-progress", GoalProgressViewSet)
urlpatterns = router.urls
