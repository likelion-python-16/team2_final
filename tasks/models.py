from django.db import models

class Task(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="tasks")
    goal = models.ForeignKey("goals.Goal", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    task_date = models.DateField()
    category = models.CharField(max_length=20)
    title = models.CharField(max_length=120)
    details_json = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")  # 예: pending/done/cancel
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title