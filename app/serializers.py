from rest_framework import serializers
from .models import User, Goal, Task, Food, Intake, Feedback

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"

class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = "__all__"

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"

class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = "__all__"

class IntakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intake
        fields = "__all__"

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = "__all__"
