# intakes/serializers.py
from rest_framework import serializers
from .models import Food, Meal, MealItem, NutritionLog


# ---------------------------
# Food
# ---------------------------
class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = "__all__"


# ---------------------------
# MealItem
# - food+grams 있으면 DB 기준 자동계산
# - 아니면 name+kcal/protein/carb/fat 자유입력 허용
# - nutrients: read-only로 계산값 노출
# ---------------------------
class MealItemSerializer(serializers.ModelSerializer):
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

    def get_nutrients(self, obj):
        return obj.resolved_nutrients()

    def validate(self, attrs):
        """
        (food & grams) 조합 또는 (name & kcal/protein/carb/fat 중 최소 하나) 입력이어야 함.
        """
        food = attrs.get("food") or getattr(self.instance, "food", None)
        grams = attrs.get("grams") if "grams" in attrs else getattr(self.instance, "grams", None)

        name = attrs.get("name") if "name" in attrs else getattr(self.instance, "name", None)
        any_macro = any(
            (attrs.get("kcal") is not None,
             attrs.get("protein_g") is not None,
             attrs.get("carb_g") is not None,
             attrs.get("fat_g") is not None)
        ) or any(
            (getattr(self.instance, "kcal", None) is not None,
             getattr(self.instance, "protein_g", None) is not None,
             getattr(self.instance, "carb_g", None) is not None,
             getattr(self.instance, "fat_g", None) is not None)
        )

        has_db_combo = (food is not None) and (grams is not None)
        has_free_combo = (name is not None) and any_macro

        if not (has_db_combo or has_free_combo):
            raise serializers.ValidationError(
                "다음 중 하나를 만족해야 합니다: (food + grams) 또는 (name + 최소 한 개의 영양값)."
            )
        return attrs


# ---------------------------
# Meal (끼니)
# - items는 읽기 전용 nested
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
# - 합계 필드는 시그널/서버에서 계산 → read_only 권장
# - user는 뷰에서 주입
# ---------------------------
class NutritionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionLog
        fields = "__all__"
        # user만 서버측 주입, 나머지 합계 필드는 임시로 writable 허용 (스모크용)
        read_only_fields = ["user"]

    def validate(self, attrs):
        # 기본 유효성: 음수 방지
        for f in ("kcal_total", "protein_total_g", "carb_total_g", "fat_total_g"):
            v = attrs.get(f)
            if v is not None and float(v) < 0:
                raise serializers.ValidationError({f: "0 이상이어야 합니다."})
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
