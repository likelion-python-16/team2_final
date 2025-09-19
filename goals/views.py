from rest_framework import viewsets, permissions
from .models import Goal, DailyGoal, GoalProgress
from .serializers import GoalSerializer, DailyGoalSerializer, GoalProgressSerializer

class GoalViewSet(viewsets.ModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Goal.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class DailyGoalViewSet(viewsets.ModelViewSet):
    queryset = DailyGoal.objects.all()
    serializer_class = DailyGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DailyGoal.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class GoalProgressViewSet(viewsets.ModelViewSet):  # 필요 시 ReadOnly로 바꿀 수 있음
    queryset = GoalProgress.objects.all()
    serializer_class = GoalProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GoalProgress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
