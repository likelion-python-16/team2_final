from rest_framework import serializers
from .models import Food, Meal, MealItem, NutritionLog

class NutritionLogSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)  # 🔁 자동주입
    class Meta:
        model = NutritionLog
        fields = "__all__"

class MealSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Meal
        fields = "__all__"

class MealItemSerializer(serializers.ModelSerializer):
    # MealItem은 meal을 통해 소유자 결정 → user 필드 없으면 생략 가능
    class Meta:
        model = MealItem
        fields = "__all__"

class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = "__all__"
