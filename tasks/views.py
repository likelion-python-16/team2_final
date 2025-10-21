# tasks/views.py
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import json
from typing import Optional

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.exceptions import FieldError
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
from rest_framework.filters import OrderingFilter

from .models import Exercise, WorkoutPlan, TaskItem

# 선택: 인테이크 모델 존재 시 사용
try:
    from intakes.models import NutritionLog, MealItem
    HAS_INTAKE_MODELS = True
except Exception:
    NutritionLog = None
    MealItem = None
    HAS_INTAKE_MODELS = False

# WorkoutLog 모델이 있으면 사용
try:
    from .models import WorkoutLog
    HAS_WORKOUT_LOG = True
except Exception:
    HAS_WORKOUT_LOG = False

from .serializers import ExerciseSerializer, WorkoutPlanSerializer, TaskItemSerializer
if HAS_WORKOUT_LOG:
    from .serializers import WorkoutLogSerializer


# ----------------------------------------------------------------------
# 유틸
# ----------------------------------------------------------------------
def monday_of(d: date) -> date:
    """ISO Monday(1) 기준: 해당 날짜가 속한 주의 월요일을 반환."""
    return d - timedelta(days=d.isoweekday() - 1)


def _has_field(model_cls, field_name: str) -> bool:
    try:
        model_cls._meta.get_field(field_name)
        return True
    except Exception:
        return False


def parse_iso_date(s: Optional[str]) -> Optional[date]:
    """YYYY-MM-DD 형식만 허용. 잘못되면 None 반환."""
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


# ----------------------------------------------------------------------
# Exercise (카탈로그) - 읽기 전용 + 드릴다운
# ----------------------------------------------------------------------
class ExerciseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Exercise.objects.all().order_by("name")
    serializer_class = ExerciseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ("name", "target")

    def get_queryset(self):
        qs = Exercise.objects.all()
        target = self.request.query_params.get("target")
        if target:
            qs = qs.filter(target=target)
        return qs.order_by("name")

    # /exercises/targets/  → ["chest","back","legs",...]
    @action(detail=False, methods=["get"], url_path="targets")
    def targets(self, request):
        targets = (
            Exercise.objects.exclude(target__isnull=True)
            .exclude(target__exact="")
            .order_by("target")
            .values_list("target", flat=True)
            .distinct()
        )
        return Response(list(targets))


# ----------------------------------------------------------------------
# WorkoutPlan - 소유자 전용
# - 날짜 필터: plan.date / plan.log_date / created_at__date 순으로 시도
# ----------------------------------------------------------------------
class WorkoutPlanViewSet(viewsets.ModelViewSet):
    queryset = WorkoutPlan.objects.all()
    serializer_class = WorkoutPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_value_regex = r"\d+"  # pk 숫자 제한
    ordering = ("-id",)
    filter_backends = [OrderingFilter]
    ordering_fields = ("id", "created_at")

    def _get_date_param(self) -> Optional[date]:
        qp = self.request.query_params
        return parse_iso_date(qp.get("log_date") or qp.get("date"))

    def _with_date_filter(self, qs):
        """여러 후보 경로로 날짜 필터링. 첫 매칭 전략 사용."""
        d = self._get_date_param()
        if not d:
            return qs

        tried = []
        if _has_field(WorkoutPlan, "date"):
            tried.append(Q(date=d))
        if _has_field(WorkoutPlan, "log_date"):
            tried.append(Q(log_date=d))
        tried.append(Q(created_at__date=d))

        for cond in tried:
            try:
                tmp = qs.filter(cond).distinct()
            except FieldError:
                continue
            if tmp.exists():
                return tmp
        return qs.none()

    def get_queryset(self):
        qs = WorkoutPlan.objects.filter(user=self.request.user)
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
        base = WorkoutPlan.objects.filter(user=request.user)
        
        # 1차: 기본 전략
        qs1 = self._with_date_filter(base)
        debug = {
            "requested_date": d.isoformat(),
            "server_now": timezone.now().isoformat(),
            "server_today": timezone.localdate().isoformat(),
            "match1_count": qs1.count(),
        }
        qs = qs1
        match_strategy = "primary"
        # 2차: created_at__date in {d-1, d, d+1}
        if not qs.exists():
            from datetime import timedelta as _td
            around = [d - _td(days=1), d, d + _td(days=1)]
            qs2 = base.filter(created_at__date__in=around).order_by("id")
            debug.update({"match2_candidates": [x.isoformat() for x in around], "match2_count": qs2.count()})
            if qs2.exists():
                qs = qs2
                match_strategy = "around"
        # 3차: 최신 1건 폴백
        if not qs.exists():
            qs3 = base.order_by("-created_at", "-id")[:1]
            debug["match3_count"] = qs3.count()
            qs = qs3
            match_strategy = "latest"

        data = self.get_serializer(qs, many=True).data
        if request.query_params.get("debug") == "1":
            return Response({"data": data, "debug": debug, "strategy": match_strategy})
        return Response(data)

    # GET /workoutplans/today
    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        today_ = timezone.localdate()
        plan = (
            WorkoutPlan.objects.filter(user=request.user, created_at__date=today_)
            .order_by("-created_at", "-id")
            .first()
        )
        if not plan:
            raise NotFound("오늘 플랜이 없습니다.")
        return Response(self.get_serializer(plan).data)

    # POST /workoutplans/today/ensure/  → 멱등 보장
    @action(detail=False, methods=["post"], url_path="today/ensure")
    def ensure_today(self, request):
        today_ = timezone.localdate()
        plan = (
            WorkoutPlan.objects.filter(user=request.user, created_at__date=today_)
            .order_by("-created_at", "-id")
            .first()
        )
        created = False

        if not plan:
            defaults = {
                "title": f"{today_.isoformat()} Workout",
                "description": "",
                "summary": "",
                "target_focus": request.data.get("target_focus", ""),
                "source": getattr(getattr(WorkoutPlan, "PlanSource", None), "MANUAL", None)
                          or getattr(WorkoutPlan, "PlanSource", None)
                          or None,
            }
            plan = WorkoutPlan.objects.create(user=request.user, **defaults)
            created = True

            # 모델에 date 필드가 있으면 '오늘' 기록 (시차 예방)
            if _has_field(WorkoutPlan, "date"):
                plan.date = today_
                plan.save(update_fields=["date"] + (["updated_at"] if _has_field(WorkoutPlan, "updated_at") else []))

        ser = self.get_serializer(plan)
        return Response(ser.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    # POST /workoutplans/{id}/self-feedback/
    @action(detail=True, methods=["post"], url_path="self-feedback")
    def self_feedback(self, request, pk=None):
        plan = self.get_object()
        txt = (request.data.get("text") or "").strip()
        plan.description = txt
        update_fields = ["description"]
        if _has_field(WorkoutPlan, "updated_at"):
            update_fields.append("updated_at")
        plan.save(update_fields=update_fields)
        return Response({"ok": True, "description": plan.description})

    # POST /workoutplans/{id}/ai-feedback/
    @action(detail=True, methods=["post"], url_path="ai-feedback")
    def ai_feedback(self, request, pk=None):
        plan = self.get_object()
        summary = (request.data.get("summary") or "").strip()
        meta = request.data.get("meta")
        plan.summary = summary
        if meta is not None and _has_field(WorkoutPlan, "ai_response"):
            plan.ai_response = meta
        if _has_field(WorkoutPlan, "last_synced_at"):
            plan.last_synced_at = None
        update_fields = ["summary"]
        if _has_field(WorkoutPlan, "ai_response"):
            update_fields.append("ai_response")
        if _has_field(WorkoutPlan, "last_synced_at"):
            update_fields.append("last_synced_at")
        if _has_field(WorkoutPlan, "updated_at"):
            update_fields.append("updated_at")
        plan.save(update_fields=update_fields)
        payload = {"ok": True, "summary": plan.summary}
        if _has_field(WorkoutPlan, "ai_response"):
            payload["ai_response"] = getattr(plan, "ai_response", None)
        return Response(payload)

    # POST /workoutplans/{id}/generate-ai/
    @action(detail=True, methods=["post"], url_path="generate-ai")
    def generate_ai(self, request, pk=None):
        plan = self.get_object()
        data = request.data or {}
        plan.title = data.get("title", plan.title)
        if _has_field(WorkoutPlan, "target_focus"):
            plan.target_focus = data.get("target_focus", getattr(plan, "target_focus", ""))

        # AI 메타 반영(필드 존재 여부 체크)
        ai = data.get("ai") or {}
        if hasattr(WorkoutPlan, "PlanSource"):
            plan.source = WorkoutPlan.PlanSource.AI_INITIAL
        for f, k in (
            ("ai_model", "model"),
            ("ai_version", "version"),
            ("ai_prompt", "prompt"),
            ("ai_response", "response"),
            ("ai_confidence", "confidence"),
        ):
            if _has_field(WorkoutPlan, f):
                setattr(plan, f, ai.get(k, getattr(plan, f, None)))
        plan.save()

        created: list[TaskItem] = []
        for t in data.get("tasks") or []:
            ex_id = t.get("exercise")
            if not ex_id:
                continue
            intensity_value = t.get("intensity") or getattr(TaskItem.IntensityLevel, "MEDIUM", "medium")
            if intensity_value == "mid":  # 호환
                intensity_value = getattr(TaskItem.IntensityLevel, "MEDIUM", "medium")

            kwargs = dict(
                workout_plan=plan,
                exercise_id=ex_id,
                duration_min=t.get("duration_min") or 0,
                target_sets=t.get("target_sets"),
                target_reps=t.get("target_reps"),
                intensity=intensity_value,
                notes=t.get("notes") or "",
                order=t.get("order") or 1,
            )
            # 선택 필드
            if _has_field(TaskItem, "is_ai_recommended"):
                kwargs["is_ai_recommended"] = True
            if _has_field(TaskItem, "ai_goal"):
                kwargs["ai_goal"] = t.get("ai_goal") or ""
            if _has_field(TaskItem, "ai_metadata"):
                kwargs["ai_metadata"] = t.get("ai_metadata")
            if _has_field(TaskItem, "recommended_weight_range"):
                kwargs["recommended_weight_range"] = t.get("recommended_weight_range") or ""

            created.append(TaskItem.objects.create(**kwargs))

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
        기준 주(월~일)의 계획/TaskItem을 타깃 주로 복제.
        WorkoutPlan.created_at의 '날짜' 기준으로 동작 (date 필드 없이 사용 가능)
        - source_start: YYYY-MM-DD (옵션, 기본: 이번 주 월요일)
        - target_start: YYYY-MM-DD (옵션, 기본: source_start + 7일)
        - overwrite: true/false (옵션, 기본 false)
        """
        user = request.user
        q = request.query_params
        overwrite = (q.get("overwrite") or "false").lower() == "true"

        src_raw = q.get("source_start")
        tgt_raw = q.get("target_start")
        src0 = monday_of(parse_iso_date(src_raw) or date.today())
        tgt0 = monday_of(parse_iso_date(tgt_raw) or (src0 + timedelta(days=7)))

        src_days = [src0 + timedelta(days=i) for i in range(7)]
        tgt_days = [tgt0 + timedelta(days=i) for i in range(7)]

        src_plans = (
            WorkoutPlan.objects.filter(user=user)
            .filter(created_at__date__range=(src0, src0 + timedelta(days=6)))
            .order_by("created_at", "id")
        )

        # 같은 날짜의 최신 플랜으로 매핑
        src_map = {}
        for p in src_plans:
            d0 = p.created_at.date()
            src_map[d0] = p

        created_plans = 0
        created_items = 0
        skipped_days: list[str] = []
        overwritten_days: list[str] = []

        try:
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
                            source=getattr(src_plan, "source", getattr(WorkoutPlan.PlanSource, "MANUAL", None)),
                        )
                        created_plans += 1
                        
                        # date 필드가 있으면 타깃 날짜로 보정
                        if _has_field(WorkoutPlan, "date"):
                            tgt_plan.date = tgt_day
                            tgt_plan.save(update_fields=["date"] + (["updated_at"] if _has_field(WorkoutPlan, "updated_at") else []))
                    
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
                            "order": (it.order or 1),
                        }
                        # AI/보조 필드
                        if "is_ai_recommended" in taskitem_fields:
                            attrs["is_ai_recommended"] = getattr(it, "is_ai_recommended", False)
                        if "ai_goal" in taskitem_fields:
                            attrs["ai_goal"] = getattr(it, "ai_goal", "")
                        if "ai_metadata" in taskitem_fields:
                            attrs["ai_metadata"] = getattr(it, "ai_metadata", None)
                        if "recommended_weight_range" in taskitem_fields:
                            attrs["recommended_weight_range"] = getattr(it, "recommended_weight_range", "")

                        # 상태 관련 필드 초기화
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


# ----------------------------------------------------------------------
# TaskItem - 계획 내 운동 항목 (+ 완료/스킵 토글, 주간 집계)
# ----------------------------------------------------------------------
class TaskItemViewSet(viewsets.ModelViewSet):
    queryset = TaskItem.objects.select_related("workout_plan", "exercise").all()
    serializer_class = TaskItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_value_regex = r"\d+"
    ordering = ("-id",)
    filter_backends = [OrderingFilter]
    ordering_fields = ("id", "order", "duration_min")

    def get_queryset(self):
        qs = (
            TaskItem.objects.select_related("workout_plan", "exercise")
            .filter(workout_plan__user=self.request.user)
        )
        d = parse_iso_date(self.request.query_params.get("date") or self.request.query_params.get("log_date"))
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
    @action(detail=True, methods=["post"], url_path="toggle-complete")
    def toggle_complete(self, request, pk=None):
        ti = self.get_object()
        if ti.workout_plan.user_id != request.user.id:
            raise PermissionDenied("다른 사용자의 항목입니다.")

        field_names = {f.name for f in TaskItem._meta.get_fields()}
        missing = [f for f in ("completed", "completed_at", "skipped") if f not in field_names]
        if missing:
            return Response(
                {"detail": f"TaskItem 모델에 {', '.join(missing)} 필드가 필요합니다. 마이그레이션을 적용해주세요."},
                status=400,
            )

        val = request.data.get("value")
        new_val = True if val in (True, "true", "True", 1, "1") else False

        ti.completed = new_val
        ti.completed_at = timezone.now() if new_val else None
        if new_val:
            ti.skipped = False
            if "skip_reason" in field_names:
                ti.skip_reason = None

        update_fields = ["completed", "completed_at", "skipped"]
        if "skip_reason" in field_names:
            update_fields.append("skip_reason")
        if "updated_at" in field_names:
            update_fields.append("updated_at")

        ti.save(update_fields=update_fields)
        return Response({"ok": True, "id": ti.id, "completed": ti.completed, "completed_at": ti.completed_at})

        # ✅ WorkoutLog 동기화 (모델 있을 때만)
        if HAS_WORKOUT_LOG:
            today_ = timezone.localdate()
            dur = int(getattr(ti, "duration_min", 0) or 0)

            if new_val:
                # 완료 → 오늘 로그 업서트
                wl, created = WorkoutLog.objects.get_or_create(
                    user=request.user,
                    task_item=ti,
                    date=today_,                      # ← 키에 date 포함 (권장)
                    defaults={"duration_min": dur},
                )
                if not created and wl.duration_min != dur:
                    wl.duration_min = dur
                    wl.save(update_fields=["duration_min"])
            else:
                # 완료 해제 → 오늘 로그만 제거(다른 날짜 보존)
                WorkoutLog.objects.filter(
                    user=request.user, task_item=ti, date=today_
                ).delete()


            # 3) (선택) DailyGoal의 workout_minutes_actual 업데이트
            try:
                from goals.models import DailyGoal
                total_min = (
                    WorkoutLog.objects
                    .filter(user=request.user, date=today_)
                    .aggregate(Sum("duration_min"))["duration_min__sum"] or 0
                )
                dg, _ = DailyGoal.objects.get_or_create(user=request.user, date=today_)
                dg.workout_minutes_actual = int(total_min)
                dg.save(update_fields=["workout_minutes_actual"])
            except Exception:
                pass

        return Response({"ok": True, "id": ti.id, "completed": ti.completed, "completed_at": ti.completed_at})
    
    # ✅ POST /taskitems/{id}/toggle-skip/
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
        WorkoutPlan.created_at의 '날짜' 기준으로 필터링.
        """
        start = monday_of(parse_iso_date(request.query_params.get("start")) or date.today())
        end = start + timedelta(days=6)

        items = self.get_queryset().filter(workout_plan__created_at__date__range=(start, end))
        total = items.count()

        field_names = {f.name for f in TaskItem._meta.get_fields()}
        has_completed = "completed" in field_names
        has_skipped = "skipped" in field_names

        done = items.filter(completed=True).count() if has_completed else 0
        skipped = items.filter(skipped=True).count() if has_skipped else 0
        rate = round((done * 100.0 / total), 1) if total else 0.0

        # 일자별 완료 여부
        day_has_done = {start + timedelta(days=i): False for i in range(7)}
        if total:
            if has_completed:
                for dt, c in items.values_list("workout_plan__created_at", "completed"):
                    d0 = dt.date()
                    if start <= d0 <= end and c:
                        day_has_done[d0] = True
            else:
                for dt in items.values_list("workout_plan__created_at", flat=True):
                    d0 = dt.date()
                    if start <= d0 <= end:
                        day_has_done[d0] = True

        # best streak
        cur = best = 0
        for i in range(7):
            d0 = start + timedelta(days=i)
            if day_has_done.get(d0, False):
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
            "tasks": {"total": total, "completed": done, "skipped": skipped, "completion_rate": rate},
            "streak": {"best_in_week": best},
            "feedback": feedback,
        }, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# WorkoutLog (선택) - user 기준 필터/주입
# ----------------------------------------------------------------------
if HAS_WORKOUT_LOG:

    class WorkoutLogViewSet(viewsets.ModelViewSet):
        queryset = WorkoutLog.objects.all()
        serializer_class = WorkoutLogSerializer
        permission_classes = [permissions.IsAuthenticated]
        filter_backends = [OrderingFilter]
        ordering_fields = ("id", "date")
        ordering = ("-id",)

        def get_queryset(self):
            return WorkoutLog.objects.filter(user=self.request.user).select_related(
                "task_item", "task_item__workout_plan", "task_item__exercise"
            )

        def perform_create(self, serializer):
            ti = serializer.validated_data.get("task_item")
            if ti is not None and getattr(ti.workout_plan, "user_id", None) != self.request.user.id:
                raise PermissionDenied("다른 사용자의 계획/항목에 로그를 추가할 수 없습니다.")
            serializer.save(user=self.request.user)


# ----------------------------------------------------------------------
# Fixtures → 간단 JSON으로 노출 (프런트 시드용)
# GET /api/fixtures/exercises/
# ----------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def fixtures_exercises(request):
    """
    tasks/fixtures/exercise.json 또는 exercises.json 을 읽어
    [{id, name, target, ...}, ...] 형태로 반환
    - 안전장치: 파일 크기 상한(약 1MB), list 스키마만 수용
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
        if fixture_path.stat().st_size > 1_000_000:
            return Response({"detail": "fixture too large (>1MB)"}, status=400)
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    except Exception as e:
        return Response({"detail": f"fixture read error: {e}"}, status=400)

    if not isinstance(raw, list):
        return Response({"detail": "fixture schema must be a JSON list"}, status=400)

    out = []
    for rec in raw:
        model_name = str(rec.get("model", "")).lower()
        if not model_name.endswith("exercise"):
            continue
        pk = rec.get("pk")
        fields = rec.get("fields", {}) or {}
        if not isinstance(fields, dict):
            continue
        out.append({"id": pk, **fields})
    return Response(out)


# ----------------------------------------------------------------------
# 템플릿 뷰 (대시보드/워크아웃/밀)
# ----------------------------------------------------------------------
@ensure_csrf_cookie
@login_required
def dashboard(request):
    """템플릿 대시보드 (프로토타입)"""
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
            {"id": "sleep", "text": "Get 7+ hours sleep", "completed": True,  "type": "sleep"},
            {"id": "meal",  "text": "Log breakfast calories",  "completed": True,  "type": "meal"},
        ]

    completed_count   = sum(1 for task in daily_tasks if task["completed"])
    total_tasks       = len(daily_tasks)
    progress_complete = int(round(completed_count / total_tasks * 100)) if total_tasks else 0

    ai_insights = [
        {"id": "progress", "type": "success", "title": "Great Progress!",  "message": "Your strength sessions were consistent. Keep it up with steady increments.", "confidence": 94},
        {"id": "tip",      "type": "info",    "title": "Optimization Tip", "message": "마지막 세트는 1~2회 RIR(여유 반복 수) 남기고 마무리해보세요.",        "confidence": 87},
    ]

    progress_cards = [
        {
            "label":          "Workouts",
            "value":          f"{completed_count}/{total_tasks}",
            "render_value":   f"{completed_count}/{total_tasks}",
            "render_percent": progress_complete,
            "progress":       progress_complete,
            "color":          "secondary",
        },
    ]

    # ====== 오늘 합계(today_totals) 주입 ======
    today = timezone.localdate()
    today_totals = {
        "workout_minutes": 0,
        "meals": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},
        "goals": {"total": 0, "completed": 0},
    }

    # 1) 운동 합계 (WorkoutLog 있을 때)
    if HAS_WORKOUT_LOG:
        wl_sum = (
            WorkoutLog.objects
            .filter(user=request.user, date=today)
            .aggregate(total=Sum("duration_min"))
            .get("total") or 0
        )
        today_totals["workout_minutes"] = int(wl_sum)
    else:
        today_totals["workout_minutes"] = 0
        
    # ✅ 폴백: WorkoutLog가 0이면, 오늘 완료된 TaskItem duration 합계로 보정
    if today_totals["workout_minutes"] == 0:
        try:
            ti_sum = (
                TaskItem.objects
                .filter(workout_plan__user=request.user,
                        workout_plan__created_at__date=today,
                        completed=True)
                .aggregate(Sum("duration_min"))["duration_min__sum"]
                or 0
            )
            today_totals["workout_minutes"] = ti_sum
        except Exception:
            pass

    # 2) 식단 합계 (NutritionLog 우선, 없으면 MealItem 대안)
    if HAS_INTAKE_MODELS:
        try:
            # ✅ NutritionLog의 합계 필드명 사용
            agg = (
                NutritionLog.objects
                .filter(user=request.user, date=today)
                .aggregate(
                    kcal=Sum("kcal_total"),
                    protein=Sum("protein_total_g"),
                    carb=Sum("carb_total_g"),
                    fat=Sum("fat_total_g"),
                )
            )
            today_totals["meals"] = {
                "calories": int(agg["kcal"] or 0),
                "protein":  int(agg["protein"] or 0),
                "carbs":    int(agg["carb"] or 0),
                "fat":      int(agg["fat"] or 0),
            }
        except Exception:
            # ✅ MealItem 폴백(필드명: kcal/protein_g/carb_g/fat_g)
            try:
                agg = (
                    MealItem.objects
                    .filter(meal__user=request.user, meal__log_date=today)
                    .aggregate(
                        kcal=Sum("kcal"),
                        protein=Sum("protein_g"),
                        carb=Sum("carb_g"),
                        fat=Sum("fat_g"),
                    )
                )
                today_totals["meals"] = {
                    "calories": int(agg["kcal"] or 0),
                    "protein":  int(agg["protein"] or 0),
                    "carbs":    int(agg["carb"] or 0),
                    "fat":      int(agg["fat"] or 0),
                }
            except Exception:
                pass

    # 3) 목표 합계 (DailyGoal 우선, 없으면 Goal 대안)
    try:
        from goals.models import DailyGoal
        q = DailyGoal.objects.filter(user=request.user, date=today)
        today_totals["goals"] = {"total": q.count(), "completed": q.filter(is_completed=True).count()}
    except Exception:
        try:
            from goals.models import Goal
            q = Goal.objects.filter(user=request.user, is_active=True)
            today_totals["goals"] = {"total": q.count(), "completed": q.filter(progress__gte=100).count()}
        except Exception:
            pass
    # ==========================================

    return render(
        request,
        "tasks/dashboard.html",
        {
            "summary":            summary,
            "recommendations":    recommendations,
            "daily_tasks":        daily_tasks,
            "ai_insights":        ai_insights,
            "progress_cards":     progress_cards,
            "quick_actions": [
                {"icon": "zap",    "title": "Start Workout", "caption": "Begin today's training", "url": reverse("tasks:workouts"), "variant": "primary"},
                {"icon": "camera", "title": "Log Meal",      "caption": "Take a photo",           "url": reverse("tasks:meals"),    "variant": "secondary"},
                {"icon": "trend",  "title": "View Progress", "caption": "Check your stats",       "url": "#progress",               "variant": "coral"},
                {"icon": "target", "title": "Set Goals",     "caption": "Update targets",         "url": "#goal",                   "variant": "purple"},
            ],
            "ai_loading":         False,
            "progress_complete":  progress_complete,
            "progress_total":     total_tasks,
            "progress_done":      completed_count,
            "today_totals":       today_totals,
        },
    )


@ensure_csrf_cookie
@login_required
def workouts(request):
    week_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    workouts_plan = [
        {
            "id":         "1",
            "name":       "Upper Body Strength",
            "type":       "strength",
            "duration":   45,
            "difficulty": "intermediate",
            "completed":  True,
            "exercises": [
                {"id": "1", "name": "Bench Press",    "sets": 3, "reps": 10},
                {"id": "2", "name": "Barbell Row",    "sets": 3, "reps": 8},
                {"id": "3", "name": "Overhead Press", "sets": 3, "reps": 10},
            ],
        },
    ]
    return render(
        request,
        "tasks/workouts.html",
        {
            "week_days":     week_days,
            "workouts_plan": workouts_plan,
        },
    )


@ensure_csrf_cookie
@login_required
def meals(request):
    # 사용자별 목표(데모 값)
    nutrition_goals = {"calories": 2200, "protein": 150, "carbs": 220, "fat": 80}
    today = timezone.localdate()

    consumed = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    meal_history = []

    if HAS_INTAKE_MODELS:
        # NutritionLog 우선, 없으면 MealItem 집계
        try:
            log = NutritionLog.objects.filter(user=request.user, date=today).first()
        except Exception:
            log = None

        if log:
            consumed = {
                "calories": float(getattr(log, "kcal_total", 0)),
                "protein":  float(getattr(log, "protein_total_g", 0)),
                "carbs":    float(getattr(log, "carb_total_g", 0)),
                "fat":      float(getattr(log, "fat_total_g", 0)),
            }
            # 상세 히스토리: NutritionLog만으로는 아이템 목록이 없으니 아래 MealItem로 보강
            items = MealItem.objects.filter(meal__user=request.user, meal__log_date=today).order_by("-id")
        else:
            items = MealItem.objects.filter(meal__user=request.user, meal__log_date=today).order_by("-id")
            def _nut(i, k): return i.resolved_nutrients().get(k, 0)
            consumed = {
                "calories": sum(_nut(i, "kcal") for i in items),
                "protein":  sum(_nut(i, "protein_g") for i in items),
                "carbs":    sum(_nut(i, "carb_g") for i in items),
                "fat":      sum(_nut(i, "fat_g") for i in items),
            }

        # 상세 히스토리
        type_class_map = {
            "아침": "breakfast", "점심": "lunch", "저녁": "dinner", "간식": "snack",
            "breakfast": "breakfast", "lunch": "lunch", "dinner": "dinner", "snack": "snack",
        }
        for item in items:
            n = item.resolved_nutrients()
            # ✅ 사진 URL
            photo_url = None
            try:
                if getattr(item, "photo", None) and item.photo:
                    photo_url = default_storage.url(item.photo.name)
            except Exception:
                photo_url = None

            meal_history.append(
                {
                    "id": item.id,
                    "meal_type": item.meal.meal_type,
                    "name": item.name or (item.food.name if item.food else "기록된 식사"),
                    "calories": round(n.get("kcal", 0) or 0, 1),
                    "protein": round(n.get("protein_g", 0) or 0, 1),
                    "carbs": round(n.get("carb_g", 0) or 0, 1),
                    "fat": round(n.get("fat_g", 0) or 0, 1),
                    "source": "AI",
                    "type_class": type_class_map.get(item.meal.meal_type, "default"),
                    "photo_url": photo_url,
                }
            )

    def pct(cur, goal):
        return min(int(round(cur / goal * 100)) if goal else 0, 100)

    consumed = {k: round(v or 0, 1) for k, v in consumed.items()}

    nutrition_summary = [
        {"label": "칼로리", "current": consumed["calories"], "goal": nutrition_goals["calories"], "color": "primary",   "unit": "kcal", "progress": pct(consumed["calories"], nutrition_goals["calories"])},
        {"label": "단백질", "current": consumed["protein"],  "goal": nutrition_goals["protein"],  "color": "success",   "unit": "g",    "progress": pct(consumed["protein"],  nutrition_goals["protein"])},
        {"label": "탄수화물","current": consumed["carbs"],   "goal": nutrition_goals["carbs"],    "color": "warning",   "unit": "g",    "progress": pct(consumed["carbs"],    nutrition_goals["carbs"])},
        {"label": "지방",   "current": consumed["fat"],      "goal": nutrition_goals["fat"],      "color": "secondary", "unit": "g",    "progress": pct(consumed["fat"],      nutrition_goals["fat"])},
    ]

    remaining = {
        "calories": max(nutrition_goals["calories"] - consumed["calories"], 0),
        "protein":  max(nutrition_goals["protein"]  - consumed["protein"],  0),
        "carbs":    max(nutrition_goals["carbs"]    - consumed["carbs"],    0),
        "fat":      max(nutrition_goals["fat"]      - consumed["fat"],      0),
    }

    remaining_cal = remaining["calories"]
    remaining_pro = remaining["protein"]

    if remaining_cal <= 0 and remaining_pro <= 0:
        feedback_message = "오늘 목표를 이미 달성했어요! 가벼운 샐러드나 수분 섭취로 마무리해 보세요."
    elif remaining_cal <= 150:
        feedback_message = "거의 다 왔어요. 저당 요거트나 삶은 달걀처럼 가벼운 단백질 간식으로 마무리하세요."
    elif remaining_pro >= 25:
        feedback_message = "단백질이 조금 부족해요. 닭가슴살 샐러드나 두부구이를 추가해 보는 건 어떨까요?"
    else:
        feedback_message = "남은 칼로리에 맞춰 견과류 + 계란 같은 간편한 스낵을 추가해 균형을 맞춰 보세요."

    ai_feedback_cards = [{"type": "suggestion", "message": feedback_message}]
    ai_recommendations = [
        {"title": "🥗 고단백 식사", "message": f"남은 단백질 {max(remaining_pro, 0):.0f}g를 채우려면 닭가슴살 + 현미밥 + 데친 채소 조합이 좋아요.", "button": "추천 레시피 보기"},
        {"title": "🍜 든든한 한 그릇", "message": "연어구이와 고구마, 시금치 나물을 곁들이면 지방을 크게 늘리지 않으면서 포만감을 채울 수 있어요."},
        {"title": "🥙 간편 옵션", "message": "그릭요거트 + 견과류 + 바나나 조합으로 300kcal 내외의 영양 간식을 준비해 보세요."},
        {"type": "achievement", "message": "단백질 섭취가 목표의 90%에 도달했어요. 저녁에 20g만 더 챙기면 완벽!"},
    ]

    return render(
        request,
        "tasks/meals.html",
        {
            "nutrition_summary":  nutrition_summary,
            "nutrition_goals":    nutrition_goals,
            "ai_feedback_cards":  ai_feedback_cards,
            "ai_recommendations": ai_recommendations,
            "remaining_macros":   remaining,
            "meal_history":       meal_history,
        },
    )
