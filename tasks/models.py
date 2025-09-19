from django.db import models
from django.conf import settings


class Exercise(models.Model):
    """운동 종목"""
    name = models.CharField(max_length=100, verbose_name="이름")
    description = models.TextField(blank=True, verbose_name="설명")
    kcal_burned_per_min = models.FloatField(default=0.0, verbose_name="분당 소모 칼로리")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "운동"
        verbose_name_plural = "운동 목록"

class WorkoutPlan(models.Model):
    """사용자의 운동 계획"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_plans", verbose_name="사용자")
    title = models.CharField(max_length=100, verbose_name="제목")
    description = models.TextField(blank=True, verbose_name="설명")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")

    def __str__(self):
        return f"{self.user} - {self.title}"

    class Meta:
        verbose_name = "운동 계획"
        verbose_name_plural = "운동 계획 목록"

class TaskItem(models.Model):
    """운동 계획 속 개별 운동 Task"""
    workout_plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name="tasks", verbose_name="운동 계획")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="task_items", verbose_name="운동")
    duration_min = models.PositiveIntegerField(default=0, verbose_name="운동 시간(분)")
    order = models.PositiveIntegerField(default=1, verbose_name="순서")

    def __str__(self):
        return f"{self.exercise.name} ({self.duration_min} min)"

    class Meta:
        verbose_name = "작업 항목"
        verbose_name_plural = "작업 항목 목록"

class WorkoutLog(models.Model):
    """운동 수행 기록"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_logs", verbose_name="사용자")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, verbose_name="운동")
    date = models.DateField(verbose_name="날짜")
    duration_min = models.PositiveIntegerField(default=0, verbose_name="운동 시간(분)")
    kcal_burned = models.FloatField(default=0.0, verbose_name="소모 칼로리")

    def __str__(self):
        return f"{self.user} - {self.exercise.name} ({self.date})"
    class Meta:
        verbose_name = "운동 기록"
        verbose_name_plural = "운동 기록 목록"
