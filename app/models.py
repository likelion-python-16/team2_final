from django.db import models

class User(models.Model):
    email = models.CharField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    nickname = models.CharField(max_length=50, null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    height_cm = models.IntegerField(null=True, blank=True)
    weight_kg = models.IntegerField(null=True, blank=True)          # int
    activity_level = models.IntegerField(null=True, blank=True)      # int(1/2/3 등)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email


class Goal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    goal_type = models.BooleanField(default=True)                    # boolean
    target_weight_kg = models.IntegerField(null=True, blank=True)    # int
    weekly_sessions = models.IntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'goals'

    def __str__(self):
        return f"Goal(u={self.user_id}, type={self.goal_type})"


class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    goal = models.ForeignKey(Goal, on_delete=models.SET_NULL, null=True, blank=True)
    task_date = models.DateField()
    category = models.CharField(max_length=20)                       # workout / meal / lifestyle
    title = models.CharField(max_length=120)
    details_json = models.JSONField(default=dict, blank=True)        # 가변 필드
    status = models.CharField(max_length=20, default='pending')      # pending / done / skipped
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tasks'
        indexes = [
            models.Index(fields=['user', 'task_date']),
            models.Index(fields=['user', 'task_date', 'category']),
        ]

    def __str__(self):
        return f"[{self.task_date}] {self.title} ({self.category}/{self.status})"


class Food(models.Model):
    name_ko = models.CharField(max_length=200)
    brand = models.CharField(max_length=120, null=True, blank=True)
    serving_desc = models.CharField(max_length=120, null=True, blank=True)
    serving_g = models.IntegerField(null=True, blank=True)
    kcal = models.IntegerField(null=True, blank=True)
    protein_g = models.IntegerField(null=True, blank=True)
    carbs_g = models.IntegerField(null=True, blank=True)
    fat_g = models.IntegerField(null=True, blank=True)
    sodium_mg = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'foods'

    def __str__(self):
        return self.name_ko


class Intake(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    log_date = models.DateField()
    meal_type = models.CharField(max_length=20)                      # 팀 합의 전 임시 문자열 (아침/점심/저녁/간식 등)
    food = models.ForeignKey(Food, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'intake'
        indexes = [models.Index(fields=['user', 'log_date'])]

    def __str__(self):
        return f"Intake(u={self.user_id}, {self.log_date}, {self.meal_type})"


class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ref_date = models.DateField()
    scope = models.CharField(max_length=20)                          # daily / weekly
    topic = models.CharField(max_length=30)                          # nutrition / workout / adherence
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'feedbacks'
        indexes = [models.Index(fields=['user', 'ref_date', 'scope'])]

    def __str__(self):
        return f"Feedback(u={self.user_id}, {self.ref_date}, {self.scope}/{self.topic})"
