# goals/views.py
from rest_framework import viewsets, permissions
from .models import Goal, DailyGoal, GoalProgress
from .serializers import GoalSerializer, DailyGoalSerializer, GoalProgressSerializer


class BaseUserOwnedModelViewSet(viewsets.ModelViewSet):
    """
    공통 규칙:
    - 인증 필수
    - 목록/상세 모두 '내 데이터'만 보임
    - 생성/수정 시 user를 request.user로 강제 주입
    """
    permission_classes = [permissions.IsAuthenticated]
    ordering = ("-id",)  # 최신순

    def get_queryset(self):
        # 모델에 user FK가 있다고 가정
        return self.queryset.filter(user=self.request.user).order_by(*self.ordering)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        # 클라이언트가 user를 바디로 보내도 무시하고 항상 현재 사용자로 고정
        serializer.save(user=self.request.user)


class GoalViewSet(BaseUserOwnedModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer


class DailyGoalViewSet(BaseUserOwnedModelViewSet):
    queryset = DailyGoal.objects.all()
    serializer_class = DailyGoalSerializer


class GoalProgressViewSet(BaseUserOwnedModelViewSet):
    queryset = GoalProgress.objects.all()
    serializer_class = GoalProgressSerializer
