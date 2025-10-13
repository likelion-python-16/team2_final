# tasks/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone


class Exercise(models.Model):
    """운동 종목"""
    target = models.CharField(max_length=50, verbose_name="대상 부위")
    name = models.CharField(max_length=100, verbose_name="이름")
    description = models.TextField(blank=True, verbose_name="설명")
    kcal_burned_per_min = models.FloatField(default=0.0, verbose_name="분당 소모 칼로리")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "운동"
        verbose_name_plural = "운동 목록"


class WorkoutPlan(models.Model):
    """사용자의 운동 계획 (AI 생성 메타데이터 포함)"""

    class PlanSource(models.TextChoices):
        MANUAL = "manual", "Manual"
        AI_INITIAL = "ai_initial", "AI Initial"
        AI_UPDATE = "ai_update", "AI Update"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workout_plans",
        verbose_name="사용자",
    )
    goal = models.ForeignKey(
        "goals.Goal",
        on_delete=models.SET_NULL,
        related_name="workout_plans",
        null=True,
        blank=True,
        verbose_name="연계 목표",
    )
    title = models.CharField(max_length=100, verbose_name="제목")
    description = models.TextField(blank=True, verbose_name="설명")   # 자기회고 저장용
    summary = models.TextField(blank=True, verbose_name="요약")       # AI 회고 요약
    target_focus = models.CharField(max_length=50, blank=True, verbose_name="중점 영역")
    personalization_snapshot = models.JSONField(
        null=True,
        blank=True,
        verbose_name="개인화 지표",
        help_text="생성 시점의 체중/BMI/활동량 등 사용자 상태",
    )
    source = models.CharField(
        max_length=20,
        choices=PlanSource.choices,
        default=PlanSource.MANUAL,
        verbose_name="생성 출처",
    )
    ai_model = models.CharField(max_length=100, blank=True, verbose_name="AI 모델")
    ai_version = models.CharField(max_length=50, blank=True, verbose_name="AI 버전")
    ai_prompt = models.TextField(blank=True, verbose_name="AI 프롬프트")
    ai_response = models.JSONField(null=True, blank=True, verbose_name="AI 응답")
    ai_confidence = models.FloatField(null=True, blank=True, verbose_name="AI 신뢰도")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    last_synced_at = models.DateTimeField(null=True, blank=True, verbose_name="AI 마지막 동기화")

    def __str__(self):
        return f"{self.user} - {self.title}"

    class Meta:
        verbose_name = "운동 계획"
        verbose_name_plural = "운동 계획 목록"


class TaskItem(models.Model):
    """운동 계획 속 개별 운동 Task"""

    class IntensityLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    workout_plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="운동 계획",
    )
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name="task_items",
        verbose_name="운동",
    )
    duration_min = models.PositiveIntegerField(default=0, verbose_name="운동 시간(분)")
    target_sets = models.PositiveIntegerField(null=True, blank=True, verbose_name="목표 세트")
    target_reps = models.PositiveIntegerField(null=True, blank=True, verbose_name="목표 횟수")
    intensity = models.CharField(
        max_length=10,
        choices=IntensityLevel.choices,
        default=IntensityLevel.MEDIUM,
        verbose_name="강도",
    )
    notes = models.TextField(blank=True, verbose_name="메모")
    is_ai_recommended = models.BooleanField(default=False, verbose_name="AI 추천 여부")
    ai_goal = models.CharField(max_length=100, blank=True, verbose_name="AI 설정 목표")
    ai_metadata = models.JSONField(null=True, blank=True, verbose_name="AI 메타데이터")
    recommended_weight_range = models.CharField(max_length=50, blank=True, verbose_name="권장 체중 범위")
    order = models.PositiveIntegerField(default=1, verbose_name="순서")

    # ✅ 토글용 상태 필드
    completed = models.BooleanField(default=False, verbose_name="완료 여부")
    skipped = models.BooleanField(default=False, verbose_name="스킵 여부")
    skip_reason = models.CharField(max_length=200, blank=True, null=True, verbose_name="스킵 사유")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="완료 시각")

    def mark_completed(self, value: bool):
        """편의 메서드: 완료/해제 시 부수 상태 동기화"""
        self.completed = bool(value)
        if self.completed:
            self.skipped = False
            self.completed_at = timezone.now()
        else:
            self.completed_at = None

    def __str__(self):
        return f"{self.exercise.name} ({self.duration_min} min)"

    class Meta:
        verbose_name = "작업 항목"
        verbose_name_plural = "작업 항목 목록"


class WorkoutLog(models.Model):
    """운동 수행 기록"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workout_logs",
        verbose_name="사용자",
    )
    workout_plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.SET_NULL,
        related_name="workout_logs",
        null=True,
        blank=True,
        verbose_name="연계 운동 계획",
    )
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, verbose_name="운동")
    task_item = models.ForeignKey(
        TaskItem,
        on_delete=models.SET_NULL,
        related_name="workout_logs",
        null=True,
        blank=True,
        verbose_name="연계 작업",
    )
    date = models.DateField(verbose_name="날짜")
    duration_min = models.PositiveIntegerField(default=0, verbose_name="운동 시간(분)")
    kcal_burned = models.FloatField(default=0.0, verbose_name="소모 칼로리")
    perceived_exertion = models.PositiveIntegerField(null=True, blank=True, verbose_name="체감 강도")
    ai_adjusted = models.BooleanField(default=False, verbose_name="AI 조정 여부")
    notes = models.TextField(blank=True, verbose_name="메모")

    def __str__(self):
        return f"{self.user} - {self.exercise.name} ({self.date})"

    class Meta:
        verbose_name = "운동 기록"
        verbose_name_plural = "운동 기록 목록"


class WorkoutPlanGenerationLog(models.Model):
    """AI가 생성하거나 수정한 운동 계획 기록"""

    plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.CASCADE,
        related_name="generation_logs",
        verbose_name="운동 계획",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workout_plan_generation_logs",
        verbose_name="요청자",
    )
    ai_model = models.CharField(max_length=100, verbose_name="AI 모델")
    ai_version = models.CharField(max_length=50, blank=True, verbose_name="AI 버전")
    prompt = models.TextField(verbose_name="프롬프트")
    response = models.JSONField(verbose_name="응답")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")

    def __str__(self):
        return f"{self.plan} - {self.ai_model}"

    class Meta:
        verbose_name = "운동 계획 생성 로그"
        verbose_name_plural = "운동 계획 생성 로그 목록"
