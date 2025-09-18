from rest_framework import serializers
from .models import CustomUser, UserProfile, HealthData


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id", "username", "email", "nickname",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserProfileSerializer(serializers.ModelSerializer):
    age = serializers.ReadOnlyField()
    bmi = serializers.ReadOnlyField()
    bmi_category = serializers.ReadOnlyField()
    daily_calories = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id", "user", "gender", "height_cm", "weight_kg",
            "target_weight_kg", "activity_level", "birth_date",
            "phone_number", "created_at", "updated_at",
            "age", "bmi", "bmi_category", "daily_calories"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "age", "bmi", "bmi_category", "daily_calories"]

    def get_daily_calories(self, obj):
        return obj.calculate_daily_calories()


class HealthDataSerializer(serializers.ModelSerializer):
    blood_pressure_status = serializers.ReadOnlyField()
    weight_change = serializers.ReadOnlyField()

    class Meta:
        model = HealthData
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "blood_pressure_status", "weight_change"]
