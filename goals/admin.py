from django.contrib import admin
from .models import Goal, DailyGoal, GoalProgress

@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "goal_type")


@admin.register(DailyGoal)
class DailyGoalAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "goal", "date", "completion_score")
    list_filter = ("date",)  

@admin.register(GoalProgress)
class GoalProgressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "goal", "date", "completed_sessions")
    list_filter = ("date",)  #
