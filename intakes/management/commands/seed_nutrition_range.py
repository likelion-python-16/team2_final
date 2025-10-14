# intakes/management/commands/seed_nutrition_range.py
import random
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from users.models import CustomUser
from intakes.models import Food, Meal, MealItem

MEAL_TYPES = ("아침", "점심", "저녁", "간식")


def parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        raise CommandError(f"--start/--end 는 YYYY-MM-DD 형식이어야 합니다: {s}")


class Command(BaseCommand):
    help = "지정 기간 동안 사용자(또는 전체)에 대해 Meal/MealItem을 생성하여 NutritionLog를 채웁니다."

    def add_arguments(self, parser):
        parser.add_argument("--start", required=True, help="시작일 (YYYY-MM-DD)")
        parser.add_argument("--end", required=True, help="종료일(포함, YYYY-MM-DD)")
        parser.add_argument("--only-user", type=str, default=None, help="특정 username만 대상")
        parser.add_argument("--per-day-min", type=int, default=2, help="하루 최소 끼니 수")
        parser.add_argument("--per-day-max", type=int, default=3, help="하루 최대 끼니 수")
        parser.add_argument("--items-min", type=int, default=1, help="끼니당 최소 항목")
        parser.add_argument("--items-max", type=int, default=3, help="끼니당 최대 항목")
        parser.add_argument("--skip-weekends", action="store_true", help="주말 건너뛰기")
        parser.add_argument("--seed", type=int, default=None, help="난수 시드(재현성)")
        parser.add_argument("--max-foods", type=int, default=5000, help="Food 샘플 상한")

        # 추가 옵션들
        parser.add_argument("--max-items-per-meal", type=int, default=3,
                            help="끼니(Meal)당 최대 아이템 개수(오늘 제외 가능)")
        parser.add_argument("--max-items-per-day", type=int, default=9,
                            help="하루 전체 최대 아이템 개수(오늘 제외 가능)")
        parser.add_argument("--idempotent", action="store_true",
                            help="해당 날짜에 이미 데이터가 있으면 그 날짜는 건너뜀(사용자 단위)")
        parser.add_argument("--allow-past-append", action="store_true",
                            help="과거 날짜에도 추가 누적을 허용(기본은 과거 잠금)")
        parser.add_argument("--today-unlimited", action="store_true",
                            help="오늘 날짜에 한해 per-day/per-meal 상한 미적용")

    @transaction.atomic
    def handle(self, *args, **opt):
        start = parse_date(opt["start"])
        end = parse_date(opt["end"])
        if start > end:
            raise CommandError("start는 end보다 이전이어야 합니다.")
        if opt["seed"] is not None:
            random.seed(opt["seed"])

        foods = list(Food.objects.all().only("id", "kcal_per_100g")[:opt["max_foods"]])
        if not foods:
            self.stdout.write(self.style.ERROR("Food 데이터가 없습니다. CSV 먼저 적재하세요."))
            return

        users = list(CustomUser.objects.filter(username=opt["only_user"])) if opt["only_user"] \
            else list(CustomUser.objects.all())
        if not users:
            self.stdout.write(self.style.ERROR("대상 사용자 없음"))
            return

        created_meals = 0
        created_items = 0

        cur = start
        today = timezone.now().date()

        while cur <= end:
            # 주말 스킵
            if opt["skip_weekends"] and cur.weekday() >= 5:
                cur += timedelta(days=1)
                continue

            is_today = (cur == today)

            for user in users:
                # 과거 잠금: 과거 날짜에 해당 사용자 데이터가 이미 있으면 스킵
                if not opt["allow_past_append"] and cur < today:
                    if MealItem.objects.filter(meal__user=user, meal__log_date=cur).exists():
                        continue

                # 멱등 모드: 해당 날짜에 사용자 데이터가 이미 있으면 그 날짜 전체 스킵
                if opt["idempotent"]:
                    if MealItem.objects.filter(meal__user=user, meal__log_date=cur).exists():
                        continue

                # 하루 끼니 수/종류 결정(사용자 단위)
                per_day = random.randint(opt["per_day_min"], opt["per_day_max"])
                used_types = random.sample(MEAL_TYPES, k=min(per_day, len(MEAL_TYPES)))

                # 오늘이 아니면 per-day 상한 체크
                if not (opt["today_unlimited"] and is_today):
                    day_total = MealItem.objects.filter(meal__user=user, meal__log_date=cur).count()
                    remaining_day_room = max(0, opt["max_items_per_day"] - day_total)
                    if remaining_day_room <= 0:
                        continue
                else:
                    # 오늘은 무제한 모드
                    remaining_day_room = None  # 의미 없음

                for mt in used_types:
                    # (user, date, type) 중복 안전: 있으면 재사용
                    qs = Meal.objects.filter(user=user, log_date=cur, meal_type=mt).order_by("id")
                    if qs.exists():
                        meal = qs.first()
                    else:
                        meal = Meal.objects.create(user=user, log_date=cur, meal_type=mt)
                        created_meals += 1

                    # 끼니별 상한 계산 (오늘은 제외 가능)
                    if not (opt["today_unlimited"] and is_today):
                        meal_items_now = MealItem.objects.filter(meal=meal).count()
                        meal_room = max(0, opt["max_items_per_meal"] - meal_items_now)
                        if meal_room <= 0:
                            continue
                    else:
                        meal_room = None  # 의미 없음

                    # 생성할 아이템 수 결정 + 남은 데이/끼니 상한 반영
                    raw_items = random.randint(opt["items_min"], opt["items_max"])
                    if (opt["today_unlimited"] and is_today):
                        n_items = raw_items
                    else:
                        n_items = raw_items
                        if meal_room is not None:
                            n_items = min(n_items, meal_room)
                        if remaining_day_room is not None:
                            n_items = min(n_items, remaining_day_room)
                        if n_items <= 0:
                            continue

                    # 실제 생성
                    for _ in range(n_items):
                        food = random.choice(foods)
                        # 끼니/요일에 따라 무게 편차 (아침 작게, 주말 가산)
                        base = {"아침": 120, "점심": 220, "저녁": 250, "간식": 80}[mt]
                        jitter = random.randint(-40, 60)
                        weekend_boost = 30 if cur.weekday() >= 5 else 0
                        grams = max(40, base + jitter + weekend_boost)

                        MealItem.objects.create(meal=meal, food=food, grams=grams)
                        created_items += 1

                        # 오늘이 아니면 상한 카운터 감소
                        if not (opt["today_unlimited"] and is_today):
                            if remaining_day_room is not None:
                                remaining_day_room -= 1
                                if remaining_day_room <= 0:
                                    break
                    # 데이 상한 다 썼으면 끼니 루프 중단
                    if not (opt["today_unlimited"] and is_today):
                        if remaining_day_room is not None and remaining_day_room <= 0:
                            break

            cur += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f"완료! 생성된 Meal={created_meals}, MealItem={created_items} (signals로 NutritionLog 자동 갱신)"
        ))
