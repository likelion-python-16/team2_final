# tasks/views.py
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
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
# - created_at.date 로 오늘/과거 조회
# - 자기/AI 회고, AI 생성 반영
# ------------------------------
class WorkoutPlanViewSet(viewsets.ModelViewSet):
    queryset = WorkoutPlan.objects.all()
    serializer_class = WorkoutPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WorkoutPlan.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # GET /workoutplans/by-date/?date=YYYY-MM-DD
    @action(detail=False, methods=["get"], url_path="by-date")
    def by_date(self, request):
        qd = request.query_params.get("date")
        if not qd:
            return Response({"detail": "date=YYYY-MM-DD 쿼리 파라미터가 필요합니다."}, status=400)
        plans = (
            self.get_queryset()
            .annotate(d=TruncDate("created_at"))
            .filter(d=qd)
            .order_by("-id")
        )
        ser = self.get_serializer(plans, many=True)
        return Response(ser.data)

    # POST /workoutplans/today/ensure/
    # 오늘자(created_at.date == today) 플랜이 없으면 생성 후 반환
    @action(detail=False, methods=["post"], url_path="today/ensure")
    def ensure_today(self, request):
        today = date.today()
        qs = (
            self.get_queryset()
            .annotate(d=TruncDate("created_at"))
            .filter(d=today)
            .order_by("-id")
        )
        plan = qs.first()
        if not plan:
            plan = WorkoutPlan.objects.create(
                user=request.user,
                title=f"{today.isoformat()} Workout",
                description="",
                summary="",
                target_focus=request.data.get("target_focus", ""),
                source=WorkoutPlan.PlanSource.MANUAL,
            )
        ser = self.get_serializer(plan)
        return Response(ser.data, status=200)

    # POST /workoutplans/{id}/self-feedback/
    # body: {"text": "..."}  → description에 저장
    @action(detail=True, methods=["post"], url_path="self-feedback")
    def self_feedback(self, request, pk=None):
        plan = self.get_object()
        txt = (request.data.get("text") or "").strip()
        plan.description = txt
        plan.save(update_fields=["description", "updated_at"])
        return Response({"ok": True, "description": plan.description})

    # POST /workoutplans/{id}/ai-feedback/
    # body: {"summary": "...", "meta": {...}} → summary/ai_response 저장
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

    # (선택) POST /workoutplans/{id}/generate-ai/
    # body:
    # {
    #   "title": "Upper Body",
    #   "target_focus": "chest,shoulders",
    #   "tasks": [
    #     {"exercise": 1, "duration_min": 0, "target_sets": 3, "target_reps": 10,
    #      "intensity":"medium","notes":"warmup","order":1}
    #   ],
    #   "ai": {"model":"gpt-x","version":"1","prompt":"...","response":{...},"confidence":0.82}
    # }
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
            created.append(
                TaskItem.objects.create(
                    workout_plan=plan,
                    exercise_id=ex_id,
                    duration_min=t.get("duration_min") or 0,
                    target_sets=t.get("target_sets"),
                    target_reps=t.get("target_reps"),
                    intensity=t.get("intensity") or TaskItem.IntensityLevel.MEDIUM,
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
            status=200,
        )


# ------------------------------
# TaskItem - 계획 내 운동 항목
#   - workout_plan__user 로 소유권 필터
#   - 생성/수정 시 계획 소유권 검사
# ------------------------------
class TaskItemViewSet(viewsets.ModelViewSet):
    queryset = TaskItem.objects.select_related("workout_plan", "exercise").all()
    serializer_class = TaskItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TaskItem.objects.select_related("workout_plan", "exercise").filter(
            workout_plan__user=self.request.user
        )

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
            # TaskItem/Plan 소유권은 자연스럽게 연결되지만, 필요하면 더 엄격히 검사 가능
            ti = serializer.validated_data.get("task_item")
            if ti is not None and getattr(ti.workout_plan, "user_id", None) != self.request.user.id:
                raise PermissionDenied("다른 사용자의 계획/항목에 로그를 추가할 수 없습니다.")
            serializer.save(user=self.request.user)


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
            "completed": False,  # 완료 체크 별도 없음 → 프론트/로그 집계로 처리
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
        "tasks/meals.html",
        {
            "nutrition_summary": nutrition_summary,
            "todays_meals": todays_meals,
            "nutrition_goals": nutrition_goals,
            "ai_feedback_cards": ai_feedback_cards,
            "ai_recommendations": ai_recommendations,
        },
    )
