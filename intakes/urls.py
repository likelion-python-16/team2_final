from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FoodViewSet, MealViewSet, MealItemViewSet, NutritionLogViewSet

router = DefaultRouter()
router.register(r'foods', FoodViewSet, basename='food')
router.register(r'meals', MealViewSet, basename='meal')
router.register(r'mealitems', MealItemViewSet, basename='mealitem')
router.register(r'nutritionlogs', NutritionLogViewSet, basename='nutritionlog')

# ✅ 테스트 호환용 alias: /api/intakes/ → NutritionLogViewSet에 매핑
router.register(r'intakes',       NutritionLogViewSet,basename='intakes')

urlpatterns = [path('', include(router.urls))]