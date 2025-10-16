# tasks/api_views.py
from datetime import datetime
from django.db.models import Sum, Count, Q, DateField
from django.db.models.functions import Cast
from django.core.exceptions import FieldError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings

from .models import TaskItem, WorkoutPlan

# 전역 설정값만 유지 (done_min 전역 사용 금지)
kcal_per_min = getattr(settings, "WORKOUT_KCAL_PER_MIN", 5)


def parse_yyyy_mm_dd(s: str):
    """'YYYY-MM-DD' → date. 실패 시 None."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def filter_by_user(qs, user):
    """
    로그인 사용자 스코프 제한.
    - workout_plan__user 우선
    - TaskItem.user 대안
    - 둘 다 없으면 그대로 반환
    """
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
    """
    주어진 date d로 TaskItem을 최대한 날짜 매칭.
    1) WorkoutPlan 쪽 날짜 후보
    2) TaskItem 쪽 날짜/생성일 후보
    매칭되면 즉시 반환, 전부 실패하면 None.
    """
    # 1) WorkoutPlan 날짜 필드 후보
    plan_date_fields = ["date", "plan_date", "scheduled_date", "scheduled_for", "day"]
    for f in plan_date_fields:
        try:
            return qs.filter(**{f"workout_plan__{f}": d})
        except FieldError:
            continue

    # 2) TaskItem 날짜/생성일 후보
    task_date_fields = ["date", "workout_date", "scheduled_date", "created_at__date", "completed_at__date"]
    for f in task_date_fields:
        try:
            return qs.filter(**{f: d})
        except FieldError:
            continue

    return None


def latest_plan_tasks(qs):
    """
    날짜 매칭 실패 시 최후의 보루:
    - 해당 유저의 가장 최근 WorkoutPlan을 골라 그 TaskItem을 반환
    - 최근 기준은 다음 중 존재하는 필드 순서대로 정렬:
      created_at, created, updated_at, updated, id
    """
    plan_ids = list(
        qs.exclude(workout_plan__isnull=True)
          .values_list("workout_plan_id", flat=True).distinct()
    )

    candidates = WorkoutPlan.objects.all()
    if plan_ids:
        candidates = candidates.filter(id__in=plan_ids)

    orderings = ["-created_at", "-created", "-updated_at", "-updated", "-id"]
    for field in orderings:
        try:
            latest = candidates.order_by(field).first()
            if latest:
                return qs.filter(workout_plan=latest)
        except FieldError:
            continue
    return qs.none()


def base_qs(request_user, date_str: str, plan_id: str | None):
    """
    plan_id가 있으면 해당 플랜의 TaskItem,
    없으면 '그 날짜' TaskItem을 최대한 찾아 반환.
    전부 실패 시 '가장 최근 플랜의 TaskItem'로 폴백.
    """
    d = parse_yyyy_mm_dd(date_str)
    if not d:
        raise ValueError("invalid date format")

    qs = TaskItem.objects.select_related("workout_plan", "exercise")
    qs = filter_by_user(qs, request_user)

    if plan_id:
        return qs.filter(workout_plan_id=plan_id)

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


class WorkoutSummaryView(APIView):
    """
    GET /api/workoutplans/summary/?date=YYYY-MM-DD[&workout_plan=<id>]
    - total_min: 모든 Task의 duration 합 (기존 키 유지)
    - tasks_count, completed_count, calories (기존 키 유지)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        plan_id = request.query_params.get("workout_plan")
        if not date_str:
            return Response({"detail": "date is required (YYYY-MM-DD)"}, status=400)

        try:
            qs = base_qs(request.user, date_str, plan_id)
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

        # 완료된 분 합은 지역변수로 계산 (전역 X)
        done_min = int(qs.filter(completed=True).aggregate(x=Sum("duration_min")).get("x") or 0)
        calories = int(done_min * kcal_per_min)

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
            qs = base_qs(request.user, date_str, plan_id)
        except ValueError:
            return Response({"detail": "invalid date format"}, status=400)

        agg = qs.aggregate(total=Count("id"), done=Count("id", filter=Q(completed=True)))
        total = int(agg.get("total") or 0)
        done = int(agg.get("done") or 0)

        recos = []
        if total == 0:
            recos.append({"title": "오늘 계획이 없어요", "action_text": "플랜 생성", "action_url": "/tasks/workouts/#wk-ensure-today"})
        else:
            ratio = done / total if total else 0.0
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
            qs = base_qs(request.user, date_str, plan_id)
        except ValueError:
            return Response({"detail": "invalid date format"}, status=400)

        bullets = []

        # 대표 운동명
        top_name = None
        try:
            q1 = qs.exclude(exercise_name__isnull=True).exclude(exercise_name__exact="")
            top = list(q1.values_list("exercise_name", flat=True)[:1])
            if top:
                top_name = top[0]
        except FieldError:
            pass
        if not top_name:
            try:
                top = list(qs.filter(exercise__isnull=False).values_list("exercise__name", flat=True)[:1])
                if top:
                    top_name = top[0]
            except FieldError:
                pass
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
