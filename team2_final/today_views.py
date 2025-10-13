from datetime import date
from django.db.models import Sum, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def today_summary(request):
    user = request.user
    today = date.today()

    # ---- DailyGoal ----
    dailygoal = None
    try:
        from goals.models import DailyGoal
        dg = DailyGoal.objects.filter(user=user, date=today).first()
        if dg:
            # score 없으면 completion_score 대체 사용
            score_val = getattr(dg, "score", None)
            if score_val is None:
                score_val = getattr(dg, "completion_score", None)

            dailygoal = {
                "date": today.isoformat(),
                "kcal_target": getattr(dg, "kcal_target", 0) or 0,
                "protein_target_g": getattr(dg, "protein_target_g", 0) or 0,
                "workout_minutes_target": getattr(dg, "workout_minutes_target", 0) or 0,
                "kcal_actual": getattr(dg, "kcal_actual", 0) or 0,
                "protein_actual_g": getattr(dg, "protein_actual_g", 0) or 0,
                "workout_minutes_actual": getattr(dg, "workout_minutes_actual", 0) or 0,
                "score": score_val,
            }
    except Exception:
        dailygoal = None

    # ---- NutritionLog 합계 (필드명: date / *_total) ----
    nutrition = {"date": today.isoformat(), "kcal": 0, "protein_g": 0, "fat_g": 0, "carb_g": 0}
    try:
        from intakes.models import NutritionLog
        agg = (
            NutritionLog.objects
            .filter(user=user, date=today)  # ✅ log_date 아님!
            .aggregate(
                kcal=Sum("kcal_total"),
                protein=Sum("protein_total_g"),
                fat=Sum("fat_total_g"),
                carbs=Sum("carb_total_g"),
            )
        )
        nutrition.update({
            "kcal": agg.get("kcal") or 0,
            "protein_g": agg.get("protein") or 0,
            "fat_g": agg.get("fat") or 0,
            "carb_g": agg.get("carbs") or 0,
        })
    except Exception:
        pass

    # ---- Tasks ----
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
                "completed": getattr(t, "completed", False),
                "skipped": getattr(t, "skipped", False),
            })
    except Exception:
        tasks = []

    return Response({
        "date": today.isoformat(),
        "dailygoal": dailygoal,
        "nutrition": nutrition,
        "tasks": tasks,
    })
