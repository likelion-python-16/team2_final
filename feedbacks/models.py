from django.db import models
from django.conf import settings


class Feedback(models.Model):
    """사용자가 남기는 피드백 (AI 코칭 결과 포함)"""

    class FeedbackSource(models.TextChoices):
        USER = "user", "User"
        AI = "ai", "AI"
        HYBRID = "hybrid", "Hybrid"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedbacks")
    workout_plan = models.ForeignKey("tasks.WorkoutPlan", on_delete=models.SET_NULL, null=True, blank=True, related_name="feedbacks")
    daily_report = models.ForeignKey("feedbacks.DailyReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="feedbacks")
    message = models.TextField()
    summary = models.TextField(blank=True)
    recommended_action = models.TextField(blank=True)
    sentiment_score = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=FeedbackSource.choices, default=FeedbackSource.USER)
    ai_model = models.CharField(max_length=100, blank=True)
    ai_version = models.CharField(max_length=50, blank=True)
    ai_prompt = models.TextField(blank=True)
    ai_response = models.JSONField(null=True, blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Feedback by {self.user} ({self.created_at.date()})"


class DailyReport(models.Model):
    """사용자의 하루 건강 리포트"""

    class ReportSource(models.TextChoices):
        USER = "user", "User"
        DEVICE = "device", "Device"
        AI = "ai", "AI"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_reports")
    date = models.DateField()
    summary = models.TextField(blank=True)
    highlights = models.TextField(blank=True)
    challenges = models.TextField(blank=True)
    mood = models.CharField(max_length=20, choices=[("good", "Good"), ("average", "Average"), ("bad", "Bad")], default="average")
    score = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=ReportSource.choices, default=ReportSource.USER)
    ai_model = models.CharField(max_length=100, blank=True)
    ai_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.date}"


class Achievement(models.Model):
    """달성한 업적"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements")
    daily_goal = models.ForeignKey("goals.DailyGoal", on_delete=models.SET_NULL, null=True, blank=True, related_name="achievements")
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    badge = models.CharField(max_length=50, blank=True)
    achieved_at = models.DateTimeField(auto_now_add=True)
    shared_to_ai = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.title}"


class FeedbackGenerationLog(models.Model):
    """AI가 생성한 피드백의 히스토리"""

    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name="generation_logs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="feedback_generation_logs")
    ai_model = models.CharField(max_length=100)
    ai_version = models.CharField(max_length=50, blank=True)
    prompt = models.TextField()
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.feedback} - {self.ai_model}"
