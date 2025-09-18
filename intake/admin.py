from django.contrib import admin
from .models import Food, Meal, MealItem, NutritionLog  

@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ("id", "name")

@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "log_date", "meal_type")

@admin.register(MealItem)
class MealItemAdmin(admin.ModelAdmin):
    list_display = ("id", "meal", "food", "grams", "name")

@admin.register(NutritionLog)                           
class NutritionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "date", "kcal_total", "protein_total_g", "carb_total_g", "fat_total_g")
