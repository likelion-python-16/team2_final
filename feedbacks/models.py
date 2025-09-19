from django.db import models
from django.conf import settings


class Feedback(models.Model):
    """사용자가 남기는 피드백"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedbacks",
        verbose_name="사용자",
    )
    message = models.TextField(verbose_name="메시지")  # 사용자가 입력하는 피드백 메시지
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")  # 작성 시간

    def __str__(self):
        return f"Feedback by {self.user} ({self.created_at.date()})"

    class Meta:
        verbose_name = "피드백"
        verbose_name_plural = "피드백 목록"


class DailyReport(models.Model):
    """사용자의 하루 건강 리포트"""
    MOOD_CHOICES = (
        ("good", "좋음"),
        ("average", "보통"),
        ("bad", "나쁨"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_reports",
        verbose_name="사용자",
    )
    date = models.DateField(verbose_name="날짜")  # 리포트 날짜
    summary = models.TextField(blank=True, verbose_name="요약")  # 하루 요약 내용
    mood = models.CharField(
        max_length=20,
        choices=MOOD_CHOICES,
        default="average",
        verbose_name="기분",  # 하루 기분 상태
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")  # 작성 시간

    def __str__(self):
        return f"{self.user} - {self.date}"

    class Meta:
        verbose_name = "일간 리포트"
        verbose_name_plural = "일간 리포트 목록"


class Achievement(models.Model):
    """달성한 업적"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
        verbose_name="사용자",
    )
    title = models.CharField(max_length=100, verbose_name="제목")  # 업적 이름
    description = models.TextField(blank=True, verbose_name="설명")  # 업적 설명
    achieved_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="달성 시각",  # 달성한 시간
    )

    def __str__(self):
        return f"{self.user} - {self.title}"

    class Meta:
        verbose_name = "달성도"
        verbose_name_plural = "달성도 목록"
