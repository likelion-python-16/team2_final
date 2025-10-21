# team2_final/today_views.py
from __future__ import annotations

from datetime import date
from typing import Dict, Any, Optional

from django.db.models import Sum, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


def _round1(v: Any) -> float:
    """숫자를 소수 1자리로 반올림. None/NaN/inf 안전 처리."""
    try:
        x = float(v or 0.0)
    except Exception:
        return 0.0
    if x != x or x in (float("inf"), float("-inf")):
        return 0.0
    return round(x, 1)


# 선택: WorkoutLog가 존재하는 환경에서 운동 시간 합계 사용
try:
    from tasks.models import WorkoutLog
    HAS_WORKOUT_LOG = True
except Exception:
    HAS_WORKOUT_LOG = False


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def today_summary(request):
    """
    오늘 요약 엔드포인트

    응답 스키마:
    {
      "date": "YYYY-MM-DD",
      "dailygoal": {
        "date": "...",
        "kcal_target": number,
        "protein_target_g": number,
        "workout_minutes_target": number,
        "kcal_actual": number,
        "protein_actual_g": number,
        "workout_minutes_actual": number,
        "score": number|null
      } | null,
      "workout_minutes": number,       # ✅ WorkoutLog 합계(분)
      "nutrition": {
        "date": "...",
        "kcal": number,
        "protein_g": number,
        "fat_g": number,
        "carb_g": number
      },
      "tasks": [
        { "id":..., "exercise_id":..., "exercise_name":..., "duration_min":..., "order":..., "completed": bool, "skipped": bool },
        ...
      ]
    }
    """
    user = request.user
    today = date.today()

    # ---- DailyGoal ----
    dailygoal: Optional[Dict[str, Any]] = None
    try:
        from goals.models import DailyGoal
        dg = DailyGoal.objects.filter(user=user, date=today).first()
        if dg:
            score_val = getattr(dg, "score", None)
            if score_val is None:
                score_val = getattr(dg, "completion_score", None)

            dailygoal = {
                "date": today.isoformat(),
                "kcal_target": _round1(getattr(dg, "kcal_target", 0)),
                "protein_target_g": _round1(getattr(dg, "protein_target_g", 0)),
                "workout_minutes_target": _round1(getattr(dg, "workout_minutes_target", 0)),
                "kcal_actual": _round1(getattr(dg, "kcal_actual", 0)),
                "protein_actual_g": _round1(getattr(dg, "protein_actual_g", 0)),
                "workout_minutes_actual": _round1(getattr(dg, "workout_minutes_actual", 0)),
                "score": _round1(score_val) if score_val is not None else None,
            }
    except Exception:
        dailygoal = None

    # ---- WorkoutLog 합계 (있으면) ----
    workout_minutes = 0.0
    if HAS_WORKOUT_LOG:
        try:
            workout_minutes = float(
                WorkoutLog.objects
                .filter(user=user, date=today)
                .aggregate(Sum("duration_min"))["duration_min__sum"]
                or 0.0
            )
        except Exception:
            workout_minutes = 0.0
    workout_minutes = _round1(workout_minutes)

    # DailyGoal에 보강 반영(응답 레벨에서만 보강)
    if dailygoal is not None:
        if (dailygoal.get("workout_minutes_actual") or 0.0) == 0.0 and workout_minutes > 0.0:
            dailygoal["workout_minutes_actual"] = workout_minutes

    # ---- NutritionLog 합계 (필드명: date / *_total) ----
    nutrition = {"date": today.isoformat(), "kcal": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carb_g": 0.0}
    try:
        from intakes.models import NutritionLog
        agg = (
            NutritionLog.objects
            .filter(user=user, date=today)  # ✅ 주의: log_date 아님
            .aggregate(
                kcal=Sum("kcal_total"),
                protein=Sum("protein_total_g"),
                fat=Sum("fat_total_g"),
                carbs=Sum("carb_total_g"),
            )
        )
        nutrition.update({
            "kcal": _round1(agg.get("kcal")),
            "protein_g": _round1(agg.get("protein")),
            "fat_g": _round1(agg.get("fat")),
            "carb_g": _round1(agg.get("carbs")),
        })
    except Exception:
        pass  # 모델 부재/마이그레 전이면 0 유지

    # ---- Tasks (오늘 due 또는 due 없음) ----
    tasks = []
    try:
        from tasks.models import TaskItem
        qs = (
            TaskItem.objects
            .filter(workout_plan__user=user)
            .filter(Q(due_date=today) | Q(due_date__isnull=True))
            .order_by("order", "id")
        )
        for t in qs:
            exercise = getattr(t, "exercise", None)
            tasks.append({
                "id": getattr(t, "id", None),
                "exercise_id": getattr(t, "exercise_id", None),
                "exercise_name": getattr(exercise, "name", None) if exercise else None,
                "duration_min": getattr(t, "duration_min", None),
                "order": getattr(t, "order", None),
                "completed": bool(getattr(t, "completed", False)),
                "skipped": bool(getattr(t, "skipped", False)),
            })
    except Exception:
        tasks = []

    return Response({
        "date": today.isoformat(),
        "dailygoal": dailygoal,
        "workout_minutes": workout_minutes,  # ✅ 프런트에서 링/요약에 바로 사용
        "nutrition": nutrition,
        "tasks": tasks,
    })
