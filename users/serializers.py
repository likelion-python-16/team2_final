# users/serializers.py
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import CustomUser, HealthData, UserProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    유저 기본 직렬화기
    - username/id는 읽기전용 (아이디 변경 방지)
    - is_active는 일반 PATCH로는 수정 불가(휴면/복구는 별도 액션에서 처리)
    """

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "is_active", "date_joined"]


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "nickname", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserProfileSerializer(serializers.ModelSerializer):
    age = serializers.ReadOnlyField()
    bmi = serializers.ReadOnlyField()
    bmi_category = serializers.ReadOnlyField()
    daily_calories = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user",
            "gender",
            "height_cm",
            "weight_kg",
            "target_weight_kg",
            "activity_level",
            "birth_date",
            "phone_number",
            "created_at",
            "updated_at",
            "age",
            "bmi",
            "bmi_category",
            "daily_calories",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "age",
            "bmi",
            "bmi_category",
            "daily_calories",
        ]

    def get_daily_calories(self, obj):
        return obj.calculate_daily_calories()


class HealthDataSerializer(serializers.ModelSerializer):
    blood_pressure_status = serializers.ReadOnlyField()
    weight_change = serializers.ReadOnlyField()

    class Meta:
        model = HealthData
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "blood_pressure_status",
            "weight_change",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    """
    회원가입 전용 Serializer
    - username/email/nickname 중복 체크
    - Django 비밀번호 정책 적용(validate_password)
    - create_user() 사용으로 비밀번호 해시 자동 처리
    """

    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(
        write_only=True, trim_whitespace=False, required=False
    )
    re_password = serializers.CharField(
        write_only=True, trim_whitespace=False, required=False
    )
    nickname = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "password2",
            "re_password",
            "nickname",
        )
        read_only_fields = ("id",)

    # --- 필드 단위 검증 ---
    def validate_username(self, value):
        if not value:
            raise serializers.ValidationError("아이디를 입력하세요.")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("이미 사용 중인 아이디입니다.")
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 등록된 이메일입니다.")
        return value

    def validate_nickname(self, value):
        if User.objects.filter(nickname=value).exists():
            raise serializers.ValidationError("이미 사용 중인 닉네임입니다.")
        return value

    # --- 교차 검증 ---
    def validate(self, attrs):
        pw = attrs.get("password")
        pw2 = attrs.get("password2") or attrs.get("re_password")
        if pw2 is not None and pw != pw2:
            raise serializers.ValidationError(
                {"password2": ["비밀번호 확인이 일치하지 않습니다."]}
            )
        validate_password(pw)
        return attrs

    # --- 생성 로직 ---
    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("password2", None)
        validated_data.pop("re_password", None)

        user = User.objects.create_user(password=password, **validated_data)
        return user
