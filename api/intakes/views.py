# intakes/views.py
from rest_framework import viewsets, permissions, exceptions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Food, Meal, MealItem, NutritionLog
from .serializers import (
    FoodSerializer, MealSerializer, MealItemSerializer, NutritionLogSerializer
)


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
        # 자식 클래스에서 self.queryset 지정 → 여기서 내 소유만 필터
        qs = self.queryset
        if hasattr(self.serializer_class.Meta.model, "user"):
            qs = qs.filter(user=self.request.user)
        return qs.order_by(*self.ordering)

    def perform_create(self, serializer):
        # 모델에 user 필드가 있을 때만 주입
        model = serializer.Meta.model
        field_names = [f.name for f in model._meta.fields]
        if "user" in field_names:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        model = serializer.Meta.model
        field_names = [f.name for f in model._meta.fields]
        if "user" in field_names:
            serializer.save(user=self.request.user)
        else:
            serializer.save()


# ─────────────────────────  읽기 전용 카탈로그(식품)  ─────────────────────────
class FoodViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/foods/?q=닭가슴살  ← 이름 부분일치 검색
    """
    queryset = Food.objects.all().order_by("id")
    serializer_class = FoodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


# ─────────────────────────  식단/식사/아이템  ─────────────────────────
class MealViewSet(BaseUserOwnedModelViewSet):
    """
    GET /api/meals/?date=YYYY-MM-DD&meal_type=아침
    """
    queryset = Meal.objects.select_related("user").prefetch_related("items")
    serializer_class = MealSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        date = self.request.query_params.get("date")
        if date:
            qs = qs.filter(log_date=date)
        meal_type = self.request.query_params.get("meal_type")
        if meal_type:
            qs = qs.filter(meal_type=meal_type)
        return qs

    @action(detail=False, methods=["get"], url_path="by-date")
    def by_date(self, request):
        """
        GET /api/meals/by-date/?date=YYYY-MM-DD
        해당 날짜의 끼니(아침/점심/저녁/간식) 목록 반환
        """
        date = request.query_params.get("date")
        if not date:
            return Response({"detail": "date=YYYY-MM-DD 쿼리 파라미터가 필요합니다."}, status=400)
        qs = self.get_queryset().filter(log_date=date).order_by("id")
        ser = self.get_serializer(qs, many=True)
        return Response(ser.data)


class MealItemViewSet(viewsets.ModelViewSet):
    """
    MealItem은 meal.user를 통해 소유자가 결정됨.
    - 생성/수정 시 meal.user == request.user 검증
    """
    queryset = MealItem.objects.select_related("meal", "food")
    serializer_class = MealItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering = ("-id",)

    def get_queryset(self):
        return self.queryset.filter(meal__user=self.request.user).order_by(*self.ordering)

    def perform_create(self, serializer):
        meal = serializer.validated_data.get("meal")
        if not meal:
            raise exceptions.ValidationError("meal 필드는 필수입니다.")
        if meal.user_id != self.request.user.id:
            raise exceptions.PermissionDenied("본인 식사에만 아이템을 추가할 수 있습니다.")
        serializer.save()

    def perform_update(self, serializer):
        meal = serializer.validated_data.get("meal") or getattr(serializer.instance, "meal", None)
        if meal and meal.user_id != self.request.user.id:
            raise exceptions.PermissionDenied("본인 식사 항목만 수정할 수 있습니다.")
        serializer.save()


# ─────────────────────────  영양 기록(= /api/intakes/ alias 가능)  ─────────────────────────
class NutritionLogViewSet(BaseUserOwnedModelViewSet):
    """
    - 시그널로 Meal/MealItem 변동 시 자동 집계됨.
    - 편의 액션:
      * GET  /api/nutritionlogs/by-date/?date=YYYY-MM-DD
      * POST /api/nutritionlogs/ensure/?date=YYYY-MM-DD   ← 없으면 생성(0으로)
      * POST /api/nutritionlogs/{id}/recalc/               ← 강제 재집계
    """
    queryset = NutritionLog.objects.select_related("user")
    serializer_class = NutritionLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        date = self.request.query_params.get("date")
        if date:
            qs = qs.filter(date=date)
        return qs

    @action(detail=False, methods=["get"], url_path="by-date")
    def by_date(self, request):
        date = request.query_params.get("date")
        if not date:
            return Response({"detail": "date=YYYY-MM-DD 쿼리 파라미터가 필요합니다."}, status=400)
        inst = self.get_queryset().filter(date=date).first()
        if not inst:
            return Response({"detail": "해당 날짜의 NutritionLog가 없습니다."}, status=404)
        return Response(self.get_serializer(inst).data)

    @action(detail=False, methods=["post"], url_path="ensure")
    def ensure(self, request):
        """
        POST /api/nutritionlogs/ensure/?date=YYYY-MM-DD
        해당 날짜의 NutritionLog가 없으면 0값으로 생성하여 반환.
        """
        date = request.query_params.get("date")
        if not date:
            return Response({"detail": "date=YYYY-MM-DD 쿼리 파라미터가 필요합니다."}, status=400)
        obj, created = NutritionLog.objects.get_or_create(user=request.user, date=date)
        if created:
            obj.save()  # 기본값(0) 저장
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="recalc")
    def recalc(self, request, pk=None):
        """
        POST /api/nutritionlogs/{id}/recalc/
        Meal/MealItem 합계를 다시 계산해서 저장.
        """
        log = self.get_object()
        log.recalc()
        return Response(self.get_serializer(log).data)
