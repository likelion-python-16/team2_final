"""
intakes/signals.py

MealItem이 추가/수정/삭제될 때, 같은 유저/날짜의 NutritionLog 합계를
자동으로 재계산하여 저장한다.

핵심 아이디어
- source of truth는 MealItem
- NutritionLog는 '하루 합계 캐시'(읽기 전용 느낌)
- post_save/post_delete 훅으로 항상 일관성 유지
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum

from .models import MealItem, NutritionLog


def recalc_nutritionlog(user, log_date):
    """
    특정 사용자/날짜에 대한 MealItem들을 모두 집계해서
    NutritionLog에 반영한다.
    """
    # MealItem ←(FK)− Meal(log_date, user)
    agg = MealItem.objects.filter(
        meal__user=user,
        meal__log_date=log_date,
    ).aggregate(
        kcal=Sum("kcal"),
        protein=Sum("protein_g"),
        fat=Sum("fat_g"),
        carb=Sum("carb_g"),
    )

    # 없으면 생성(get_or_create), 있으면 업데이트
    log, _ = NutritionLog.objects.get_or_create(user=user, date=log_date)
    log.kcal_total = agg["kcal"] or 0
    log.protein_total_g = agg["protein"] or 0
    log.fat_total_g = agg["fat"] or 0
    log.carb_total_g = agg["carb"] or 0
    log.save()


@receiver(post_save, sender=MealItem)
def mealitem_saved(sender, instance, **kwargs):
    """
    MealItem 생성/수정 후 NutritionLog 재계산.
    """
    user = instance.meal.user
    log_date = instance.meal.log_date
    recalc_nutritionlog(user, log_date)


@receiver(post_delete, sender=MealItem)
def mealitem_deleted(sender, instance, **kwargs):
    """
    MealItem 삭제 후 NutritionLog 재계산.
    """
    user = instance.meal.user
    log_date = instance.meal.log_date
    recalc_nutritionlog(user, log_date)
