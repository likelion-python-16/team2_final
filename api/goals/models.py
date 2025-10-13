from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# 식사 합계 참조
from intakes.models import NutritionLog


class Goal(models.Model):
    """큰 목표 (예: 다이어트)"""
    user = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="goals",
        verbose_name="사용자",
    )
    goal_type = models.CharField(max_length=20, verbose_name="목표 유형")

    def __str__(self) -> str:
        return f"{self.user_id} - {self.goal_type}"

    class Meta:
        verbose_name = "목표"
        verbose_name_plural = "목표 목록"
        ordering = ["-id"]


class DailyGoal(models.Model):
    """하루 단위 목표"""
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

    # 타겟 값(없을 수 있음)
    kcal_target = models.IntegerField(null=True, blank=True, verbose_name="목표 열량(kcal)")
    protein_target_g = models.IntegerField(null=True, blank=True, verbose_name="목표 단백질(g)")
    workout_minutes_target = models.IntegerField(null=True, blank=True, verbose_name="목표 운동 시간(분)")

    # 계산 결과 캐시
    completion_score = models.FloatField(null=True, blank=True, verbose_name="달성도 점수(%)")

    def __str__(self) -> str:
        return f"{self.user_id} {self.date} - {self.goal.goal_type}"

    def compute_score(self) -> None:
        """
        NutritionLog와 GoalProgress를 종합해서 달성도(%)를 계산해 completion_score에 캐시.
        - kcal/protein: 목표 대비 비율
        - workout: '세션 1회 = 30분' 가정으로 목표 시간 대비 비율
        - 사용 가능한 지표만 평균
        """
        # 식사 합계 (없을 수 있으므로 안전 조회)
        nl = NutritionLog.objects.filter(user=self.user, date=self.date).first()
        kcal_total = getattr(nl, "kcal_total", None)
        protein_total_g = getattr(nl, "protein_total_g", None)

        kcal_ratio = (kcal_total / self.kcal_target) if (kcal_total is not None and self.kcal_target) else None
        protein_ratio = (protein_total_g / self.protein_target_g) if (protein_total_g is not None and self.protein_target_g) else None

        # 운동 진행도 (세션 수 기반)
        gp = GoalProgress.objects.filter(user=self.user, goal=self.goal, date=self.date).first()
        completed_sessions = getattr(gp, "completed_sessions", None)
        workout_ratio = (
            (completed_sessions * 30) / self.workout_minutes_target
            if (completed_sessions is not None and self.workout_minutes_target)
            else None
        )

        parts = [r for r in (kcal_ratio, protein_ratio, workout_ratio) if r is not None]
        self.completion_score = round(sum(parts) / len(parts) * 100, 1) if parts else 0.0
        self.save(update_fields=["completion_score"])

    class Meta:
        verbose_name = "일일 목표"
        verbose_name_plural = "일일 목표 목록"
        unique_together = ("user", "goal", "date")  # 같은 날 같은 목표는 1개
        ordering = ["-date", "-id"]


class GoalProgress(models.Model):
    """실제 운동/체중 기록 (여기서는 세션 수 예시)"""
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
    completed_sessions = models.IntegerField(null=True, blank=True, verbose_name="완료 세션 수")

    def __str__(self) -> str:
        return f"{self.user_id} {self.date} - {self.goal.goal_type} ({self.completed_sessions or 0}회)"

    class Meta:
        verbose_name = "목표 진행도"
        verbose_name_plural = "목표 진행도 목록"
        unique_together = ("user", "goal", "date")
        ordering = ["-date", "-id"]


# ---------------- signals ---------------- #

@receiver([post_save, post_delete], sender=GoalProgress)
def update_goal_score(sender, instance, **kwargs):
    """운동 기록이 바뀌면 해당 날짜의 DailyGoal 점수 갱신"""
    dgs = DailyGoal.objects.filter(user=instance.user, goal=instance.goal, date=instance.date)
    for dg in dgs:
        dg.compute_score()


@receiver([post_save, post_delete], sender=NutritionLog)
def update_goal_score_from_log(sender, instance, **kwargs):
    """식사 합계가 바뀌면 해당 날짜의 DailyGoal 점수 갱신"""
    dgs = DailyGoal.objects.filter(user=instance.user, date=instance.date)
    for dg in dgs:
        dg.compute_score()
