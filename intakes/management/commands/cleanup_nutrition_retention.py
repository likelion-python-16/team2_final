from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.db.models.signals import post_save, post_delete

from intakes.models import Meal, MealItem, NutritionLog, update_nutrition_log
from users.models import CustomUser

class Command(BaseCommand):
    help = "Nutrition 데이터 보존정책: 최근 N일만 남기고 과거 데이터 삭제"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=60, help="최근 며칠을 보존할지 (기본 60)")
        parser.add_argument("--only-user", type=str, default=None, help="특정 사용자만")
        parser.add_argument("--dry-run", action="store_true", help="건수만 출력(삭제 안 함)")

    def handle(self, *args, **opt):
        days = opt["days"]
        if days <= 0:
            raise CommandError("--days 는 양수여야 합니다.")
        cutoff = timezone.now().date() - timedelta(days=days)
        self.stdout.write(self.style.NOTICE(f"보존 기준(포함 X): {cutoff} 이전 데이터 삭제"))

        meals_qs = Meal.objects.filter(log_date__lt=cutoff)
        items_qs = MealItem.objects.filter(meal__log_date__lt=cutoff)
        logs_qs = NutritionLog.objects.filter(date__lt=cutoff)

        if opt["only_user"]:
            users = CustomUser.objects.filter(username=opt["only-user"])
            if not users.exists():
                raise CommandError(f"username={opt['only-user']} 없음")
            meals_qs = meals_qs.filter(user__in=users)
            items_qs = items_qs.filter(meal__user__in=users)
            logs_qs = logs_qs.filter(user__in=users)

        meals_cnt = meals_qs.count()
        items_cnt = items_qs.count()
        logs_cnt  = logs_qs.count()
        self.stdout.write(f"[대상] MealItem={items_cnt}, Meal={meals_cnt}, NutritionLog={logs_cnt}")

        if opt["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: 삭제하지 않았습니다."))
            return

        # 대량 삭제 시 성능 위해 시그널 잠시 해제
        post_save.disconnect(update_nutrition_log, sender=MealItem)
        post_delete.disconnect(update_nutrition_log, sender=MealItem)
        post_save.disconnect(update_nutrition_log, sender=Meal)
        post_delete.disconnect(update_nutrition_log, sender=Meal)

        try:
            with transaction.atomic():
                logs_deleted  = logs_qs.delete()[0]
                items_deleted = items_qs.delete()[0]
                meals_deleted = meals_qs.delete()[0]
        finally:
            # 시그널 복구
            post_save.connect(update_nutrition_log, sender=MealItem)
            post_delete.connect(update_nutrition_log, sender=MealItem)
            post_save.connect(update_nutrition_log, sender=Meal)
            post_delete.connect(update_nutrition_log, sender=Meal)

        self.stdout.write(self.style.SUCCESS(
            f"삭제 완료: NutritionLog={logs_deleted}, MealItem={items_deleted}, Meal={meals_deleted} "
            f"(최근 {days}일 보존)"
        ))
