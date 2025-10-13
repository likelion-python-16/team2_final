from rest_framework import serializers
from .models import Feedback, DailyReport, Achievement


class FeedbackSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)  # 🔁 자동주입
    class Meta:
        model = Feedback
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class DailyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReport
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = "__all__"
        read_only_fields = ["id", "achieved_at"]
