from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeedbackViewSet, DailyReportViewSet, AchievementViewSet

router = DefaultRouter()
router.register(r'api/feedbacks', FeedbackViewSet, basename='feedback')
router.register(r'api/dailyreports', DailyReportViewSet, basename='dailyreport')
router.register(r'api/achievements', AchievementViewSet, basename='achievement')

urlpatterns = [path('', include(router.urls))]
