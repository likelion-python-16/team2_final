from django.db import models

class Feedback(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="feedbacks")
    ref_date = models.DateField()
    scope = models.CharField(max_length=20)     # 예: "diet","workout"
    topic = models.CharField(max_length=30)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.scope}:{self.topic}"
