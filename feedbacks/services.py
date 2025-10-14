# 중복 방지 제약이 있어도, 서비스 레벨에서 한 번 더 안전하게 처리 (동시성 대응 포함)
from datetime import date
from django.db import transaction
from django.db.models import Sum

from .models import DailyReport, Feedback

# (선택) tasks의 WorkoutLog가 있을 때만 사용
try:
    from tasks.models import WorkoutLog
    HAS_WORKOUT_LOG = True
except Exception:
    HAS_WORKOUT_LOG = False

def compute_day_totals(user, d: date):
    """대시보드용: 하루 합계(운동/식단/목표). 필요에 맞게 확장."""
    workout_minutes = 0
    if HAS_WORKOUT_LOG:
        workout_minutes = (
            WorkoutLog.objects.filter(user=user, date=d).aggregate(Sum("duration_min"))["duration_min__sum"] or 0
        )
    return {
        "workout_minutes": int(workout_minutes),
        "meals": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},  # TODO: 영양앱 연동 시 교체
        "goals": {"completed": 0, "total": 0},                          # TODO: goals 앱 연동 시 교체
    }

@transaction.atomic
def ensure_daily_report(user, d: date, *, source="user", summary=None, score=None):
    """(user, date) 1건 보장: 있으면 업데이트, 없으면 생성."""
    dr, created = DailyReport.objects.get_or_create(
        user=user, date=d,
        defaults={"source": source, "summary": summary or "", "score": score},
    )
    updates = {}
    if summary is not None and dr.summary != summary:
        updates["summary"] = summary
    if score is not None and dr.score != score:
        updates["score"] = score
    if updates:
        for k, v in updates.items():
            setattr(dr, k, v)
        dr.save(update_fields=[*updates.keys(), "updated_at"])
    return dr, created

@transaction.atomic
def ensure_ai_feedback(user, d: date, *, ai_model: str, prompt: str, response: dict,
                       summary: str = "", recommended_action: str = "", confidence: float | None = None):
    """
    '하루 1개 AI 피드백' 보장:
    - DailyReport 보장 후
    - (daily_report, source='ai') 1건 유지 (있으면 업데이트, 없으면 생성)
    """
    dr, _ = ensure_daily_report(user, d, source="ai")
    fb = (Feedback.objects
          .select_for_update()  # 동시성 안전
          .filter(user=user, daily_report=dr, source=Feedback.FeedbackSource.AI)
          .order_by("-id").first())
    if fb is None:
        fb = Feedback.objects.create(
            user=user,
            daily_report=dr,
            source=Feedback.FeedbackSource.AI,
            ai_model=ai_model,
            ai_prompt=prompt,
            ai_response=response,
            ai_confidence=confidence,
            message=response.get("message", "") if isinstance(response, dict) else "",
            summary=summary,
            recommended_action=recommended_action,
        )
    else:
        fb.ai_model = ai_model
        fb.ai_prompt = prompt
        fb.ai_response = response
        fb.ai_confidence = confidence
        if summary:
            fb.summary = summary
        if recommended_action:
            fb.recommended_action = recommended_action
        if isinstance(response, dict) and response.get("message"):
            fb.message = response["message"]
        fb.save(update_fields=[
            "ai_model", "ai_prompt", "ai_response", "ai_confidence",
            "summary", "recommended_action", "message", "updated_at",
        ])
    return fb