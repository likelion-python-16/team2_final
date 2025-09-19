from rest_framework import viewsets, permissions
from .models import Food, Meal, MealItem, NutritionLog
from .serializers import FoodSerializer, MealSerializer, MealItemSerializer, NutritionLogSerializer

class FoodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Food.objects.all()
    serializer_class = FoodSerializer
    permission_classes = [permissions.IsAuthenticated]

    # 관리자만 쓰기 가능하게 하고 싶다면 ModelViewSet + custom permission으로 바꿔도 됨

class MealViewSet(viewsets.ModelViewSet):
    queryset = Meal.objects.all()
    serializer_class = MealSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Meal.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class MealItemViewSet(viewsets.ModelViewSet):
    queryset = MealItem.objects.all()
    serializer_class = MealItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MealItem.objects.filter(meal__user=self.request.user)

class NutritionLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NutritionLog.objects.all()
    serializer_class = NutritionLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NutritionLog.objects.filter(user=self.request.user)
