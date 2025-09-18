from django.contrib import admin
from .models import Food,Meal,MealItem,NutritionLog

# Register your models here.
admin.site.register(Food)
admin.site.register(Meal)
admin.site.register(MealItem)
admin.site.register(NutritionLog)
