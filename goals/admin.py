from django.contrib import admin
from .models import Goal,DailyGoal,GoalProgress,NutritionLog

# Register your models here.
admin.site.register(Goal) 
admin.site.register(DailyGoal) 
admin.site.register(GoalProgress) 
admin.site.register(NutritionLog) 
