from django.contrib import admin
from .models import TaskItem,WorkoutLog,WorkoutPlan,Exercise

# Register your models here.
admin.site.register(TaskItem)
admin.site.register(WorkoutLog)
admin.site.register(WorkoutPlan)
admin.site.register(Exercise)