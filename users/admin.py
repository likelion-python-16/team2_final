from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "nickname", "gender", "height_cm", "weight_kg", "activity_level", "created_at")
    search_fields = ("email", "nickname")