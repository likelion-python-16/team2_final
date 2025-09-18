from django.db import models

class User(models.Model):
    email = models.CharField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    nickname = models.CharField(max_length=50)
    gender = models.CharField(max_length=10)
    height_cm = models.IntegerField()
    weight_kg = models.IntegerField()
    activity_level = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nickname or self.email
