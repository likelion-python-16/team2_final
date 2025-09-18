from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

class Food(models.Model):
    # 음식 사전
    name = models.CharField(max_length=120, unique=True)
    kcal_per_100g = models.FloatField()
    protein_g_per_100g = models.FloatField()
    carb_g_per_100g = models.FloatField()
    fat_g_per_100g = models.FloatField()

    def __str__(self):
        return self.name

class Meal(models.Model):
    # 하루의 한 끼
    MEAL_TYPES = (("아침","아침"),("점심","점심"),("저녁","저녁"),("간식","간식"))
    user = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, related_name="meals")
    log_date = models.DateField()
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPES)

    def __str__(self):
        return f"{self.user_id} {self.log_date} {self.meal_type}"

class MealItem(models.Model):
    # 식사 안의 세부 항목
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.SET_NULL, null=True, blank=True)
    grams = models.FloatField(null=True, blank=True)
    name = models.CharField(max_length=120, null=True, blank=True)
    kcal = models.FloatField(null=True, blank=True)
    protein_g = models.FloatField(null=True, blank=True)
    carb_g = models.FloatField(null=True, blank=True)
    fat_g = models.FloatField(null=True, blank=True)

    def resolved_nutrients(self):
        # food + grams 있으면 DB값을 활용, 없으면 자유입력 사용
        if self.food and self.grams:
            f = self.grams / 100.0
            return {
                "kcal": self.food.kcal_per_100g * f,
                "protein_g": self.food.protein_g_per_100g * f,
                "carb_g": self.food.carb_g_per_100g * f,
                "fat_g": self.food.fat_g_per_100g * f,
            }
        return {
            "kcal": self.kcal or 0,
            "protein_g": self.protein_g or 0,
            "carb_g": self.carb_g or 0,
            "fat_g": self.fat_g or 0,
        }

class NutritionLog(models.Model):
    # 하루 총합 캐시
    user = models.ForeignKey("users.CustomUser", on_delete=models.CASCADE, related_name="nutrition_logs")
    date = models.DateField()
    kcal_total = models.FloatField(default=0)
    protein_total_g = models.FloatField(default=0)
    carb_total_g = models.FloatField(default=0)
    fat_total_g = models.FloatField(default=0)

    class Meta:
        unique_together = ("user", "date")

    def recalc(self):
        # 해당 날짜의 MealItem 합산
        items = MealItem.objects.filter(meal__user=self.user, meal__log_date=self.date)
        self.kcal_total = sum(i.resolved_nutrients()["kcal"] for i in items)
        self.protein_total_g = sum(i.resolved_nutrients()["protein_g"] for i in items)
        self.carb_total_g = sum(i.resolved_nutrients()["carb_g"] for i in items)
        self.fat_total_g = sum(i.resolved_nutrients()["fat_g"] for i in items)
        self.save()

# ---------------- signals ---------------- #
@receiver([post_save, post_delete], sender=MealItem)
@receiver([post_save, post_delete], sender=Meal)
def update_nutrition_log(sender, instance, **kwargs):
    # Meal/MealItem이 바뀌면 NutritionLog도 갱신
    user = instance.user if isinstance(instance, Meal) else instance.meal.user
    date = instance.log_date if isinstance(instance, Meal) else instance.meal.log_date
    log, _ = NutritionLog.objects.get_or_create(user=user, date=date)
    log.recalc()