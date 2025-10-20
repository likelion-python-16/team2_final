# tasks/api_views.py
from datetime import datetime
from typing import Optional

from django.conf import settings
from django.core.exceptions import FieldError
from django.db.models import Sum, Count, Q, DateField
from django.db.models.functions import Cast
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TaskItem, WorkoutPlan

# ---------- 설정 ----------
kcal_per_min_default = getattr(settings, "WORKOUT_KCAL_PER_MIN", 5)
INTENSITY_KCAL_MAP = {
    "light": 4, "low": 4,
    "mid": 6, "medium": 6,
    "high": 8, "hard": 9,
}
INTENSITY_WEIGHT = {
    "light": 1.0, "low": 1.0,
    "mid": 1.2, "medium": 1.2,
    "high": 1.5, "hard": 1.6,
}

# ---------- 유틸 ----------
def parse_yyyy_mm_dd(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def _has_field(model_cls, field_name: str) -> bool:
    try:
        model_cls._meta.get_field(field_name)
        return True
    except Exception:
        return False

def filter_by_user(qs, user):
    try:
        return qs.filter(workout_plan__user=user)
    except FieldError:
        pass
    try:
        return qs.filter(user=user)
    except FieldError:
        pass
    return qs

def any_date_filter(qs, d):
    plan_date_fields = ["date", "plan_date", "scheduled_date", "scheduled_for", "day"]
    for f in plan_date_fields:
        try:
            return qs.filter(**{f"workout_plan__{f}": d})
        except FieldError:
            continue
    task_date_fields = ["date", "workout_date", "scheduled_date", "created_at__date", "completed_at__date"]
    for f in task_date_fields:
        try:
            return qs.filter(**{f: d})
        except FieldError:
            continue
    return None

def latest_plan_tasks(qs):
    plan_ids = list(
        qs.exclude(workout_plan__isnull=True).values_list("workout_plan_id", flat=True).distinct()
    )
    candidates = WorkoutPlan.objects.all()
    if plan_ids:
        candidates = candidates.filter(id__in=plan_ids)
    for field in ["-created_at", "-created", "-updated_at", "-updated", "-id"]:
        try:
            latest = candidates.order_by(field).first()
            if latest:
                return qs.filter(workout_plan=latest)
        except FieldError:
            continue
    return qs.none()

def base_qs(request_user, date_str: str, plan_id: Optional[str]):
    d = parse_yyyy_mm_dd(date_str)
    if not d:
        raise ValueError("invalid date format")
    qs = TaskItem.objects.select_related("workout_plan", "exercise")
    qs = filter_by_user(qs, request_user)

    if plan_id:
        try:
            pid = int(plan_id)
        except Exception:
            raise ValueError("invalid workout_plan id")
        return qs.filter(workout_plan_id=pid)

    matched = any_date_filter(qs, d)
    if matched is not None and matched.exists():
        return matched

    for f in ["created_at", "created", "updated_at", "updated"]:
        try:
            casted = qs.annotate(_pdate=Cast(f"workout_plan__{f}", output_field=DateField()))
            tmp = casted.filter(_pdate=d)
            if tmp.exists():
                return tmp
        except FieldError:
            continue
    return latest_plan_tasks(qs)

def norm_intensity(val: str | None) -> str:
    if not val:
        return "medium"
    v = str(val).strip().lower()
    if v in ("mid",): return "medium"
    if v in ("light","low"): return "light"
    if v in ("high","hard","intense"): return "high"
    if v not in ("light","medium","high"): return "medium"
    return v

def kcal_per_min_for(task) -> int:
    try:
        intensity = norm_intensity(getattr(task, "intensity", None))
        return INTENSITY_KCAL_MAP.get(intensity, kcal_per_min_default)
    except Exception:
        return kcal_per_min_default

def task_group_key(t):
    for f in ("muscle_group","body_part","category","exercise_group","type","target"):
        try:
            val = getattr(t, f, None)
            if val: return str(val)
        except Exception:
            continue
    try:
        val = t.exercise and getattr(t.exercise, "group", None)
        if val: return str(val)
    except Exception:
        pass
    return "기타"

# ---------- API ----------
class WorkoutSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        plan_id  = request.query_params.get("workout_plan")
        if not date_str:
            return Response({"detail": "date is required (YYYY-MM-DD)"}, status=400)
        try:
            qs = base_qs(request.user, date_str, plan_id)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        has_completed = _has_field(TaskItem, "completed")

        # 안전한 집계
        agg = qs.aggregate(
            total_min=Sum("duration_min"),
            tasks_count=Count("id"),
        )
        total_min   = int(agg.get("total_min") or 0)
        tasks_count = int(agg.get("tasks_count") or 0)

        if has_completed:
            try:
                completed_count = int(qs.filter(completed=True).count())
            except Exception:
                completed_count = 0
        else:
            completed_count = 0

        # 완료 항목 칼로리
        calories_sum = 0
        try:
            done_iterable = qs.filter(completed=True) if has_completed else qs
            for t in done_iterable.values("duration_min", "intensity"):
                minutes = int(t.get("duration_min") or 0)
                intensity = norm_intensity(t.get("intensity"))
                rate = INTENSITY_KCAL_MAP.get(intensity, kcal_per_min_default)
                calories_sum += minutes * rate
        except Exception:
            # values()가 실패하면 안전 루프
            try:
                for t in (done_iterable[:200] if has_completed else qs[:200]):
                    minutes = int(getattr(t, "duration_min", 0) or 0)
                    rate = kcal_per_min_for(t)
                    calories_sum += minutes * rate
            except Exception:
                calories_sum = 0

        return Response({
            "date": date_str,
            "workout_plan": int(plan_id) if plan_id else None,
            "total_min": total_min,
            "tasks_count": tasks_count,
            "completed_count": completed_count,
            "calories": int(calories_sum),
            "note": "기본 요약입니다."
        })


class RecommendationsView(APIView):
    """
    규칙:
    1) 할 일 없음 → 플랜 생성 유도
    2) 남은(Task.completed=False) 항목 그룹핑 → 최다 그룹 추천
    3) 남은 항목 평균 강도/총 시간에 따라 가이드 문구
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        plan_id  = request.query_params.get("workout_plan")
        if not date_str:
            return Response({"detail": "date is required"}, status=400)
        try:
            qs = base_qs(request.user, date_str, plan_id)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        total = qs.count()
        if total == 0:
            return Response([{
                "title": "오늘 계획이 없어요",
                "action_text": "플랜 생성",
                "action_url": "/tasks/workouts/#wk-ensure-today"
            }])

        # 남은 항목 계산 (completed 필드 유무 가드)
        has_completed = _has_field(TaskItem, "completed")
        try:
            remain_qs = qs.filter(completed=False) if has_completed else qs
        except Exception:
            remain_qs = qs

        remain = list(remain_qs[:200])

        # 2) 그룹핑
        groups = {}
        for t in remain:
            key = task_group_key(t)
            groups.setdefault(key, {"items": [], "minutes": 0, "ints": []})
            groups[key]["items"].append(t)
            groups[key]["minutes"] += int(getattr(t, "duration_min", 0) or 0)
            groups[key]["ints"].append(norm_intensity(getattr(t, "intensity", None)))

        recos = []
        if groups:
            gname, info = sorted(
                groups.items(),
                key=lambda kv: (len(kv[1]["items"]), kv[1]["minutes"]),
                reverse=True
            )[0]
            recos.append({"title": f"{gname} 중심으로 마무리해보세요 ({len(info['items'])}개 남음)"})

        # 3) 강도/시간 기반 가이드
        remain_minutes = sum(int(getattr(t, "duration_min", 0) or 0) for t in remain)
        ints = [norm_intensity(getattr(t, "intensity", None)) for t in remain]
        hi = sum(1 for x in ints if x == "high")
        med = sum(1 for x in ints if x == "medium")
        low = sum(1 for x in ints if x == "light")

        if remain_minutes <= 20 and med + low >= hi:
            recos.append({"title": "남은 시간 20분 이하 — 전신 서킷으로 깔끔하게!"})
        elif hi >= med + low:
            recos.append({"title": "고강도 위주 — 세트 간 휴식 90초로 품질 유지"})
        else:
            recos.append({"title": "중강도 위주 — 마지막은 스트레칭으로 마무리"})

        return Response(recos)


class TodayInsightsView(APIView):
    """
    GET /api/insights/today/?date=YYYY-MM-DD[&workout_plan=<id>]
    - 대표 운동: duration_min * 강도 가중치 (없으면 1.2) 기준
    - 보조: 진행도(완료/전체), 총 계획 시간
    - 절대 500 터지지 않도록 방어
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        plan_id  = request.query_params.get("workout_plan")
        debug    = request.query_params.get("debug") == "1"

        if not date_str:
            return Response({"detail": "date is required"}, status=400)

        try:
            qs = base_qs(request.user, date_str, plan_id)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        except Exception as e:
            if debug:
                return Response({"detail": f"base_qs error: {e.__class__.__name__}: {e}"}, status=500)
            return Response({"bullets": []}, status=200)

        bullets = []
        try:
            # 1) 대표 운동 후보
            candidates = []
            try:
                candidates = list(qs.values("exercise_name", "duration_min", "intensity"))
            except Exception:
                candidates = []

            if not candidates:
                try:
                    candidates = list(qs.values("exercise__name", "duration_min", "intensity"))
                except Exception:
                    candidates = []

            if not candidates:
                tmp = []
                for t in qs[:50]:
                    try:
                        name = getattr(t, "exercise_name", None)
                        if not name and getattr(t, "exercise", None):
                            name = getattr(t.exercise, "name", None)
                        if not name:
                            name = getattr(t, "name", None) or getattr(t, "title", None) or getattr(t, "label", None) or "Exercise"
                        mins = int(getattr(t, "duration_min", 0) or 0)
                        inten = getattr(t, "intensity", None)
                        tmp.append({"_name": name, "_mins": mins, "_intensity": inten})
                    except Exception:
                        continue
                if tmp:
                    candidates = [{"exercise_name": x["_name"], "duration_min": x["_mins"], "intensity": x["_intensity"]} for x in tmp]

            # 2) 가중치 스코어
            best_name, best_score = None, -1
            for t in candidates:
                try:
                    name = t.get("exercise_name") or t.get("exercise__name") or "Exercise"
                    mins = int(t.get("duration_min") or 0)
                    inten = t.get("intensity")
                    v = str(inten).strip().lower() if inten else "medium"
                    if v == "mid": v = "medium"
                    weight = INTENSITY_WEIGHT.get(v, 1.2)
                    score = mins * weight
                    if score > best_score:
                        best_score = score
                        best_name = name
                except Exception:
                    continue
            if best_name:
                bullets.append(f"대표 운동: {best_name}")

            # 3) 진행도
            has_completed = _has_field(TaskItem, "completed")
            try:
                total = qs.count()
                if total:
                    done = qs.filter(completed=True).count() if has_completed else 0
                    bullets.append(f"진행: {done}/{total}")
            except Exception:
                pass

            # 4) 총 계획 시간
            try:
                total_min = qs.aggregate(Sum("duration_min")).get("duration_min__sum") or 0
                bullets.append(f"총 계획 시간: {int(total_min)}분")
            except Exception:
                pass

            return Response({"bullets": bullets})
        except Exception as e:
            if debug:
                return Response({"detail": f"insights error: {e.__class__.__name__}: {e}", "bullets": []}, status=500)
            return Response({"bullets": []})
