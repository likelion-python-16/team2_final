from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone


class Food(models.Model):
    # 음식 사전
    name = models.CharField(max_length=120, unique=True, verbose_name="이름")
    kcal_per_100g = models.FloatField(verbose_name="열량(kcal/100g)")
    protein_g_per_100g = models.FloatField(verbose_name="단백질(g/100g)")
    carb_g_per_100g = models.FloatField(verbose_name="탄수화물(g/100g)")
    fat_g_per_100g = models.FloatField(verbose_name="지방(g/100g)")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "음식"
        verbose_name_plural = "음식 목록"


class Meal(models.Model):
    # 하루의 한 끼
    MEAL_TYPES = (("아침", "아침"), ("점심", "점심"), ("저녁", "저녁"), ("간식", "간식"))

    user = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="meals",
        verbose_name="사용자",
    )
    log_date = models.DateField(verbose_name="기록 날짜")
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPES, verbose_name="식사 유형")

    def __str__(self):
        return f"{self.user_id} {self.log_date} {self.meal_type}"

    class Meta:
        verbose_name = "식사"
        verbose_name_plural = "식사 목록"


class MealItem(models.Model):
    # 식사 안의 세부 항목
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name="items", verbose_name="식사")
    food = models.ForeignKey(Food, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="음식")
    grams = models.FloatField(null=True, blank=True, verbose_name="중량(g)")
    name = models.CharField(max_length=120, null=True, blank=True, verbose_name="이름")
    kcal = models.FloatField(null=True, blank=True, verbose_name="열량(kcal)")
    protein_g = models.FloatField(null=True, blank=True, verbose_name="단백질(g)")
    carb_g = models.FloatField(null=True, blank=True, verbose_name="탄수화물(g)")
    fat_g = models.FloatField(null=True, blank=True, verbose_name="지방(g)")
    photo = models.ImageField(upload_to="meals/%Y/%m/%d/", null=True, blank=True)
    serving_g = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=20, default='csv')  # 'db'|'csv'|'csv_estimate'|'default'
    ai_label = models.CharField(max_length=200, null=True, blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        base = self.food.name if self.food else (self.name or "항목")
        return f"{base} - {self.grams or 0:g}g"

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

    class Meta:
        verbose_name = "식사 항목"
        verbose_name_plural = "식사 항목 목록"


class NutritionLog(models.Model):
    # 하루 총합 캐시
    user = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.CASCADE,
        related_name="nutrition_logs",
        verbose_name="사용자",
    )
    date = models.DateField(verbose_name="날짜")
    kcal_total = models.FloatField(default=0, verbose_name="총 열량(kcal)")
    protein_total_g = models.FloatField(default=0, verbose_name="총 단백질(g)")
    carb_total_g = models.FloatField(default=0, verbose_name="총 탄수화물(g)")
    fat_total_g = models.FloatField(default=0, verbose_name="총 지방(g)")

    class Meta:
        unique_together = ("user", "date")
        verbose_name = "영양 기록"
        verbose_name_plural = "영양 기록 목록"

    def __str__(self):
        return f"{self.user_id} {self.date}"

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
