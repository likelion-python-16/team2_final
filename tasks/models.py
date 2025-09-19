from django.db import models
from django.conf import settings


class Exercise(models.Model):
    """운동 종목"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    kcal_burned_per_min = models.FloatField(default=0.0)

    def __str__(self):
        return self.name


class WorkoutPlan(models.Model):
    """사용자의 운동 계획 (AI 생성 메타데이터 포함)"""

    class PlanSource(models.TextChoices):
        MANUAL = "manual", "Manual"
        AI_INITIAL = "ai_initial", "AI Initial"
        AI_UPDATE = "ai_update", "AI Update"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_plans")
    goal = models.ForeignKey("goals.Goal", on_delete=models.SET_NULL, related_name="workout_plans", null=True, blank=True)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=PlanSource.choices, default=PlanSource.MANUAL)
    ai_model = models.CharField(max_length=100, blank=True)
    ai_version = models.CharField(max_length=50, blank=True)
    ai_prompt = models.TextField(blank=True)
    ai_response = models.JSONField(null=True, blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.title}"


class TaskItem(models.Model):
    """운동 계획 속 개별 운동 Task"""

    class IntensityLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    workout_plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name="tasks")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="task_items")
    duration_min = models.PositiveIntegerField(default=0)
    target_sets = models.PositiveIntegerField(null=True, blank=True)
    target_reps = models.PositiveIntegerField(null=True, blank=True)
    intensity = models.CharField(max_length=10, choices=IntensityLevel.choices, default=IntensityLevel.MEDIUM)
    notes = models.TextField(blank=True)
    is_ai_recommended = models.BooleanField(default=False)
    ai_goal = models.CharField(max_length=100, blank=True)
    ai_metadata = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.exercise.name} ({self.duration_min} min)"


class WorkoutLog(models.Model):
    """운동 수행 기록"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_logs")
    workout_plan = models.ForeignKey(WorkoutPlan, on_delete=models.SET_NULL, related_name="workout_logs", null=True, blank=True)
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    task_item = models.ForeignKey(TaskItem, on_delete=models.SET_NULL, related_name="workout_logs", null=True, blank=True)
    date = models.DateField()
    duration_min = models.PositiveIntegerField(default=0)
    kcal_burned = models.FloatField(default=0.0)
    perceived_exertion = models.PositiveIntegerField(null=True, blank=True)
    ai_adjusted = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user} - {self.exercise.name} ({self.date})"


class WorkoutPlanGenerationLog(models.Model):
    """AI가 생성하거나 수정한 운동 계획 기록"""

    plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name="generation_logs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="workout_plan_generation_logs")
    ai_model = models.CharField(max_length=100)
    ai_version = models.CharField(max_length=50, blank=True)
    prompt = models.TextField()
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.plan} - {self.ai_model}"
