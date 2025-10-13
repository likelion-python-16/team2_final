from rest_framework import serializers
from .models import Goal, DailyGoal, GoalProgress


class GoalSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Goal
        fields = "__all__"


class GoalProgressSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = GoalProgress
        fields = "__all__"


class DailyGoalSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = DailyGoal
        fields = "__all__"
