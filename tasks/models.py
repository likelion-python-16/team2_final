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
    """사용자의 운동 계획"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_plans")
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.title}"


class TaskItem(models.Model):
    """운동 계획 속 개별 운동 Task"""
    workout_plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name="tasks")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="task_items")
    duration_min = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.exercise.name} ({self.duration_min} min)"


class WorkoutLog(models.Model):
    """운동 수행 기록"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_logs")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    date = models.DateField()
    duration_min = models.PositiveIntegerField(default=0)
    kcal_burned = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.user} - {self.exercise.name} ({self.date})"
