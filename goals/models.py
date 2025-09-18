from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from intake.models import NutritionLog

class Goal(models.Model):
    # 큰 목표 (예: 다이어트)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="goals")
    goal_type = models.CharField(max_length=20)

class DailyGoal(models.Model):
    # 하루 단위 목표
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="daily_goals")
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="daily_goals")
    date = models.DateField()
    kcal_target = models.IntegerField(null=True, blank=True)
    protein_target_g = models.IntegerField(null=True, blank=True)
    workout_minutes_target = models.IntegerField(null=True, blank=True)
    completion_score = models.FloatField(null=True, blank=True)

    def compute_score(self):
        nl = NutritionLog.objects.filter(user=self.user, date=self.date).first()
        kcal_ratio = (nl.kcal_total / self.kcal_target) if (nl and self.kcal_target) else None
        protein_ratio = (nl.protein_total_g / self.protein_target_g) if (nl and self.protein_target_g) else None
        gp = GoalProgress.objects.filter(user=self.user, goal=self.goal, date=self.date).first()
        workout_ratio = (gp.completed_sessions * 30 / self.workout_minutes_target) if (gp and self.workout_minutes_target) else None
        parts = [r for r in [kcal_ratio, protein_ratio, workout_ratio] if r is not None]
        self.completion_score = round(sum(parts) / len(parts) * 100, 1) if parts else 0
        self.save()

class GoalProgress(models.Model):
    # 실제 운동/체중 기록
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="goal_progress")
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="progress")
    date = models.DateField()
    completed_sessions = models.IntegerField(null=True, blank=True)

# ---------------- signals ---------------- #
@receiver([post_save, post_delete], sender=GoalProgress)
def update_goal_score(sender, instance, **kwargs):
    # 운동 기록이 바뀌면 DailyGoal 점수 갱신
    dgs = DailyGoal.objects.filter(user=instance.user, goal=instance.goal, date=instance.date)
    for dg in dgs:
        dg.compute_score()

@receiver([post_save, post_delete], sender=NutritionLog)
def update_goal_score_from_log(sender, instance, **kwargs):
    # 식사 합계가 바뀌면 DailyGoal 점수 갱신
    dgs = DailyGoal.objects.filter(user=instance.user, date=instance.date)
    for dg in dgs:
        dg.compute_score()
