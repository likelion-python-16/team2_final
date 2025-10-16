from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(["GET"])
def healthz(_):
    """
    Liveness: 애플리케이션 프로세스가 살아있는지 확인 (DB 의존 없음)
    """
    return Response({"status": "ok"})

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import connections
from django.db.utils import OperationalError
import json

@csrf_exempt
@require_POST
def simple_token(request):
    """
    공개 토큰 발급(테스트용): username/password로 JWT 반환
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("invalid json")
    username = data.get("username", "")
    password = data.get("password", "")
    user = authenticate(username=username, password=password)
    if not user:
        return JsonResponse(
            {"error": {"code": "unauthorized", "message": "invalid credentials", "status_code": 401}},
            status=401,
        )
    refresh = RefreshToken.for_user(user)
    return JsonResponse({"access": str(refresh.access_token), "refresh": str(refresh)})

def readyz(_request):
    """
    Readiness: DB 연결 가능 여부로 200/503 판단 (쿠버네티스 readinessProbe 용)
    """
    try:
        connections["default"].cursor()
        return JsonResponse({"status": "ok"})
    except OperationalError:
        return JsonResponse({"status": "db-unavailable"}, status=503)
