# intakes/management/commands/seed_nutrition_logs.py
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from users.models import CustomUser
from intakes.models import Food, Meal, MealItem


MEAL_TYPES = ("아침", "점심", "저녁", "간식")


class Command(BaseCommand):
    help = "최근 N일치 더미 Meal/MealItem을 생성해 NutritionLog를 자동으로 채웁니다."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="과거 며칠치 생성할지 (기본 30)")
        parser.add_argument("--per-day-min", type=int, default=2, help="하루 최소 끼니 수(기본 2)")
        parser.add_argument("--per-day-max", type=int, default=3, help="하루 최대 끼니 수(기본 3)")
        parser.add_argument("--items-min", type=int, default=1, help="끼니당 최소 항목(기본 1)")
        parser.add_argument("--items-max", type=int, default=3, help="끼니당 최대 항목(기본 3)")
        parser.add_argument("--only-user", type=str, default=None, help="특정 username만 대상")
        parser.add_argument("--seed", type=int, default=None, help="난수 시드 고정(재현성)")

    @transaction.atomic
    def handle(self, *args, **opts):
        days = opts["days"]
        per_day_min = opts["per_day_min"]
        per_day_max = opts["per_day_max"]
        items_min = opts["items_min"]
        items_max = opts["items_max"]
        only_user = opts["only_user"]
        seed = opts["seed"]

        if seed is not None:
            random.seed(seed)

        foods = list(Food.objects.all())
        if not foods:
            self.stdout.write(self.style.ERROR("Food 데이터가 없습니다. 먼저 CSV를 적재하세요."))
            return

        if only_user:
            users = list(CustomUser.objects.filter(username=only_user))
        else:
            users = list(CustomUser.objects.all())

        if not users:
            self.stdout.write(self.style.ERROR("대상 사용자(들)가 없습니다."))
            return

        today = timezone.now().date()
        created_meals = 0
        created_items = 0

        for user in users:
            for d in range(days):
                log_date = today - timedelta(days=d + 1)  # 어제부터 과거로

                # 하루 끼니 수
                n_meals = random.randint(per_day_min, per_day_max)
                used_types = random.sample(MEAL_TYPES, k=min(n_meals, len(MEAL_TYPES)))

                for meal_type in used_types:
                    # ✅ 중복이 있어도 안전: 첫 번째 것을 재사용하고, 없으면 생성
                    meal_qs = Meal.objects.filter(user=user, log_date=log_date, meal_type=meal_type).order_by("id")
                    if meal_qs.exists():
                        meal = meal_qs.first()
                        created = False
                    else:
                        meal = Meal.objects.create(user=user, log_date=log_date, meal_type=meal_type)
                        created = True
                    if created:
                        created_meals += 1

                    # 끼니 내 항목 수
                    n_items = random.randint(items_min, items_max)
                    for _ in range(n_items):
                        food = random.choice(foods)
                        grams = random.randint(50, 300)  # 50~300 g
                        # food+grams 조합이면 signals 통해 NutritionLog 자동 반영
                        MealItem.objects.create(
                            meal=meal,
                            food=food,
                            grams=grams,
                        )
                        created_items += 1

        self.stdout.write(self.style.SUCCESS(
            f"완료! 생성된 Meal={created_meals}, MealItem={created_items} "
            f"(signals로 NutritionLog 자동 갱신)"
        ))
