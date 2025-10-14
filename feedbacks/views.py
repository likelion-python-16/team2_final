# feedbacks/views.py
from datetime import date as _date
from django.db.models import Q

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound

from .models import Feedback, DailyReport, Achievement
from .serializers import FeedbackSerializer, DailyReportSerializer, AchievementSerializer

# 서비스 헬퍼 (일일 1개 보장 업서트)
from .services import ensure_daily_report, ensure_ai_feedback


class FeedbackViewSet(viewsets.ModelViewSet):
    """
    /feedbacks/           CRUD (본인 것만)
    /feedbacks/by-date/?date=YYYY-MM-DD  -> 해당 날짜 것만
    /feedbacks/ai/ensure/ (POST)         -> 하루 1개 AI 피드백 업서트
    """
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Feedback.objects.filter(user=self.request.user).order_by("-created_at", "-id")
        d = self.request.query_params.get("date")
        if d:
            # DailyReport(date=d) 또는 Feedback.created_at__date=d 로 fallback
            qs = qs.filter(Q(daily_report__date=d) | Q(created_at__date=d))
        return qs

    def perform_create(self, serializer):
        # 항상 본인 소유로 저장
        serializer.save(user=self.request.user)

    # GET /feedbacks/by-date/?date=YYYY-MM-DD
    @action(detail=False, methods=["get"], url_path="by-date")
    def by_date(self, request):
        d = request.query_params.get("date")
        if not d:
            return Response({"detail": "date=YYYY-MM-DD 쿼리 파라미터가 필요합니다."}, status=400)
        qs = self.get_queryset().filter(Q(daily_report__date=d) | Q(created_at__date=d))
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        ser = self.get_serializer(qs, many=True)
        return Response(ser.data)

    # POST /feedbacks/ai/ensure/
    # body: {
    #   "date": "YYYY-MM-DD"(옵션, 기본 오늘),
    #   "model": "gpt-x-2025",
    #   "prompt": "string",
    #   "response": {...},                # AI 원문 JSON
    #   "summary": "요약",                # 선택
    #   "recommended_action": "액션",     # 선택
    #   "confidence": 88.0               # 선택(0~100)
    # }
    @action(detail=False, methods=["post"], url_path="ai/ensure")
    def ai_ensure(self, request):
        u = request.user
        payload = request.data or {}
        d_str = payload.get("date")
        try:
            d = _date.fromisoformat(d_str) if d_str else _date.today()
        except Exception:
            return Response({"detail": "date 형식이 잘못되었습니다. YYYY-MM-DD"}, status=400)

        model = payload.get("model") or "gpt-x-2025"
        prompt = payload.get("prompt") or "일일 코칭 요약 생성"
        response = payload.get("response") or {"message": "콜드스타트: 내일은 하체 위주로 진행해요."}
        summary = payload.get("summary") or ""
        action_txt = payload.get("recommended_action") or ""
        confidence = payload.get("confidence")

        # 하루 1개 보장 업서트
        fb = ensure_ai_feedback(
            user=u,
            d=d,
            ai_model=model,
            prompt=prompt,
            response=response,
            summary=summary,
            recommended_action=action_txt,
            confidence=confidence,
        )

        # (선택) plan 연계가 필요한 경우 클라이언트에서 PATCH로 연결 가능
        # 여기서는 단순히 결과만 반환
        ser = self.get_serializer(fb)
        return Response({"ok": True, "date": d.isoformat(), "feedback": ser.data}, status=status.HTTP_200_OK)


class DailyReportViewSet(viewsets.ModelViewSet):
    """
    /dailyreports/        CRUD (본인 것만)
    /dailyreports/ensure/ (POST) -> (user,date) 1개 보장 get_or_create
    """
    queryset = DailyReport.objects.all()
    serializer_class = DailyReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = DailyReport.objects.filter(user=self.request.user).order_by("-date", "-id")
        d = self.request.query_params.get("date")
        if d:
            qs = qs.filter(date=d)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # POST /dailyreports/ensure/
    # body: {"date": "YYYY-MM-DD", "summary": "...", "score": 90.0}
    @action(detail=False, methods=["post"], url_path="ensure")
    def ensure(self, request):
        payload = request.data or {}
        d_str = payload.get("date")
        if not d_str:
            return Response({"detail": "date=YYYY-MM-DD 가 필요합니다."}, status=400)
        try:
            d = _date.fromisoformat(d_str)
        except Exception:
            return Response({"detail": "date 형식이 잘못되었습니다. YYYY-MM-DD"}, status=400)

        dr, created = ensure_daily_report(
            request.user,
            d,
            source=payload.get("source", "user"),
            summary=payload.get("summary"),
            score=payload.get("score"),
        )
        ser = self.get_serializer(dr)
        return Response({"ok": True, "created": created, "daily_report": ser.data})


class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Achievement.objects.filter(user=self.request.user).order_by("-achieved_at", "-id")
