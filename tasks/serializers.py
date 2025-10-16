# tasks/serializers.py
from rest_framework import serializers

from .models import Exercise, WorkoutPlan, TaskItem

# 선택적: 프로젝트에 있을 수도 있는 WorkoutLog
try:
    from .models import WorkoutLog
    HAS_WORKOUT_LOG = True
except Exception:
    HAS_WORKOUT_LOG = False


# ---------------------------------------
# 운동 카탈로그
# ---------------------------------------
class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = "__all__"
        read_only_fields = []


# ---------------------------------------
# 하루 계획 내 개별 Task(운동 항목)
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
            # 상태/토글
            "completed",
            "skipped",
            "skip_reason",
            "completed_at",
        ]
        read_only_fields = [
            "exercise_name",
            "exercise_detail",
            "completed_at",
        ]

    def validate_intensity(self, v):
        # 프런트에서 'mid'를 보낼 수 있으니 'medium'으로 보정
        if v == "mid":
            return TaskItem.IntensityLevel.MEDIUM
        return v

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
# 하루 운동 계획 (역참조 이름 자동 인식 버전)
# - related_name이 없으면 기본은 taskitem_set
# - related_name="tasks"로 정의한 프로젝트도 지원
# ---------------------------------------
class WorkoutPlanSerializer(serializers.ModelSerializer):
    tasks = serializers.SerializerMethodField(read_only=True)
    tasks_count = serializers.SerializerMethodField(read_only=True)
    total_duration_min = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WorkoutPlan
        fields = [
            "id",
            "user",
            "title",
            "description",          # 자기 회고
            "summary",              # AI 회고
            "target_focus",
            "source",
            "ai_model",
            "ai_version",
            "ai_prompt",
            "ai_response",
            "ai_confidence",
            "created_at",
            "updated_at",
            # 계산/확장 필드
            "tasks",
            "tasks_count",
            "total_duration_min",
        ]
        read_only_fields = [
            "user",
            "created_at",
            "updated_at",
            "tasks",
            "tasks_count",
            "total_duration_min",
        ]

    # 내부 유틸: 역참조 쿼리셋 얻기
    def _task_qs(self, obj):
        qs = None
        # 1) 기본 역참조 이름
        if hasattr(obj, "taskitem_set"):
            try:
                qs = obj.taskitem_set.all()
            except Exception:
                qs = None
        # 2) 커스텀 related_name="tasks" 대응
        if qs is None and hasattr(obj, "tasks"):
            try:
                qs = obj.tasks.all()
            except Exception:
                qs = None
        return qs or []

    def get_tasks(self, obj):
        qs = self._task_qs(obj)
        return TaskItemSerializer(qs, many=True, context=self.context).data

    def get_tasks_count(self, obj) -> int:
        qs = self._task_qs(obj)
        try:
            return qs.count() if hasattr(qs, "count") else len(list(qs))
        except Exception:
            return 0

    def get_total_duration_min(self, obj) -> int:
        try:
            return sum((ti.duration_min or 0) for ti in self._task_qs(obj))
        except Exception:
            return 0


# ---------------------------------------
# 수행 로그 (프로젝트에 있을 때만)
# ---------------------------------------
if HAS_WORKOUT_LOG:
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


# ---------------------------------------
# 대량 생성(프런트 배치 입력용)
# ---------------------------------------
class BulkTaskItemSerializer(serializers.Serializer):
    exercise = serializers.IntegerField()
    order = serializers.IntegerField(min_value=1)
    duration_min = serializers.IntegerField(min_value=1)
    sets = serializers.IntegerField(min_value=0, required=False, default=0)
    reps = serializers.IntegerField(min_value=0, required=False, default=0)
    intensity = serializers.CharField(required=False, default="medium")

    def validate_intensity(self, v):
        if v == "mid":
            return TaskItem.IntensityLevel.MEDIUM
        valid = [c[0] for c in TaskItem.IntensityLevel.choices]
        if v not in valid:
            raise serializers.ValidationError(f"intensity는 {valid} 중 하나여야 합니다.")
        return v


class BulkTaskItemListSerializer(serializers.Serializer):
    items = BulkTaskItemSerializer(many=True)
