from rest_framework.routers import SimpleRouter
from .views import FeedbackViewSet

router = SimpleRouter()
router.register("", FeedbackViewSet, basename="feedbacks")
urlpatterns = router.urls