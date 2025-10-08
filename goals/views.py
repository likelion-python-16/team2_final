# goals/views.py
from datetime import date, timedelta
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Goal, DailyGoal, GoalProgress
from .serializers import GoalSerializer, DailyGoalSerializer, GoalProgressSerializer

# NutritionLog이 있을 때만 연동(부트캠프 편의용)
try:
    from intakes.models import NutritionLog
    HAS_NUTRITION = True
except Exception:
    HAS_NUTRITION = False


class BaseUserOwnedModelViewSet(viewsets.ModelViewSet):
    """
    공통 규칙:
    - 인증 필수
    - 목록/상세 모두 '내 데이터'만 보임
    - 생성/수정 시 user를 request.user로 강제 주입
    """
    permission_classes = [permissions.IsAuthenticated]
    ordering = ("-id",)  # 최신순

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by(*self.ordering)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)


class GoalViewSet(BaseUserOwnedModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer


class DailyGoalViewSet(BaseUserOwnedModelViewSet):
    queryset = DailyGoal.objects.select_related("goal").all()
    serializer_class = DailyGoalSerializer

    # POST /api/dailygoals/ensure/?date=YYYY-MM-DD&goal_type=diet
    # (옵션) kcal_target, protein_target_g, workout_minutes_target 쿼리 파라미터로 오버라이드 가능
    @action(detail=False, methods=["post"], url_path="ensure")
    def ensure(self, request):
        q = request.query_params

        # 날짜 파싱(기본: 오늘)
        try:
            d_str = (q.get("date") or "").strip()
            d = date.fromisoformat(d_str) if d_str else timezone.localdate()
        except Exception:
            return Response({"detail": "date는 YYYY-MM-DD 형식이어야 합니다."}, status=400)

        goal_type = (q.get("goal_type") or "diet").strip()
        if not goal_type:
            return Response({"detail": "goal_type 쿼리 파라미터가 필요합니다."}, status=400)

        def _as_int(name: str):
            v = q.get(name)
            if v in (None, ""):
                return None
            try:
                return int(v)
            except Exception:
                return None

        kcal_t = _as_int("kcal_target")
        protein_t = _as_int("protein_target_g")
        workout_t = _as_int("workout_minutes_target")

        # 1) Goal ensure
        goal, _g_created = Goal.objects.get_or_create(
            user=request.user, goal_type=goal_type
        )

        # 2) DailyGoal ensure
        dg, created = DailyGoal.objects.get_or_create(
            user=request.user, goal=goal, date=d,
            defaults={
                "kcal_target": kcal_t,
                "protein_target_g": protein_t,
                "workout_minutes_target": workout_t,
            },
        )

        updated = False
        if not created:
            for fname, val in [
                ("kcal_target", kcal_t),
                ("protein_target_g", protein_t),
                ("workout_minutes_target", workout_t),
            ]:
                if val is not None and getattr(dg, fname) != val:
                    setattr(dg, fname, val)
                    updated = True
            if updated:
                dg.save(update_fields=["kcal_target", "protein_target_g", "workout_minutes_target"])

        # 점수 재계산(가능하면)
        try:
            dg.compute_score()
        except Exception:
            pass

        return Response(
            {"created": created, "updated": updated, "daily_goal": DailyGoalSerializer(dg).data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    # GET /api/dailygoals/summary/?start=YYYY-MM-DD&days=7
    # 날짜별 타겟/실측/세션/점수 배열로 반환(프런트 차트 바인딩용)
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        q = request.query_params
        # 시작일(기본: 오늘)
        try:
            start_str = (q.get("start") or "").strip()
            start = date.fromisoformat(start_str) if start_str else timezone.localdate()
        except Exception:
            return Response({"detail": "start는 YYYY-MM-DD 형식이어야 합니다."}, status=400)

        # 기간(1~31일)
        try:
            days = int(q.get("days") or 7)
            if not (1 <= days <= 31):
                raise ValueError
        except Exception:
            return Response({"detail": "days는 1~31 사이의 정수여야 합니다."}, status=400)

        end = start + timedelta(days=days - 1)

        dgs = (
            self.get_queryset()
            .filter(date__range=(start, end))
            .select_related("goal")
            .order_by("date", "id")
        )

        # 보조 조회 함수
        def _nutrition_for(d):
            if not HAS_NUTRITION:
                return None
            return (
                NutritionLog.objects.filter(user=request.user, date=d)
                .order_by("-id")
                .first()
            )

        def _progress_for(d, goal):
            return (
                GoalProgress.objects.filter(user=request.user, goal=goal, date=d)
                .order_by("-id")
                .first()
            )

        rows = []
        remaining_days = {start + timedelta(days=i) for i in range(days)}

        for dg in dgs:
            nl = _nutrition_for(dg.date)
            gp = _progress_for(dg.date, dg.goal)
            rows.append(
                {
                    "date": dg.date.isoformat(),
                    "goal_id": dg.goal_id,
                    "goal_type": dg.goal.goal_type,
                    "kcal_target": dg.kcal_target,
                    "protein_target_g": dg.protein_target_g,
                    "workout_minutes_target": dg.workout_minutes_target,
                    "kcal_total": getattr(nl, "kcal_total", None) if nl else None,
                    "protein_total_g": getattr(nl, "protein_total_g", None) if nl else None,
                    "completed_sessions": getattr(gp, "completed_sessions", None) if gp else None,
                    "completion_score": dg.completion_score,
                }
            )
            remaining_days.discard(dg.date)

        # DailyGoal이 없는 날짜도 빈 행을 추가(차트 구간 맞춤)
        for d in sorted(remaining_days):
            nl = _nutrition_for(d)
            rows.append(
                {
                    "date": d.isoformat(),
                    "goal_id": None,
                    "goal_type": None,
                    "kcal_target": None,
                    "protein_target_g": None,
                    "workout_minutes_target": None,
                    "kcal_total": getattr(nl, "kcal_total", None) if nl else None,
                    "protein_total_g": getattr(nl, "protein_total_g", None) if nl else None,
                    "completed_sessions": None,
                    "completion_score": None,
                }
            )

        return Response(rows, status=200)


class GoalProgressViewSet(BaseUserOwnedModelViewSet):
    queryset = GoalProgress.objects.all()
    serializer_class = GoalProgressSerializer
