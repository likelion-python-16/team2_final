from django.db import models
from django.conf import settings


class Feedback(models.Model):
    """사용자가 남기는 피드백"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedbacks")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback by {self.user} ({self.created_at.date()})"


class DailyReport(models.Model):
    """사용자의 하루 건강 리포트"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_reports")
    date = models.DateField()
    summary = models.TextField(blank=True)
    mood = models.CharField(max_length=20, choices=[("good", "Good"), ("average", "Average"), ("bad", "Bad")], default="average")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.date}"


class Achievement(models.Model):
    """달성한 업적"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements")
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    achieved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.title}"
