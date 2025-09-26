from rest_framework import serializers
from .models import Exercise, WorkoutPlan, TaskItem, WorkoutLog


# ---------------------------------------
# 운동 카탈로그 (읽기 전용으로도 쓰기 쉬움)
# ---------------------------------------
class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        # target, name, description, kcal_burned_per_min
        fields = "__all__"
        read_only_fields = []


# ---------------------------------------
# 하루 계획 내 개별 Task(운동 항목)
# - exercise_name / exercise_detail: 읽기 전용 보조 정보
# - 기본 검증(duration_min, order >= 0)
# - 소유권 검증은 뷰에서 한 번 더(perform_create)
# ---------------------------------------
class TaskItemSerializer(serializers.ModelSerializer):
    exercise_name = serializers.ReadOnlyField(source="exercise.name")
    exercise_detail = ExerciseSerializer(source="exercise", read_only=True)

    class Meta:
        model = TaskItem
        fields = [
            "id",
            "workout_plan",
            "exercise",
            "exercise_name",
            "exercise_detail",
            "duration_min",
            "target_sets",
            "target_reps",
            "intensity",
            "notes",
            "is_ai_recommended",
            "ai_goal",
            "ai_metadata",
            "recommended_weight_range",
            "order",
        ]
        extra_kwargs = {
            # 필요 시 아래 주석 해제해서 FK를 write_only로 숨길 수 있음
            # "workout_plan": {"write_only": True},
            # "exercise": {"write_only": True},
        }

    def validate_duration_min(self, v):
        if v is not None and v < 0:
            raise serializers.ValidationError("duration_min은 0 이상이어야 해요.")
        return v

    def validate_order(self, v):
        if v is not None and v < 0:
            raise serializers.ValidationError("order는 0 이상이어야 해요.")
        return v

    def validate(self, attrs):
        # 소유권 1차 방어(뷰에서도 검사하지만 메시지를 더 친절하게)
        request = self.context.get("request")
        plan = attrs.get("workout_plan") or getattr(self.instance, "workout_plan", None)
        if request and plan and plan.user_id != request.user.id:
            raise serializers.ValidationError("내 플랜(TaskItem)만 생성/수정할 수 있습니다.")
        return attrs


# ---------------------------------------
# 하루 운동 계획
# - 읽기 전용으로 tasks 포함
# - 편의 필드: tasks_count, total_duration_min
# - AI/메타 필드 반영
# ---------------------------------------
class WorkoutPlanSerializer(serializers.ModelSerializer):
    tasks = TaskItemSerializer(many=True, read_only=True)
    tasks_count = serializers.SerializerMethodField(read_only=True)
    total_duration_min = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WorkoutPlan
        fields = [
            "id",
            "user",
            "goal",
            "title",
            "description",               # 자기 회고 저장 용
            "summary",                   # AI 회고 요약
            "target_focus",
            "personalization_snapshot",
            "source",
            "ai_model",
            "ai_version",
            "ai_prompt",
            "ai_response",
            "ai_confidence",
            "created_at",
            "updated_at",
            "last_synced_at",
            # 읽기 전용 확장
            "tasks",
            "tasks_count",
            "total_duration_min",
        ]
        read_only_fields = [
            "user", "created_at", "updated_at", "last_synced_at",
            "tasks", "tasks_count", "total_duration_min",
        ]

    def get_tasks_count(self, obj) -> int:
        # related_name='tasks'
        return obj.tasks.count()

    def get_total_duration_min(self, obj) -> int:
        return sum((ti.duration_min or 0) for ti in obj.tasks.all())


# ---------------------------------------
# 수행 로그
# - exercise_name 읽기 전용
# - user는 보통 뷰에서 주입 → read_only 권장
# ---------------------------------------
class WorkoutLogSerializer(serializers.ModelSerializer):
    exercise_name = serializers.ReadOnlyField(source="exercise.name")

    class Meta:
        model = WorkoutLog
        fields = [
            "id",
            "user",
            "workout_plan",
            "task_item",
            "exercise",
            "exercise_name",
            "date",
            "duration_min",
            "kcal_burned",
            "perceived_exertion",
            "ai_adjusted",
            "notes",
        ]
        read_only_fields = ["user"]
