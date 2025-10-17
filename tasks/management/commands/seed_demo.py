# tasks/management/commands/seed_demo.py
from __future__ import annotations

import json
import random
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, List, Dict, TYPE_CHECKING

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.apps import apps
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

# ----- 정적 분석 전용 타입 임포트 (런타임에 실행되지 않음) -----
if TYPE_CHECKING:
    from tasks.models import WorkoutPlan as WP, TaskItem as TI, Exercise as EX

# ----- 런타임 모델 로딩 -----
User = get_user_model()
WorkoutPlan = apps.get_model('tasks', 'WorkoutPlan')
TaskItem = apps.get_model('tasks', 'TaskItem')
Exercise = apps.get_model('tasks', 'Exercise')


def aware(dt: datetime) -> datetime:
    """naive datetime을 현재 TZ로 aware 처리"""
    tz = timezone.get_current_timezone()
    return timezone.make_aware(dt, tz) if timezone.is_naive(dt) else dt


def parse_date(s: str) -> date:
    y, m, d = map(int, s.split("-"))
    return date(y, m, d)


def strip_json_comments(s: str) -> str:
    """//, /**/ 주석 & 일부 trailing comma 제거(베스트에포트)"""
    s = re.sub(r"//.*?$", "", s, flags=re.MULTILINE)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s


class Command(BaseCommand):
    help = "Seed demo data from exercises.json over a date range (weekdays only)."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help="username (e.g., swj6824)")
        parser.add_argument("--start", default="2025-08-20", help="start date YYYY-MM-DD")
        parser.add_argument("--end", default="2025-10-17", help="end date YYYY-MM-DD")

        parser.add_argument("--per_min", dest="per_min", type=int, default=3,
                            help="min tasks per weekday")
        parser.add_argument("--per_max", dest="per_max", type=int, default=5,
                            help="max tasks per weekday")

        parser.add_argument("--ex_file", dest="ex_file",
                            default="static/data/exercises.json",
                            help="path to exercises.json (fixture or plain list)")

        parser.add_argument("--reset_demo", dest="reset_demo", action="store_true",
                            help="delete existing demo seed first "
                                 "(plans titled 'YYYY-MM-DD 플랜' or items with ai_metadata.seed_date)")

        parser.add_argument("--dry_run", dest="dry_run", action="store_true",
                            help="print plan only (no DB write)")

    # ---------- exercises.json 유연 파서 ----------
    def _load_exercises(self, ex_path: Path) -> List[Dict[str, Any]]:
        if not ex_path.exists():
            raise CommandError(f"exercises.json not found: {ex_path}")

        text = strip_json_comments(ex_path.read_text(encoding="utf-8"))
        try:
            raw = json.loads(text)
        except Exception as e:
            raise CommandError(f"invalid JSON in {ex_path}: {e}")

        data: List[Dict[str, Any]] = []
        if isinstance(raw, list):
            # Django fixture 스타일: [{"model":"tasks.exercise","pk":..,"fields":{...}}, ...]
            if raw and isinstance(raw[0], dict) and "fields" in raw[0]:
                for it in raw:
                    if not isinstance(it, dict):
                        continue
                    model = str(it.get("model", ""))
                    # 다른 모델이 섞여 있을 수 있으니 exercise만 취함
                    if model and "exercise" not in model.lower():
                        continue
                    fields = it.get("fields")
                    if isinstance(fields, dict):
                        data.append(fields)
            else:
                # 일반 리스트 [{name/target/...}, ...]
                data = [x for x in raw if isinstance(x, dict)]
        elif isinstance(raw, dict):
            # {"exercises":[...]} 혹은 섹션별 리스트를 합침
            if "exercises" in raw and isinstance(raw["exercises"], list):
                data = [x for x in raw["exercises"] if isinstance(x, dict)]
            else:
                flat = []
                for v in raw.values():
                    if isinstance(v, list):
                        flat.extend([x for x in v if isinstance(x, dict)])
                data = flat

        if not data:
            raise CommandError("exercises.json must be a non-empty list (or dict containing lists)")

        def norm(e: Dict[str, Any]) -> Dict[str, Any]:
            name = (e.get("name") or e.get("title") or "").strip()
            target = (e.get("target") or e.get("muscle") or e.get("group") or "general")
            desc = (e.get("description") or e.get("desc") or "demo exercise")
            kcal = (
                e.get("kcal_burned_per_min")
                # fixture에서 fields에 이렇게 들어있지 않으면 아래 키들도 시도
                or e.get("kcal_per_min")
                or e.get("kcalPerMin")
                or e.get("kcal")
                or 5.0
            )
            try:
                kcal = float(kcal)
            except Exception:
                kcal = 5.0
            return {
                "name": name,
                "target": str(target),
                "description": str(desc),
                "kcal_burned_per_min": kcal,
            }

        normed: List[Dict[str, Any]] = []
        for e in data:
            if not isinstance(e, dict):
                continue
            ee = norm(e)
            if ee["name"]:
                normed.append(ee)

        if not normed:
            raise CommandError("No valid exercises loaded.")
        return normed

    def handle(self, *args, **opts):
        username = opts["user"]
        start_d = parse_date(opts["start"])
        end_d = parse_date(opts["end"])
        per_min = max(1, opts["per_min"])
        per_max = max(per_min, opts["per_max"])
        ex_path = Path(opts["ex_file"]).resolve()
        reset = opts["reset_demo"]
        dry_run = opts["dry_run"]

        # 사용자 확인
        try:
            u = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User not found: {username}")

        # exercises 로드
        normed_exercises = self._load_exercises(ex_path)

        # 기존 데모 데이터 제거(옵션)
        if reset:
            with transaction.atomic():
                ti_qs = TaskItem.objects.filter(
                    Q(ai_metadata__has_key="seed_date") |
                    Q(workout_plan__title__regex=r'^\d{4}-\d{2}-\d{2} 플랜$')
                )
                ti_count = ti_qs.count()
                ti_qs.delete()

                wp_qs = WorkoutPlan.objects.filter(title__regex=r'^\d{4}-\d{2}-\d{2} 플랜$')
                wp_count = wp_qs.count()
                wp_qs.delete()

                self.stdout.write(self.style.WARNING(
                    f"[RESET] TaskItem: {ti_count}, WorkoutPlan: {wp_count} deleted"
                ))

        # Exercise 업서트
        ex_objs: List[Exercise] = []
        with transaction.atomic():
            for e in normed_exercises:
                obj, _ = Exercise.objects.get_or_create(
                    name=e["name"],
                    defaults={
                        "target": e["target"],
                        "description": e["description"],
                        "kcal_burned_per_min": e["kcal_burned_per_min"],
                    },
                )
                updated = False
                for k in ("target", "description", "kcal_burned_per_min"):
                    if getattr(obj, k) != e[k]:
                        setattr(obj, k, e[k])
                        updated = True
                if updated:
                    obj.save(update_fields=["target", "description", "kcal_burned_per_min"])
                ex_objs.append(obj)

        if not ex_objs:
            raise CommandError("No valid exercises loaded after upsert.")

        # 시드: 월~금, 하루 3~5개, 운동 고르게 분배
        random.seed(1234)
        created_days = 0
        created_tasks = 0

        def make_wp(day: date) -> 'WP':
            title = f"{day.isoformat()} 플랜"
            wp, _ = WorkoutPlan.objects.get_or_create(
                user=u, title=title,
                defaults={
                    "description": "demo",
                    "summary": "demo",
                    "target_focus": "general",
                    "source": getattr(WorkoutPlan.PlanSource, "MANUAL", "manual"),
                    "ai_model": "demo", "ai_version": "demo", "ai_prompt": "demo",
                    "created_at": aware(datetime.combine(day, time(9, 0))),
                    "updated_at": timezone.now(),
                }
            )
            # created_at이 당일로 보이도록 보정
            if getattr(wp, "created_at", None) and wp.created_at.date() != day:
                wp.created_at = aware(datetime.combine(day, time(9, 0)))
                wp.save(update_fields=["created_at"])
            return wp  # type: ignore[return-value]

        def make_task(wp: 'WP', ex: 'EX', day: date, order: int, done: bool) -> 'TI':
            # 다양화: 시간/세트/반복/강도 랜덤
            mins = random.choice([10, 12, 15, 18, 20, 25, 30])
            sets = random.choice([2, 3, 4, 5])
            reps = random.choice([8, 10, 12, 15, 20])

            # TaskItem.IntensityLevel 이 enum인 경우 안전 접근
            inten_low = getattr(TaskItem.IntensityLevel, "LOW", "low")
            inten_med = getattr(TaskItem.IntensityLevel, "MEDIUM", "medium")
            inten_high = getattr(TaskItem.IntensityLevel, "HIGH", "high")
            inten = random.choice([inten_low, inten_med, inten_high])

            # kcal 추정치: 운동별 분당 kcal * duration
            per_min_kcal = float(getattr(ex, "kcal_burned_per_min", 5.0) or 5.0)
            kcal = int(per_min_kcal * mins)

            t = TaskItem(
                workout_plan=wp,
                exercise=ex,
                duration_min=mins,
                order=order,
                intensity=inten,
                completed=done,
                notes="demo",
                is_ai_recommended=True,
                ai_goal="체력 향상",
                recommended_weight_range=random.choice(["Light", "Medium", "Heavy"]),
                target_sets=sets,
                target_reps=reps,
                ai_metadata={"seed_date": day.isoformat(), "kcal": kcal},
            )
            if done and hasattr(t, "completed_at"):
                t.completed_at = aware(datetime.combine(day, time(18, 0)))
            if not dry_run:
                t.save()
            return t  # type: ignore[return-value]

        d = start_d
        while d <= end_d:
            if d.weekday() < 5:  # 월(0)~금(4)
                wp = make_wp(d)
                n = random.randint(per_min, per_max)

                # 매일 섞고 필요 개수만 '중복 없이' 선택 (풀보다 적으면 중복 허용)
                pool = ex_objs[:]
                random.shuffle(pool)
                chosen: List['EX'] = pool[:n] if len(pool) >= n else random.choices(ex_objs, k=n)

                # 일부 완료 처리
                done_indices = set(random.sample(range(n), k=random.randint(1, n)))

                if dry_run:
                    self.stdout.write(f"[DRY] {d} -> {len(chosen)} tasks")
                else:
                    order = 1
                    for idx, ex in enumerate(chosen):
                        done = idx in done_indices
                        make_task(wp, ex, d, order, done)
                        created_tasks += 1
                        order += 1
                created_days += 1
            d += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"SEEDED: days={created_days}, tasks={created_tasks}"))
