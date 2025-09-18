from django.contrib import admin
from .models import Task

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "goal", "task_date", "category", "title", "status", "created_at")
    list_filter = ("category", "status")