from django.conf import settings
from django.db import models


class Feedback(models.Model):
    """사용자가 남기는 피드백 (AI 코칭 결과 포함)"""

    class FeedbackSource(models.TextChoices):
        USER = "user", "User"
        AI = "ai", "AI"
        HYBRID = "hybrid", "Hybrid"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedbacks",
        verbose_name="사용자",
    )
    workout_plan = models.ForeignKey(
        "tasks.WorkoutPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks",
        verbose_name="연계 운동 계획",
    )
    daily_report = models.ForeignKey(
        "feedbacks.DailyReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks",
        verbose_name="연계 리포트",
    )
    message = models.TextField(verbose_name="메시지")
    summary = models.TextField(blank=True, verbose_name="요약")
    recommended_action = models.TextField(blank=True, verbose_name="추천 조치")
    sentiment_score = models.FloatField(null=True, blank=True, verbose_name="감성 점수")
    # AI가 생성했는지 여부와 모델 정보, 프롬프트/응답을 기록해 코칭 이력을 추적
    source = models.CharField(max_length=10, choices=FeedbackSource.choices, default=FeedbackSource.USER, verbose_name="생성 출처")
    ai_model = models.CharField(max_length=100, blank=True, verbose_name="AI 모델")
    ai_version = models.CharField(max_length=50, blank=True, verbose_name="AI 버전")
    ai_prompt = models.TextField(blank=True, verbose_name="AI 프롬프트")
    ai_response = models.JSONField(null=True, blank=True, verbose_name="AI 응답")
    ai_confidence = models.FloatField(null=True, blank=True, verbose_name="AI 신뢰도")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")

    def __str__(self):
        return f"Feedback by {self.user} ({self.created_at.date()})"

    class Meta:
        verbose_name = "피드백"
        verbose_name_plural = "피드백 목록"


class DailyReport(models.Model):
    """사용자의 하루 건강 리포트"""

    class ReportSource(models.TextChoices):
        USER = "user", "User"
        DEVICE = "device", "Device"
        AI = "ai", "AI"

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
    date = models.DateField(verbose_name="날짜")
    summary = models.TextField(blank=True, verbose_name="요약")
    highlights = models.TextField(blank=True, verbose_name="하이라이트")
    challenges = models.TextField(blank=True, verbose_name="과제")
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, default="average", verbose_name="기분")
    score = models.FloatField(null=True, blank=True, verbose_name="AI 점수")
    # 리포트가 어느 채널에서 생성됐는지와 AI 응답 원문을 저장해 감사/재생성 지원
    source = models.CharField(max_length=10, choices=ReportSource.choices, default=ReportSource.USER, verbose_name="생성 출처")
    ai_model = models.CharField(max_length=100, blank=True, verbose_name="AI 모델")
    ai_response = models.JSONField(null=True, blank=True, verbose_name="AI 응답")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")

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
    daily_goal = models.ForeignKey(
        "goals.DailyGoal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="achievements",
        verbose_name="연계 일일 목표",
    )
    title = models.CharField(max_length=100, verbose_name="제목")
    description = models.TextField(blank=True, verbose_name="설명")
    badge = models.CharField(max_length=50, blank=True, verbose_name="배지")
    achieved_at = models.DateTimeField(auto_now_add=True, verbose_name="달성 시각")
    shared_to_ai = models.BooleanField(default=False, verbose_name="AI 공유 여부")

    def __str__(self):
        return f"{self.user} - {self.title}"

    class Meta:
        verbose_name = "달성도"
        verbose_name_plural = "달성도 목록"


class FeedbackGenerationLog(models.Model):
    """AI가 생성한 피드백 히스토리"""

    feedback = models.ForeignKey(
        Feedback,
        on_delete=models.CASCADE,
        related_name="generation_logs",
        verbose_name="피드백",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_generation_logs",
        verbose_name="요청자",
    )
    # 프롬프트/응답을 남겨 모델 동작을 검증하고 개선 데이터로 사용
    ai_model = models.CharField(max_length=100, verbose_name="AI 모델")
    ai_version = models.CharField(max_length=50, blank=True, verbose_name="AI 버전")
    prompt = models.TextField(verbose_name="프롬프트")
    response = models.JSONField(verbose_name="응답")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")

    def __str__(self):
        return f"{self.feedback} - {self.ai_model}"

    class Meta:
        verbose_name = "피드백 생성 로그"
        verbose_name_plural = "피드백 생성 로그 목록"
