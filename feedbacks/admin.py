from django.contrib import admin
from .models import Feedback

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "ref_date", "scope", "topic", "created_at")
    list_filter = ("scope",)