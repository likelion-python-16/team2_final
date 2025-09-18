from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from .models import Food, Meal, NutritionLog
from .serializers import FoodSerializer, MealSerializer, NutritionLogSerializer

class FoodViewSet(ModelViewSet):
    queryset = Food.objects.all()
    serializer_class = FoodSerializer

class MealViewSet(ModelViewSet):
    queryset = Meal.objects.all()
    serializer_class = MealSerializer

class NutritionLogViewSet(ModelViewSet):
    queryset = NutritionLog.objects.all()
    serializer_class = NutritionLogSerializer

