# tasks/api_views.py
from datetime import datetime
from django.db.models import Sum, Count, Q
from django.core.exceptions import FieldError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TaskItem, WorkoutPlan


def parse_yyyy_mm_dd(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def base_qs(date_str: str, plan_id: str | None):
    """
    plan_id가 있으면 그 플랜의 TaskItem,
    없으면 '그 날짜'의 TaskItem을 최대한 안전하게 찾는다.
    - WorkoutPlan 날짜 필드 후보 여러 개 시도
    - TaskItem 날짜/생성일 후보 여러 개 시도
    """
    d = parse_yyyy_mm_dd(date_str)
    if not d:
        raise ValueError("invalid date format")

    qs = TaskItem.objects.select_related("workout_plan", "exercise")

    if plan_id:
        return qs.filter(workout_plan_id=plan_id)

    # 1) WorkoutPlan 쪽 날짜 필드 후보
    plan_date_fields = ["date", "plan_date", "scheduled_date", "scheduled_for", "day"]
    for f in plan_date_fields:
        try:
            return qs.filter(**{f"workout_plan__{f}": d})
        except FieldError:
            continue

    # 2) TaskItem 자체 날짜/생성일 후보
    task_date_fields = ["date", "workout_date", "scheduled_date", "created_at__date", "completed_at__date"]
    for f in task_date_fields:
        try:
            return qs.filter(**{f: d})
        except FieldError:
            continue

    # 3) 최후의 보루
    try:
        return qs.filter(created_at__date=d)
    except FieldError:
        return qs.none()


class WorkoutSummaryView(APIView):
    """
    GET /api/workoutplans/summary/?date=YYYY-MM-DD[&workout_plan=<id>]
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        plan_id = request.query_params.get("workout_plan")
        if not date_str:
            return Response({"detail": "date is required (YYYY-MM-DD)"}, status=400)

        try:
            qs = base_qs(date_str, plan_id)
        except ValueError:
            return Response({"detail": "invalid date format"}, status=400)

        agg = qs.aggregate(
            total_min=Sum("duration_min"),
            tasks_count=Count("id"),
            completed_count=Count("id", filter=Q(completed=True)),
        )
        total_min = int(agg.get("total_min") or 0)
        tasks_count = int(agg.get("tasks_count") or 0)
        completed_count = int(agg.get("completed_count") or 0)

        done_min = qs.filter(completed=True).aggregate(x=Sum("duration_min")).get("x") or 0
        calories = int(done_min * 5)

        return Response({
            "date": date_str,
            "workout_plan": int(plan_id) if plan_id else None,
            "total_min": total_min,
            "tasks_count": tasks_count,
            "completed_count": completed_count,
            "calories": calories,
            "note": "기본 요약입니다."
        })


class RecommendationsView(APIView):
    """
    GET /api/recommendations/?date=YYYY-MM-DD[&workout_plan=<id>]
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        plan_id = request.query_params.get("workout_plan")
        if not date_str:
            return Response({"detail": "date is required"}, status=400)

        try:
            qs = base_qs(date_str, plan_id)
        except ValueError:
            return Response({"detail": "invalid date format"}, status=400)

        agg = qs.aggregate(total=Count("id"), done=Count("id", filter=Q(completed=True)))
        total = agg.get("total") or 0
        done = agg.get("done") or 0

        recos = []
        if total == 0:
            recos.append({"title": "오늘 계획이 없어요", "action_text": "플랜 생성", "action_url": "/tasks/workouts/#wk-ensure-today"})
        else:
            ratio = done / total if total else 0
            if ratio < 0.34:
                recos.append({"title": "가벼운 전신 루틴부터 워밍업 시작!"})
            elif ratio < 0.67:
                recos.append({"title": "남은 근력 위주로 마무리해요"})
            else:
                recos.append({"title": "스트레칭/쿨다운으로 회복하세요"})

        return Response(recos)


class TodayInsightsView(APIView):
    """
    GET /api/insights/today/?date=YYYY-MM-DD[&workout_plan=<id>]
    - 대표 운동명/진행/총 계획 시간
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        plan_id = request.query_params.get("workout_plan")
        if not date_str:
            return Response({"detail": "date is required"}, status=400)

        try:
            qs = base_qs(date_str, plan_id)
        except ValueError:
            return Response({"detail": "invalid date format"}, status=400)

        bullets = []

        # 대표 운동명: 여러 후보 필드 순차 시도 (exercise_name → exercise__name → 기타)
        top_name = None
        # 1) exercise_name (직접 필드)
        try:
            q1 = qs.exclude(exercise_name__isnull=True).exclude(exercise_name__exact="")
            top = list(q1.values_list("exercise_name", flat=True)[:1])
            if top:
                top_name = top[0]
        except FieldError:
            pass

        # 2) exercise FK가 있다면 name 필드 추정
        if not top_name:
            try:
                top = list(
                    qs.filter(exercise__isnull=False)
                      .values_list("exercise__name", flat=True)[:1]
                )
                if top:
                    top_name = top[0]
            except FieldError:
                pass

        # 3) 다른 이름 필드 후보(혹시 커스텀)
        if not top_name:
            for f in ["name", "title", "label"]:
                try:
                    top = list(qs.values_list(f, flat=True)[:1])
                    if top and top[0]:
                        top_name = top[0]
                        break
                except FieldError:
                    continue

        if top_name:
            bullets.append(f"대표 운동: {top_name}")

        total = qs.count()
        if total:
            done = qs.filter(completed=True).count()
            bullets.append(f"진행: {done}/{total}")

        total_min = qs.aggregate(Sum("duration_min")).get("duration_min__sum") or 0
        bullets.append(f"총 계획 시간: {int(total_min)}분")

        return Response({"bullets": bullets})
