# intakes/serializers.py
from decimal import Decimal, InvalidOperation
from rest_framework import serializers
from .models import Food, Meal, MealItem, NutritionLog


# ---------------------------
# 공통: Decimal → float 강제 직렬화 믹스인
# - DRF 기본 동작(Decimal → 문자열)로 인해 테스트에서 '2.00' == 2 불일치가 났던 이슈 방지
# - Meta.numeric_fields 에 명시된 필드만 변환
# ---------------------------
class NumericCoerceSerializer(serializers.ModelSerializer):
    def _coerce_number(self, val):
        if val is None:
            return None
        if isinstance(val, Decimal):
            return float(round(val, 2))
        # 일부 DB/검증 단계에서 str로 들어올 수도 있음
        if isinstance(val, str):
            try:
                return float(round(Decimal(val), 2))
            except (InvalidOperation, ValueError):
                return val
        return val

    def to_representation(self, instance):
        data = super().to_representation(instance)
        numeric_fields = getattr(self.Meta, "numeric_fields", ())
        for f in numeric_fields:
            if f in data:
                data[f] = self._coerce_number(data[f])
        return data


# ---------------------------
# Food
# ---------------------------
class FoodSerializer(NumericCoerceSerializer):
    class Meta:
        model = Food
        fields = "__all__"
        # 필요 시 여기에 numeric_fields = [...] 추가 가능


# ---------------------------
# MealItem
# - (food + grams) 이면 DB 100g 기준으로 자동계산
# - 아니면 (name + kcal/protein_g/carb_g/fat_g 중 ≥1) 자유입력 허용
# - nutrients: obj.resolved_nutrients() 결과(read-only)
# - 숫자 필드들을 float로 직렬화(Decimal 문자열 이슈 방지)
# ---------------------------
class MealItemSerializer(NumericCoerceSerializer):
    food_name = serializers.ReadOnlyField(source="food.name")
    nutrients = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MealItem
        fields = [
            "id",
            "meal",
            "food",
            "food_name",
            "grams",
            "name",
            "kcal",
            "protein_g",
            "carb_g",
            "fat_g",
            "nutrients",
        ]
        # 숫자 직렬화 강제 대상
        numeric_fields = ["kcal", "protein_g", "carb_g", "fat_g"]

    def get_nutrients(self, obj):
        # 모델 메서드에서 food+grams 우선 로직/반올림 등을 처리한다고 가정
        return obj.resolved_nutrients()

    def validate(self, attrs):
        """
        허용 조합:
          1) (food & grams>0)  → DB 기반 자동계산
          2) (name & [kcal|protein_g|carb_g|fat_g] 중 ≥1) → 자유입력
        추가 규칙:
          - food가 있으면 grams 필요(>0)
          - 자유입력 모드에서 grams는 선택(무시 가능)
        """
        instance = getattr(self, "instance", None)

        # 현재/신규 값 병합해서 판단
        food = attrs.get("food", getattr(instance, "food", None))
        grams = attrs.get("grams", getattr(instance, "grams", None))
        name = attrs.get("name", getattr(instance, "name", None))

        # 매크로 필드 존재 여부
        incoming_macros = {
            "kcal": attrs.get("kcal", getattr(instance, "kcal", None)),
            "protein_g": attrs.get("protein_g", getattr(instance, "protein_g", None)),
            "carb_g": attrs.get("carb_g", getattr(instance, "carb_g", None)),
            "fat_g": attrs.get("fat_g", getattr(instance, "fat_g", None)),
        }
        any_macro = any(v is not None for v in incoming_macros.values())

        has_db_combo = (food is not None) and (grams is not None)
        has_free_combo = (name is not None) and any_macro

        # food가 있다면 grams 필수이며 양수
        if food is not None:
            if grams is None:
                raise serializers.ValidationError({"grams": "food가 있을 때 grams는 필수입니다."})
            try:
                if float(grams) <= 0:
                    raise serializers.ValidationError({"grams": "0보다 커야 합니다."})
            except (TypeError, ValueError):
                raise serializers.ValidationError({"grams": "유효한 숫자여야 합니다."})

        if not (has_db_combo or has_free_combo):
            raise serializers.ValidationError(
                "다음 중 하나를 만족해야 합니다: (food + grams) 또는 (name + 최소 한 개의 영양값)."
            )

        return attrs


# ---------------------------
# Meal (끼니)
# - items는 read-only nested(현재 설계 유지)
# - user는 뷰에서 request.user로 주입
# ---------------------------
class MealSerializer(serializers.ModelSerializer):
    items = MealItemSerializer(many=True, read_only=True)

    class Meta:
        model = Meal
        fields = [
            "id",
            "user",
            "log_date",
            "meal_type",
            "items",
        ]
        read_only_fields = ["user", "items"]


# ---------------------------
# NutritionLog (하루 합계 캐시)
# - 합계는 서버/시그널/액션에서 계산 → read_only 권장
# - 스모크/관리 편의 위해 일단 writable 허용(테스트 단계)
# - 숫자 직렬화 강제(Decimal 문자열 이슈 방지)
# ---------------------------
class NutritionLogSerializer(NumericCoerceSerializer):
    class Meta:
        model = NutritionLog
        fields = "__all__"
        read_only_fields = ["user"]
        numeric_fields = ["kcal_total", "protein_total_g", "carb_total_g", "fat_total_g"]

    def validate(self, attrs):
        # 기본 유효성: 음수 방지
        for f in ("kcal_total", "protein_total_g", "carb_total_g", "fat_total_g"):
            v = attrs.get(f, None)
            if v is not None:
                try:
                    if float(v) < 0:
                        raise serializers.ValidationError({f: "0 이상이어야 합니다."})
                except (TypeError, ValueError):
                    raise serializers.ValidationError({f: "유효한 숫자여야 합니다."})
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["user"] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # user는 외부에서 바꾸지 않음
        validated_data.pop("user", None)
        return super().update(instance, validated_data)
