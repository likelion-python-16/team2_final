from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FoodViewSet, MealViewSet, MealItemViewSet, NutritionLogViewSet

router = DefaultRouter()
router.register(r'api/foods', FoodViewSet, basename='food')
router.register(r'api/meals', MealViewSet, basename='meal')
router.register(r'api/mealitems', MealItemViewSet, basename='mealitem')
router.register(r'api/nutritionlogs', NutritionLogViewSet, basename='nutritionlog')

urlpatterns = [path('', include(router.urls))]