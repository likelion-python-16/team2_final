# intakes/views.py
from datetime import date as _date
from rest_framework import viewsets, permissions, exceptions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Food, Meal, MealItem, NutritionLog
from .serializers import (
    FoodSerializer, MealSerializer, MealItemSerializer, NutritionLogSerializer
)

MEAL_TYPES = {"아침", "점심", "저녁", "간식"}


class BaseUserOwnedModelViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    ordering = ("-id",)

    def _model_has_user_fk(self, model_cls) -> bool:
        return any(f.name == "user" for f in model_cls._meta.fields)

    def get_queryset(self):
        qs = self.queryset.all()
        model_cls = getattr(self.queryset, "model", None)
        if model_cls and self._model_has_user_fk(model_cls):
            qs = qs.filter(user=self.request.user)
        return qs.order_by(*self.ordering)

    def perform_create(self, serializer):
        model = serializer.Meta.model
        if self._model_has_user_fk(model):
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        model = serializer.Meta.model
        if self._model_has_user_fk(model):
            serializer.save(user=self.request.user)
        else:
            serializer.save()


# ─────────────────────────  식품 카탈로그  ─────────────────────────
class FoodViewSet(viewsets.ModelViewSet):
    """
    GET /api/foods/?q=닭가슴살   ← 부분일치 검색
    ※ 쓰기(POST/PUT/PATCH/DELETE)는 관리자만 허용
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

    def _assert_staff(self):
        if not (self.request.user and self.request.user.is_staff):
            raise exceptions.PermissionDenied("식품 수정은 관리자만 가능합니다.")

    def create(self, request, *args, **kwargs):
        self._assert_staff()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._assert_staff()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._assert_staff()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._assert_staff()
        return super().destroy(request, *args, **kwargs)


# ─────────────────────────  식사(끼니)  ─────────────────────────
class MealViewSet(BaseUserOwnedModelViewSet):
    """
    GET /api/meals/?log_date=YYYY-MM-DD&meal_type=아침
    (호환) date=YYYY-MM-DD 도 지원
    """
    queryset = Meal.objects.select_related("user").prefetch_related("items")
    serializer_class = MealSerializer

    def _get_log_date_param(self):
        qp = self.request.query_params
        return qp.get("log_date") or qp.get("date")

    def get_queryset(self):
        qs = super().get_queryset()
        log_date = self._get_log_date_param()
        if log_date:
            qs = qs.filter(log_date=log_date)
        meal_type = self.request.query_params.get("meal_type")
        if meal_type:
            # 필요 시 화이트리스트 강제
            # if meal_type not in MEAL_TYPES:
            #     raise exceptions.ValidationError({"meal_type": f"허용값: {sorted(MEAL_TYPES)}"})
            qs = qs.filter(meal_type=meal_type)
        return qs

    @action(detail=False, methods=["get"], url_path="by-date")
    def by_date(self, request):
        """
        GET /api/meals/by-date/?log_date=YYYY-MM-DD
        (호환) date=YYYY-MM-DD
        """
        log_date = self._get_log_date_param()
        if not log_date:
            return Response({"detail": "log_date=YYYY-MM-DD 쿼리 파라미터가 필요합니다."}, status=400)
        qs = self.get_queryset().filter(log_date=log_date).order_by("id")
        ser = self.get_serializer(qs, many=True)
        return Response(ser.data)

    @action(detail=False, methods=["post"], url_path="ensure")
    def ensure(self, request):
        """
        POST /api/meals/ensure/?log_date=YYYY-MM-DD&meal_type=아침
        해당 날짜/끼니에 Meal이 없으면 생성 후 반환.
        """
        log_date = self._get_log_date_param() or _date.today().isoformat()
        meal_type = request.query_params.get("meal_type")
        if not meal_type:
            return Response({"detail": "meal_type 쿼리 파라미터가 필요합니다."}, status=400)
        # if meal_type not in MEAL_TYPES:
        #     return Response({"detail": f"meal_type 허용값: {sorted(MEAL_TYPES)}"}, status=400)
        obj, created = Meal.objects.get_or_create(
            user=request.user, log_date=log_date, meal_type=meal_type
        )
        return Response(self.get_serializer(obj).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# ─────────────────────────  식사 항목  ─────────────────────────
class MealItemViewSet(viewsets.ModelViewSet):
    """
    MealItem은 meal.user를 통해 소유자가 결정됨.
    - 생성/수정 시 meal.user == request.user 검증
    - grams 기반 자동계산 값은 Serializer의 read-only 필드로 제공
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
            raise exceptions.ValidationError({"meal": "이 필드는 필수입니다."})
        if meal.user_id != self.request.user.id:
            raise exceptions.PermissionDenied("본인 식사에만 아이템을 추가할 수 있습니다.")
        serializer.save()

    def perform_update(self, serializer):
        new_meal = serializer.validated_data.get("meal")
        if new_meal and new_meal.user_id != self.request.user.id:
            raise exceptions.PermissionDenied("본인 식사 항목만 수정할 수 있습니다.")
        serializer.save()


# ─────────────────────────  영양 기록(집계)  ─────────────────────────
class NutritionLogViewSet(BaseUserOwnedModelViewSet):
    """
    - 시그널로 Meal/MealItem 변동 시 자동 집계됨.
    - 편의 액션:
      * GET  /api/nutritionlogs/by-date/?log_date=YYYY-MM-DD
      * POST /api/nutritionlogs/ensure/?log_date=YYYY-MM-DD  (미지정 시 오늘)
      * POST /api/nutritionlogs/{id}/recalc/
    """
    queryset = NutritionLog.objects.select_related("user")
    serializer_class = NutritionLogSerializer

    def _get_log_date_param(self):
        qp = self.request.query_params
        return qp.get("log_date") or qp.get("date")

    def get_queryset(self):
        qs = super().get_queryset()
        log_date = self._get_log_date_param()
        if log_date:
            qs = qs.filter(date=log_date)
        return qs

    @action(detail=False, methods=["get"], url_path="by-date")
    def by_date(self, request):
        log_date = self._get_log_date_param()
        if not log_date:
            return Response({"detail": "log_date=YYYY-MM-DD 쿼리 파라미터가 필요합니다."}, status=400)
        inst = self.get_queryset().filter(date=log_date).first()
        if not inst:
            return Response({"detail": "해당 날짜의 NutritionLog가 없습니다."}, status=404)
        return Response(self.get_serializer(inst).data)

    @action(detail=False, methods=["post"], url_path="ensure")
    def ensure(self, request):
        log_date = self._get_log_date_param() or _date.today().isoformat()
        obj, created = NutritionLog.objects.get_or_create(user=request.user, date=log_date)
        if created:
            obj.save()
        return Response(self.get_serializer(obj).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="recalc")
    def recalc(self, request, pk=None):
        log = self.get_object()
        log.recalc()
        return Response(self.get_serializer(log).data)
