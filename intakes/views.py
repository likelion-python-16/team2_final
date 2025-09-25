# intakes/views.py
from rest_framework import viewsets, permissions, exceptions
from .models import Food, Meal, MealItem, NutritionLog
from .serializers import FoodSerializer, MealSerializer, MealItemSerializer, NutritionLogSerializer


class BaseUserOwnedModelViewSet(viewsets.ModelViewSet):
    """
    공통 규칙:
    - 인증 필수
    - 목록/상세 모두 '내 데이터'만 보임
    - 생성/수정 시 user를 request.user로 강제 주입(모델에 user FK가 있는 경우)
    """
    permission_classes = [permissions.IsAuthenticated]
    ordering = ("-id",)

    def get_queryset(self):
        # 자식 클래스에서 self.queryset를 지정해두면 여기서 필터링
        return self.queryset.filter(user=self.request.user).order_by(*self.ordering)

    def perform_create(self, serializer):
        # 모델에 user 필드가 있을 때만 주입 (없으면 그냥 저장)
        if "user" in [f.name for f in serializer.Meta.model._meta.fields]:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        if "user" in [f.name for f in serializer.Meta.model._meta.fields]:
            serializer.save(user=self.request.user)
        else:
            serializer.save()


# ─────────────────────────  읽기 전용 카탈로그(식품)  ─────────────────────────
class FoodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Food.objects.all().order_by("id")
    serializer_class = FoodSerializer
    permission_classes = [permissions.IsAuthenticated]


# ─────────────────────────  식단/식사/아이템  ─────────────────────────
class MealViewSet(BaseUserOwnedModelViewSet):
    queryset = Meal.objects.all()
    serializer_class = MealSerializer


class MealItemViewSet(viewsets.ModelViewSet):
    """
    MealItem은 직접 user FK가 없고 Meal을 통해 소유자가 결정되는 구조일 가능성이 높아서
    별도 처리. (meal.user == request.user 인지 검증)
    """
    queryset = MealItem.objects.select_related("meal")
    serializer_class = MealItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering = ("-id",)

    def get_queryset(self):
        return self.queryset.filter(meal__user=self.request.user).order_by(*self.ordering)

    def perform_create(self, serializer):
        meal = serializer.validated_data.get("meal")
        if meal and meal.user_id != self.request.user.id:
            raise exceptions.PermissionDenied("본인 식사에만 아이템을 추가할 수 있습니다.")
        serializer.save()

    def perform_update(self, serializer):
        meal = serializer.validated_data.get("meal") or getattr(serializer.instance, "meal", None)
        if meal and meal.user_id != self.request.user.id:
            raise exceptions.PermissionDenied("본인 식사 항목만 수정할 수 있습니다.")
        serializer.save()


# ─────────────────────────  영양 기록(= /api/intakes/ alias)  ─────────────────────────
class NutritionLogViewSet(BaseUserOwnedModelViewSet):
    """
    /api/intakes/ 는 urls.py에서 NutritionLogViewSet에 alias 되어있음.
    → CRUD 가능해야 하므로 ModelViewSet + user 자동 주입 사용.
    """
    queryset = NutritionLog.objects.all()
    serializer_class = NutritionLogSerializer
