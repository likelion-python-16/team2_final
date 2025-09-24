from rest_framework import serializers
from .models import Goal, DailyGoal, GoalProgress


class GoalSerializer(serializers.ModelSerializer):
    # 클라이언트가 보낼 수 없게 막고, 응답에는 포함
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Goal
        fields = "__all__"   # 또는 필요한 필드 명시
        # extra_kwargs = {"goal_type": {"required": True}}  # (선택) 필수 명시


class GoalProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalProgress
        fields = "__all__"


class DailyGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyGoal
        fields = "__all__"
