from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from intake.models import NutritionLog


class Goal(models.Model):
    # 큰 목표 (예: 다이어트)
    user = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="goals",
        verbose_name="사용자",
    )
    goal_type = models.CharField(max_length=20, verbose_name="목표 유형")

    def __str__(self):
        return f"{self.user_id} - {self.goal_type}"

    class Meta:
        verbose_name = "목표"
        verbose_name_plural = "목표 목록"
        ordering = ["-id"]


class DailyGoal(models.Model):
    # 하루 단위 목표
    user = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="daily_goals",
        verbose_name="사용자",
    )
    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name="daily_goals",
        verbose_name="목표",
    )
    date = models.DateField(verbose_name="날짜")

    # 타겟 값들 (없을 수 있음 → null/blank 허용)
    kcal_target = models.IntegerField(
        null=True, blank=True, verbose_name="목표 열량(kcal)"
    )
    protein_target_g = models.IntegerField(
        null=True, blank=True, verbose_name="목표 단백질(g)"
    )
    workout_minutes_target = models.IntegerField(
        null=True, blank=True, verbose_name="목표 운동 시간(분)"
    )

    # 계산 결과 캐시
    completion_score = models.FloatField(
        null=True, blank=True, verbose_name="달성도 점수(%)"
    )

    def __str__(self):
        return f"{self.user_id} {self.date} - {self.goal.goal_type}"

    def compute_score(self):
        nl = NutritionLog.objects.filter(user=self.user, date=self.date).first()
        kcal_ratio = (nl.kcal_total / self.kcal_target) if (nl and self.kcal_target) else None
        protein_ratio = (nl.protein_total_g / self.protein_target_g) if (nl and self.protein_target_g) else None

        gp = GoalProgress.objects.filter(
            user=self.user, goal=self.goal, date=self.date
        ).first()
        # 운동 1세션=30분 가정
        workout_ratio = (
            (gp.completed_sessions * 30) / self.workout_minutes_target
            if (gp and self.workout_minutes_target)
            else None
        )

        parts = [r for r in (kcal_ratio, protein_ratio, workout_ratio) if r is not None]
        self.completion_score = round(sum(parts) / len(parts) * 100, 1) if parts else 0.0
        self.save(update_fields=["completion_score"])

    class Meta:
        verbose_name = "일일 목표"
        verbose_name_plural = "일일 목표 목록"
        # 같은 날 같은 목표는 1개만
        unique_together = ("user", "goal", "date")
        ordering = ["-date", "-id"]


class GoalProgress(models.Model):
    # 실제 운동/체중 기록 (여기서는 세션 수만 예시로 둠)
    user = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="goal_progress",
        verbose_name="사용자",
    )
    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name="progress",
        verbose_name="목표",
    )
    date = models.DateField(verbose_name="날짜")
    completed_sessions = models.IntegerField(
        null=True, blank=True, verbose_name="완료 세션 수"
    )

    def __str__(self):
        return f"{self.user_id} {self.date} - {self.goal.goal_type} ({self.completed_sessions or 0}회)"

    class Meta:
        verbose_name = "목표 진행도"
        verbose_name_plural = "목표 진행도 목록"
        unique_together = ("user", "goal", "date")
        ordering = ["-date", "-id"]


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
