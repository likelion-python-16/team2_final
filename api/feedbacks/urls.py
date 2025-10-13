from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeedbackViewSet, DailyReportViewSet, AchievementViewSet

router = DefaultRouter()
router.register(r'feedbacks', FeedbackViewSet, basename='feedbacks')
router.register(r'dailyreports', DailyReportViewSet, basename='dailyreport')
router.register(r'achievements', AchievementViewSet, basename='achievement')

urlpatterns = [path('', include(router.urls))]
