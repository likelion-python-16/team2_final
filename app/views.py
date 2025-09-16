from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import User, Goal, Task, Food, Intake, Feedback
from .serializers import (
    UserSerializer, GoalSerializer, TaskSerializer,
    FoodSerializer, IntakeSerializer, FeedbackSerializer
)

class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]  # 초기 개발/테스트용 (추후 인증으로 변경)
    filterset_fields = "__all__"
    search_fields = []
    ordering_fields = "__all__"

class UserViewSet(BaseViewSet):
    queryset = User.objects.all().order_by("-id")
    serializer_class = UserSerializer
    search_fields = ["email", "nickname"]

class GoalViewSet(BaseViewSet):
    queryset = Goal.objects.all().order_by("-id")
    serializer_class = GoalSerializer

class TaskViewSet(BaseViewSet):
    queryset = Task.objects.all().order_by("-task_date", "-id")
    serializer_class = TaskSerializer
    search_fields = ["title", "category", "status"]

class FoodViewSet(BaseViewSet):
    queryset = Food.objects.all().order_by("name_ko")
    serializer_class = FoodSerializer
    search_fields = ["name_ko", "brand"]

class IntakeViewSet(BaseViewSet):
    queryset = Intake.objects.all().order_by("-log_date", "-id")
    serializer_class = IntakeSerializer
    search_fields = ["meal_type", "note"]

class FeedbackViewSet(BaseViewSet):
    queryset = Feedback.objects.all().order_by("-ref_date", "-id")
    serializer_class = FeedbackSerializer
    search_fields = ["scope", "topic", "message"]
