# tasks/views.py
from datetime import date, timedelta
from pathlib import Path
import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.response import Response

from .models import Exercise, WorkoutPlan, TaskItem

# WorkoutLog 모델이 있으면 사용
try:
    from .models import WorkoutLog
    HAS_WORKOUT_LOG = True
except Exception:
    HAS_WORKOUT_LOG = False

from .serializers import ExerciseSerializer, WorkoutPlanSerializer, TaskItemSerializer
if HAS_WORKOUT_LOG:
    from .serializers import WorkoutLogSerializer


# ---- 공통 헬퍼 -------------------------------------------------------------
def monday_of(d: date) -> date:
    """ISO Monday(1) 기준: 해당 날짜가 속한 주의 월요일을 반환."""
    return d - timedelta(days=d.isoweekday() - 1)


def _has_field(model_cls, field_name: str) -> bool:
    try:
        model_cls._meta.get_field(field_name)
        return True
    except Exception:
        return False


# ------------------------------
# Exercise (카탈로그) - 읽기 전용 + 드릴다운
# ------------------------------
class ExerciseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Exercise.objects.all()
    serializer_class = ExerciseSerializer
    permission_classes = [permissions.IsAuthenticated]

    # ?target=chest 로 필터
    def get_queryset(self):
        qs = super().get_queryset()
        target = self.request.query_params.get("target")
        if target:
            qs = qs.filter(target=target)
        return qs.order_by("name")

    # /exercises/targets/  → ["chest","back","legs",...]
    @action(detail=False, methods=["get"], url_path="targets")
    def targets(self, request):
        targets = (
            Exercise.objects.order_by("target")
            .values_list("target", flat=True)
            .distinct()
        )
        return Response(list(targets))


# ------------------------------
# WorkoutPlan
# - 소유자만 접근
# - 날짜 필터: plan.date / plan.log_date / logs.date / logs.log_date / created_at__date 순으로 시도
# - 자기/AI 회고, AI 생성 반영
# ------------------------------
class WorkoutPlanViewSet(viewsets.ModelViewSet):
    queryset = WorkoutPlan.objects.all()
    serializer_class = WorkoutPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_value_regex = r"\d+"  # pk를 숫자로 제한 → 액션 경로 pk 오인 방지
    ordering = ("-id",)

    # date/log_date 둘 다 허용
    def _get_date_param(self):
        qp = self.request.query_params
        return qp.get("log_date") or qp.get("date")

    def _with_date_filter(self, qs):
        """여러 후보 경로로 날짜 필터링. 첫 번째로 결과가 있는 조건을 사용."""
        d = self._get_date_param()
        if not d:
            return qs
        tried = []

        # 모델 필드 존재 시도
        if _has_field(WorkoutPlan, "date"):
            tried.append(Q(date=d))
        if _has_field(WorkoutPlan, "log_date"):
            tried.append(Q(log_date=d))

        # WorkoutLog가 있고 해당 필드가 있으면 시도
        if HAS_WORKOUT_LOG:
            if _has_field(WorkoutLog, "date"):
                tried.append(Q(workout_logs__date=d))
            if _has_field(WorkoutLog, "log_date"):
                tried.append(Q(workout_logs__log_date=d))

        # 마지막으로 생성일의 날짜 부분
        tried.append(Q(created_at__date=d))

        # 첫 번째로 결과가 존재하는 조건 채택
        for cond in tried:
            tmp = qs.filter(cond).distinct()
            if tmp.exists():
                return tmp
        return qs.none()

    def get_queryset(self):
        qs = WorkoutPlan.objects.filter(user=self.request.user)
        # 목록에서도 ?date= / ?log_date= 허용
        qs = self._with_date_filter(qs)
        return qs.order_by(*self.ordering)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # GET /workoutplans/by-date/?date=YYYY-MM-DD (또는 log_date=)
    @action(detail=False, methods=["get"], url_path="by-date")
    def by_date(self, request):
        d = self._get_date_param()
        if not d:
            return Response({"detail": "date=YYYY-MM-DD 쿼리 파라미터가 필요합니다."}, status=400)
        plans = self.get_queryset().order_by("id")
        ser = self.get_serializer(plans, many=True)
        return Response(ser.data)

    # GET /workoutplans/today
    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        today_ = date.today()
        # today는 created_at__date 우선 사용
        plan = (
            WorkoutPlan.objects.filter(user=request.user, created_at__date=today_)
            .order_by("-created_at", "-id")
            .first()
        )
        if not plan:
            raise NotFound("오늘 플랜이 없습니다.")
        return Response(self.get_serializer(plan).data)

    # POST /workoutplans/today/ensure/
    @action(detail=False, methods=["post"], url_path="today/ensure")
    def ensure_today(self, request):
        today_ = date.today()
        qs = WorkoutPlan.objects.filter(user=request.user, created_at__date=today_).order_by("-id")
        plan = qs.first()
        created = False
        if not plan:
            plan = WorkoutPlan.objects.create(
                user=request.user,
                title=f"{today_.isoformat()} Workout",
                description="",
                summary="",
                target_focus=request.data.get("target_focus", ""),
                source=WorkoutPlan.PlanSource.MANUAL,
            )
            created = True
        ser = self.get_serializer(plan)
        return Response(ser.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    # POST /workoutplans/{id}/self-feedback/
    @action(detail=True, methods=["post"], url_path="self-feedback")
    def self_feedback(self, request, pk=None):
        plan = self.get_object()
        txt = (request.data.get("text") or "").strip()
        plan.description = txt
        plan.save(update_fields=["description", "updated_at"])
        return Response({"ok": True, "description": plan.description})

    # POST /workoutplans/{id}/ai-feedback/
    @action(detail=True, methods=["post"], url_path="ai-feedback")
    def ai_feedback(self, request, pk=None):
        plan = self.get_object()
        summary = (request.data.get("summary") or "").strip()
        meta = request.data.get("meta")
        plan.summary = summary
        if meta is not None:
            plan.ai_response = meta
        plan.last_synced_at = None
        plan.save(update_fields=["summary", "ai_response", "updated_at", "last_synced_at"])
        return Response({"ok": True, "summary": plan.summary, "ai_response": plan.ai_response})

    # POST /workoutplans/{id}/generate-ai/
    @action(detail=True, methods=["post"], url_path="generate-ai")
    def generate_ai(self, request, pk=None):
        plan = self.get_object()
        data = request.data or {}
        plan.title = data.get("title", plan.title)
        plan.target_focus = data.get("target_focus", plan.target_focus)

        ai = data.get("ai") or {}
        plan.source = WorkoutPlan.PlanSource.AI_INITIAL
        plan.ai_model = ai.get("model", "")
        plan.ai_version = ai.get("version", "")
        plan.ai_prompt = ai.get("prompt", "")
        plan.ai_response = ai.get("response")
        plan.ai_confidence = ai.get("confidence")
        plan.save()

        created = []
        for t in data.get("tasks") or []:
            ex_id = t.get("exercise")
            if not ex_id:
                continue
            intensity_value = t.get("intensity") or TaskItem.IntensityLevel.MEDIUM
            if intensity_value == "mid":
                intensity_value = TaskItem.IntensityLevel.MEDIUM

            created.append(
                TaskItem.objects.create(
                    workout_plan=plan,
                    exercise_id=ex_id,
                    duration_min=t.get("duration_min") or 0,
                    target_sets=t.get("target_sets"),
                    target_reps=t.get("target_reps"),
                    intensity=intensity_value,
                    notes=t.get("notes") or "",
                    is_ai_recommended=True,
                    ai_goal=t.get("ai_goal") or "",
                    ai_metadata=t.get("ai_metadata"),
                    recommended_weight_range=t.get("recommended_weight_range") or "",
                    order=t.get("order") or 1,
                )
            )
        return Response(
            {
                "ok": True,
                "plan": WorkoutPlanSerializer(plan, context={"request": request}).data,
                "created_tasks": TaskItemSerializer(created, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    # POST /workoutplans/copy_week/?source_start=YYYY-MM-DD&target_start=YYYY-MM-DD&overwrite=true|false
    @action(detail=False, methods=["post"], url_path="copy_week")
    def copy_week(self, request):
        """
        기준 주(월~일)의 계획/할일(TaskItem)을 타깃 주로 복제.
        WorkoutPlan.created_at의 '날짜' 기준으로 동작 (date 필드 없이 사용 가능)
        - source_start: YYYY-MM-DD (옵션, 기본: 이번 주 월요일)
        - target_start: YYYY-MM-DD (옵션, 기본: source_start + 7일)
        - overwrite: true/false (옵션, 기본 false)
        """
        import datetime
        from django.core.exceptions import FieldError

        user = request.user
        q = request.query_params
        overwrite = (q.get("overwrite") or "false").lower() == "true"

        try:
            # 파라미터 파싱
            if q.get("source_start"):
                src0 = monday_of(datetime.date.fromisoformat(q["source_start"]))
            else:
                src0 = monday_of(date.today())

            if q.get("target_start"):
                tgt0 = monday_of(datetime.date.fromisoformat(q["target_start"]))
            else:
                tgt0 = src0 + timedelta(days=7)

            src_days = [src0 + timedelta(days=i) for i in range(7)]
            tgt_days = [tgt0 + timedelta(days=i) for i in range(7)]

            # 소스 주 플랜 수집: created_at__date 기준
            src_plans = (
                WorkoutPlan.objects.filter(user=user)
                .filter(created_at__date__range=(src0, src0 + timedelta(days=6)))
                .order_by("created_at", "id")
            )

            # 같은 날짜의 최신 플랜으로 매핑
            src_map = {}
            for p in src_plans:
                d = p.created_at.date()
                src_map[d] = p

            created_plans = 0
            created_items = 0
            skipped_days = []
            overwritten_days = []

            with transaction.atomic():
                for src_day, tgt_day in zip(src_days, tgt_days):
                    src_plan = src_map.get(src_day)
                    if not src_plan:
                        skipped_days.append(tgt_day.isoformat())
                        continue

                    # 타깃 날짜 플랜 탐색
                    tgt_plan = (
                        WorkoutPlan.objects.filter(user=user)
                        .filter(created_at__date=tgt_day)
                        .order_by("-created_at", "-id")
                        .first()
                    )

                    if not tgt_plan:
                        base_title = src_plan.title or f"{src_day.isoformat()} Workout"
                        tgt_plan = WorkoutPlan.objects.create(
                            user=user,
                            title=f"{tgt_day.isoformat()} {base_title}",
                            description="",
                            summary="",
                            target_focus=getattr(src_plan, "target_focus", ""),
                            source=getattr(src_plan, "source", WorkoutPlan.PlanSource.MANUAL),
                        )
                        created_plans += 1
                    else:
                        if not overwrite and TaskItem.objects.filter(workout_plan=tgt_plan).exists():
                            skipped_days.append(tgt_day.isoformat())
                            continue
                        if overwrite:
                            TaskItem.objects.filter(workout_plan=tgt_plan).delete()
                            overwritten_days.append(tgt_day.isoformat())

                    # --- 소스 아이템 복제 ---
                    src_items = (
                        TaskItem.objects.select_related("exercise")
                        .filter(workout_plan=src_plan)
                        .order_by("order", "id")
                    )

                    if not src_items.exists():
                        skipped_days.append(tgt_day.isoformat())
                        continue

                    # 모델 필드 존재 집합
                    taskitem_fields = {f.name for f in TaskItem._meta.get_fields()}

                    clones = []
                    for it in src_items:
                        attrs = {
                            "workout_plan": tgt_plan,
                            "exercise": it.exercise,
                            "duration_min": it.duration_min,
                            "target_sets": getattr(it, "target_sets", None),
                            "target_reps": getattr(it, "target_reps", None),
                            "intensity": getattr(it, "intensity", None),
                            "notes": getattr(it, "notes", ""),
                            "is_ai_recommended": getattr(it, "is_ai_recommended", False),
                            "ai_goal": getattr(it, "ai_goal", ""),
                            "ai_metadata": getattr(it, "ai_metadata", None),
                            "recommended_weight_range": getattr(it, "recommended_weight_range", ""),
                            "order": (it.order or 1),
                        }

                        # 모델에 해당 필드가 있을 때만 초기화
                        if "completed" in taskitem_fields:
                            attrs["completed"] = False
                        if "skipped" in taskitem_fields:
                            attrs["skipped"] = False
                        if "skip_reason" in taskitem_fields:
                            attrs["skip_reason"] = None
                        if "completed_at" in taskitem_fields:
                            attrs["completed_at"] = None

                        clones.append(TaskItem(**attrs))

                    TaskItem.objects.bulk_create(clones)
                    created_items += len(clones)

            return Response({
                "source_week": {"start": src0.isoformat(), "end": (src0 + timedelta(days=6)).isoformat()},
                "target_week": {"start": tgt0.isoformat(), "end": (tgt0 + timedelta(days=6)).isoformat()},
                "created_plans": created_plans,
                "created_items": created_items,
                "skipped_days": skipped_days,
                "overwritten_days": overwritten_days,
                "overwrite": overwrite,
            }, status=status.HTTP_200_OK)

        except FieldError as e:
            return Response({"detail": f"invalid field usage: {e}"}, status=400)
        except Exception as e:
            return Response({"detail": f"copy_week failed: {e}"}, status=500)


# ------------------------------
# TaskItem - 계획 내 운동 항목 (+ 완료/스킵 토글)
# ------------------------------
class TaskItemViewSet(viewsets.ModelViewSet):
    queryset = TaskItem.objects.select_related("workout_plan", "exercise").all()
    serializer_class = TaskItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_value_regex = r"\d+"  # pk 숫자 제한
    ordering = ("-id",)

    def get_queryset(self):
        qs = TaskItem.objects.select_related("workout_plan", "exercise").filter(
            workout_plan__user=self.request.user
        )
        # 주간 집계와 일관성 위해 ?date 필터도 허용
        d = self.request.query_params.get("date") or self.request.query_params.get("log_date")
        if d:
            qs = qs.filter(workout_plan__created_at__date=d)
        return qs.order_by(*self.ordering)

    def perform_create(self, serializer):
        plan = serializer.validated_data.get("workout_plan")
        if plan.user_id != self.request.user.id:
            raise PermissionDenied("다른 사용자의 계획에는 항목을 추가할 수 없습니다.")
        serializer.save()

    def perform_update(self, serializer):
        instance_plan = serializer.instance.workout_plan
        if instance_plan.user_id != self.request.user.id:
            raise PermissionDenied("다른 사용자의 항목은 수정할 수 없습니다.")
        new_plan = serializer.validated_data.get("workout_plan", instance_plan)
        if new_plan.user_id != self.request.user.id:
            raise PermissionDenied("다른 사용자의 계획으로 이동할 수 없습니다.")
        serializer.save()

    # ✅ POST /taskitems/{id}/toggle-complete/
    # body: {"value": true|false}
    @action(detail=True, methods=["post"], url_path="toggle-complete")
    def toggle_complete(self, request, pk=None):
        ti = self.get_object()
        if ti.workout_plan.user_id != request.user.id:
            raise PermissionDenied("다른 사용자의 항목입니다.")

        field_names = {f.name for f in TaskItem._meta.get_fields()}
        if "completed" not in field_names or "completed_at" not in field_names or "skipped" not in field_names:
            return Response(
                {"detail": "TaskItem 모델에 completed/completed_at/skipped 필드가 필요합니다. 마이그레이션을 적용해주세요."},
                status=400,
            )

        val = request.data.get("value")
        new_val = True if val in (True, "true", "True", 1, "1") else False

        ti.completed = new_val
        ti.completed_at = timezone.now() if new_val else None
        if new_val:
            # 완료되면 스킵 해제
            ti.skipped = False
            if "skip_reason" in field_names:
                ti.skip_reason = None
        ti.save(update_fields=["completed", "completed_at", "skipped", "updated_at"] if "updated_at" in field_names else ["completed", "completed_at", "skipped"])
        return Response({"ok": True, "id": ti.id, "completed": ti.completed, "completed_at": ti.completed_at})

    # ✅ POST /taskitems/{id}/toggle-skip/
    # body: {"value": true|false, "reason": "optional text"}
    @action(detail=True, methods=["post"], url_path="toggle-skip")
    def toggle_skip(self, request, pk=None):
        ti = self.get_object()
        if ti.workout_plan.user_id != request.user.id:
            raise PermissionDenied("다른 사용자의 항목입니다.")

        field_names = {f.name for f in TaskItem._meta.get_fields()}
        if "skipped" not in field_names:
            return Response({"detail": "TaskItem 모델에 skipped 필드가 필요합니다. 마이그레이션을 적용해주세요."}, status=400)

        val = request.data.get("value")
        new_val = True if val in (True, "true", "True", 1, "1") else False
        reason = (request.data.get("reason") or "").strip()

        ti.skipped = new_val
        # 스킵하면 완료 해제
        if "completed" in field_names:
            ti.completed = False
        if "completed_at" in field_names:
            ti.completed_at = None
        if "skip_reason" in field_names:
            ti.skip_reason = reason if new_val else None

        update_fields = ["skipped"]
        if "completed" in field_names:
            update_fields.append("completed")
        if "completed_at" in field_names:
            update_fields.append("completed_at")
        if "skip_reason" in field_names:
            update_fields.append("skip_reason")
        if "updated_at" in field_names:
            update_fields.append("updated_at")

        ti.save(update_fields=update_fields)
        return Response({
            "ok": True,
            "id": ti.id,
            "skipped": ti.skipped,
            "skip_reason": getattr(ti, "skip_reason", None),
        })

    # GET /taskitems/weekly_progress/?start=YYYY-MM-DD
    @action(detail=False, methods=["get"], url_path="weekly_progress")
    def weekly_progress(self, request):
        """
        주간 TaskItem 집계 + 간단 피드백.
        ?start=YYYY-MM-DD (옵션, 기본: 이번 주 월요일)
        WorkoutPlan.created_at의 '날짜' 기준으로 필터링 (date 필드 없이 동작)
        데이터가 없어도 200 OK와 빈 집계를 반환.
        """
        import datetime
        start_q = request.query_params.get("start")
        if start_q:
            start = monday_of(datetime.date.fromisoformat(start_q))
        else:
            start = monday_of(date.today())
        end = start + timedelta(days=6)

        # Datetime → Date 비교 (__date 룩업)
        items = self.get_queryset().filter(
            workout_plan__created_at__date__range=(start, end)
        )

        total = items.count()

        # 필드 존재 여부에 따른 안전 카운트
        field_names = {f.name for f in TaskItem._meta.get_fields()}
        has_completed = "completed" in field_names
        has_skipped = "skipped" in field_names

        done = items.filter(completed=True).count() if has_completed else 0
        skipped = items.filter(skipped=True).count() if has_skipped else 0
        rate = (done / total * 100.0) if total else 0.0

        # 일자별 완료 여부 계산
        day_has_done = {start + timedelta(days=i): False for i in range(7)}
        if total:
            if has_completed:
                qs = items.values_list("workout_plan__created_at", "completed")
                for dt, c in qs:
                    d = dt.date()
                    if start <= d <= end and c:
                        day_has_done[d] = True
            else:
                qs = items.values_list("workout_plan__created_at", flat=True)
                for dt in qs:
                    d = dt.date()
                    if start <= d <= end:
                        day_has_done[d] = True

        # best streak 계산
        cur = best = 0
        for i in range(7):
            d = start + timedelta(days=i)
            if day_has_done.get(d, False):
                cur += 1
                best = max(best, cur)
            else:
                cur = 0

        if rate >= 80:
            feedback = "아주 좋아요! 이번 주 루틴을 안정적으로 유지했어요. 다음 주엔 난이도를 살짝 올려볼까요?"
        elif rate >= 50:
            feedback = "절반 정도 달성! 일정/난이도 재조정이 필요해 보여요. 스킵 사유를 기록해 패턴을 찾아봐요."
        else:
            feedback = "이번 주는 어려웠네요. 세션 수를 줄이거나 시간대를 바꿔보는 것을 권장해요."

        return Response({
            "week": {"start": start.isoformat(), "end": end.isoformat()},
            "tasks": {"total": total, "completed": done, "skipped": skipped, "completion_rate": round(rate, 1)},
            "streak": {"best_in_week": best},
            "feedback": feedback,
        }, status=status.HTTP_200_OK)


# ------------------------------
# WorkoutLog (선택) - user 기준 필터/주입
# ------------------------------
if HAS_WORKOUT_LOG:

    class WorkoutLogViewSet(viewsets.ModelViewSet):
        queryset = WorkoutLog.objects.all()
        serializer_class = WorkoutLogSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            return WorkoutLog.objects.filter(user=self.request.user)

        def perform_create(self, serializer):
            ti = serializer.validated_data.get("task_item")
            if ti is not None and getattr(ti.workout_plan, "user_id", None) != self.request.user.id:
                raise PermissionDenied("다른 사용자의 계획/항목에 로그를 추가할 수 없습니다.")
            serializer.save(user=self.request.user)


# ------------------------------
# Fixtures → 간단 JSON으로 노출 (프런트 시드용)
# GET /api/fixtures/exercises/
# ------------------------------
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def fixtures_exercises(request):
    """
    tasks/fixtures/exercise.json 또는 exercises.json 을 읽어
    [{id, name, target, ...}, ...] 형태로 반환
    """
    base = Path(__file__).resolve().parent
    candidates = [
        base / "fixtures" / "exercise.json",
        base / "fixtures" / "exercises.json",
    ]
    fixture_path = next((p for p in candidates if p.exists()), None)
    if not fixture_path:
        return Response({"detail": "fixture not found (exercise[s].json)"}, status=404)

    try:
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    except Exception as e:
        return Response({"detail": f"fixture read error: {e}"}, status=400)

    out = []
    for rec in raw if isinstance(raw, list) else []:
        if str(rec.get("model", "")).endswith("exercise"):
            pk = rec.get("pk")
            fields = rec.get("fields", {}) or {}
            out.append({"id": pk, **fields})
    return Response(out)


# ------------------------------
# 템플릿 뷰 (대시보드/워크아웃/밀)
# ------------------------------
@ensure_csrf_cookie
@login_required
def dashboard(request):
    """템플릿 대시보드"""
    total_minutes = 0
    if HAS_WORKOUT_LOG:
        total_minutes = (
            WorkoutLog.objects.filter(user=request.user)
            .aggregate(Sum("duration_min"))["duration_min__sum"]
            or 0
        )

    summary = {
        "total_minutes": total_minutes,
        "recommended_intensity": "Medium",
        "active_plans": WorkoutPlan.objects.filter(user=request.user).count(),
    }

    # 가장 최근 플랜(생성일 기준) 항목 상위 4개 추천
    recent_plan = (
        WorkoutPlan.objects.filter(user=request.user)
        .order_by("-created_at", "-id")
        .first()
    )
    recommendations = (
        TaskItem.objects.filter(workout_plan__user=request.user, workout_plan=recent_plan)
        .select_related("exercise")
        .order_by("order", "id")[:4]
        if recent_plan
        else TaskItem.objects.none()
    )

    daily_tasks = [
        {
            "id": ti.id,
            "text": (
                f"{ti.exercise.name} "
                f"{(str(ti.target_sets)+'x'+str(ti.target_reps)) if (ti.target_sets and ti.target_reps) else ''}"
            ).strip(),
            "completed": False,
            "type": "workout",
        }
        for ti in recommendations
    ]
    if not daily_tasks:
        daily_tasks = [
            {"id": "water", "text": "Drink 8 glasses of water", "completed": False, "type": "water"},
            {"id": "sleep", "text": "Get 7+ hours sleep", "completed": True, "type": "sleep"},
            {"id": "meal", "text": "Log breakfast calories", "completed": True, "type": "meal"},
        ]

    completed_count = sum(1 for task in daily_tasks if task["completed"])
    total_tasks = len(daily_tasks)
    progress_complete = int(round(completed_count / total_tasks * 100)) if total_tasks else 0

    ai_insights = [
        {"id": "progress", "type": "success", "title": "Great Progress!", "message": "Your strength sessions were consistent. Keep it up with steady increments.", "confidence": 94},
        {"id": "tip", "type": "info", "title": "Optimization Tip", "message": "마지막 세트는 1~2회 RIR(여유 반복 수) 남기고 마무리해보세요.", "confidence": 87},
    ]

    progress_cards = [
        {"label": "Workouts", "value": f"{completed_count}/{total_tasks}", "render_value": f"{completed_count}/{total_tasks}", "render_percent": progress_complete, "progress": progress_complete, "color": "secondary"},
    ]

    return render(
        request,
        "tasks/dashboard.html",
        {
            "summary": summary,
            "recommendations": recommendations,
            "daily_tasks": daily_tasks,
            "ai_insights": ai_insights,
            "progress_cards": progress_cards,
            "quick_actions": [
                {"icon": "zap", "title": "Start Workout", "caption": "Begin today's training", "url": reverse("tasks:workouts"), "variant": "primary"},
                {"icon": "camera", "title": "Log Meal", "caption": "Take a photo", "url": reverse("tasks:meals"), "variant": "secondary"},
                {"icon": "trend", "title": "View Progress", "caption": "Check your stats", "url": "#progress", "variant": "coral"},
                {"icon": "target", "title": "Set Goals", "caption": "Update targets", "url": "#goal", "variant": "purple"},
            ],
            "ai_loading": False,
            "progress_complete": progress_complete,
            "progress_total": total_tasks,
            "progress_done": completed_count,
        },
    )


@ensure_csrf_cookie
@login_required
def workouts(request):
    week_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    workouts_plan = [
        {
            'id': '1',
            'name': 'Upper Body Strength',
            'type': 'strength',
            'duration': 45,
            'difficulty': 'intermediate',
            'completed': True,
            'exercises': [
                {'id': '1', 'name': 'Bench Press', 'sets': 3, 'reps': 10},
                {'id': '2', 'name': 'Barbell Row', 'sets': 3, 'reps': 8},
                {'id': '3', 'name': 'Overhead Press', 'sets': 3, 'reps': 10},
            ],
        },
    ]
    return render(
        request,
        'tasks/workouts.html',
        {'week_days': week_days, 'workouts_plan': workouts_plan},
    )


@ensure_csrf_cookie
@login_required
def meals(request):
    # 템플릿 데모용
    nutrition_goals = {"calories": 2200, "protein": 150, "carbs": 220, "fat": 80}
    todays_meals = [
        {"id": "1", "name": "Protein Overnight Oats", "type": "breakfast", "calories": 420, "protein": 25, "carbs": 45, "fat": 12,
         "image": "https://images.unsplash.com/photo-1571091718767-18b5b1457add?w=400&h=300&fit=crop", "ai_generated": True},
        {"id": "2", "name": "Grilled Chicken Quinoa Bowl", "type": "lunch", "calories": 550, "protein": 45, "carbs": 40, "fat": 18,
         "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400&h=300&fit=crop", "ai_generated": True},
    ]

    def pct(cur, goal):
        return min(int(round(cur / goal * 100)) if goal else 0, 100)

    consumed = {
        "calories": sum(m["calories"] for m in todays_meals),
        "protein": sum(m["protein"] for m in todays_meals),
        "carbs": sum(m["carbs"] for m in todays_meals),
        "fat": sum(m["fat"] for m in todays_meals),
    }

    nutrition_summary = [
        {"label": "Calories", "current": consumed["calories"], "goal": nutrition_goals["calories"], "color": "primary", "unit": "cal", "progress": pct(consumed["calories"], nutrition_goals["calories"])},
        {"label": "Protein", "current": consumed["protein"], "goal": nutrition_goals["protein"], "color": "success", "unit": "g", "progress": pct(consumed["protein"], nutrition_goals["protein"])},
        {"label": "Carbs", "current": consumed["carbs"], "goal": nutrition_goals["carbs"], "color": "warning", "unit": "g", "progress": pct(consumed["carbs"], nutrition_goals["carbs"])},
        {"label": "Fat", "current": consumed["fat"], "goal": nutrition_goals["fat"], "color": "secondary", "unit": "g", "progress": pct(consumed["fat"], nutrition_goals["fat"])},
    ]

    ai_feedback_cards = [
        {"type": "suggestion", "message": "You're 300 calories below your goal. Consider adding a protein-rich snack to reach your targets."}
    ]
    ai_recommendations = [
        {"title": "🥗 Dinner Suggestion", "message": "Based on your remaining calories and macros, try a salmon and sweet potato dish.", "button": "View Recipe"},
        {"type": "achievement", "message": "Great protein intake today! You're 90% towards your protein goal."},
    ]

    return render(
        request,
        'tasks/meals.html',
        {
            "nutrition_summary": nutrition_summary,
            "todays_meals": todays_meals,
            "nutrition_goals": nutrition_goals,
            "ai_feedback_cards": ai_feedback_cards,
            "ai_recommendations": ai_recommendations,
        },
    )
