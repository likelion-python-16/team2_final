from rest_framework import serializers
from .models import Exercise, WorkoutPlan, TaskItem, WorkoutLog


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = "__all__"


class TaskItemSerializer(serializers.ModelSerializer):
    exercise_name = serializers.ReadOnlyField(source="exercise.name")

    class Meta:
        model = TaskItem
        fields = ["id", "workout_plan", "exercise", "exercise_name", "duration_min", "order"]


class WorkoutPlanSerializer(serializers.ModelSerializer):
    tasks = TaskItemSerializer(many=True, read_only=True)

    class Meta:
        model = WorkoutPlan
        fields = ["id", "user", "title", "description", "created_at", "tasks"]


class WorkoutLogSerializer(serializers.ModelSerializer):
    exercise_name = serializers.ReadOnlyField(source="exercise.name")

    class Meta:
        model = WorkoutLog
        fields = ["id", "user", "exercise", "exercise_name", "date", "duration_min", "kcal_burned"]
