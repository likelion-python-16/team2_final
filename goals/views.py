from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from .models import Goal, DailyGoal, GoalProgress   
from .serializers import GoalSerializer, DailyGoalSerializer, GoalProgressSerializer

class GoalViewSet(ModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer

class DailyGoalViewSet(ModelViewSet):
    queryset = DailyGoal.objects.all()
    serializer_class = DailyGoalSerializer

class GoalProgressViewSet(ModelViewSet):
    queryset = GoalProgress.objects.all()
    serializer_class = GoalProgressSerializer
