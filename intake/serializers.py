from rest_framework import serializers
from .models import Food, Meal, MealItem, NutritionLog 

class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = "__all__"

class MealItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealItem
        fields = "__all__"

class MealSerializer(serializers.ModelSerializer):
    items = MealItemSerializer(many=True, read_only=True)

    class Meta:
        model = Meal
        fields = "__all__"

class NutritionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionLog
        fields = "__all__"