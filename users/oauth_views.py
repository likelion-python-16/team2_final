# users/oauth_views.py
import secrets
import urllib.parse
from urllib.parse import urlsplit, urlunsplit

import requests
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.http import (
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.urls import reverse
from django.views.decorators.http import require_GET
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


# ---------------------------
# 공통 유틸
# ---------------------------

def _issue_jwt_for_user(user):
    """SimpleJWT 토큰 발급"""
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def _redirect_after_auth(request, tokens=None):
    """
    로그인 이후 이동.
    - next 쿼리가 있으면 우선
    - 없으면 대시보드
    - 데모로 access 토큰을 쿼리로 전달(실서비스는 HttpOnly 쿠키 권장)
    """
    next_url = request.GET.get("next") or reverse("tasks:dashboard")
    if tokens:
        q = urllib.parse.urlencode({"access": tokens["access"]})
        return HttpResponseRedirect(f"{next_url}?{q}")
    return HttpResponseRedirect(next_url)


def _build_callback_abs_url(request, pattern_name: str) -> str:
    """
    콜백 절대 URL을 생성하되,
    - 로컬 개발(127.0.0.1, localhost) 환경에서는 스킴을 http로 강제
    - 그 외 환경(프록시/https)에서는 요청 스킴을 그대로 사용
    """
    abs_url = request.build_absolute_uri(reverse(pattern_name))
    parts = urlsplit(abs_url)
    host_lower = parts.netloc.lower()
    if host_lower.startswith("127.0.0.1") or host_lower.startswith("localhost"):
        # 카카오 콘솔에 http로 등록했다면 여기서 http로 강제
        abs_url = urlunsplit(("http", parts.netloc, parts.path, parts.query, parts.fragment))
    # 디버그 로그
    print(f"[OAUTH] callback for {pattern_name} => {abs_url}")
    return abs_url


def _http_post_json(url, data=None, headers=None, timeout=8):
    r = requests.post(url, data=data or {}, headers=headers or {}, timeout=timeout)
    # 디버그
    print(f"[HTTP POST] {url} -> {r.status_code} {r.text[:300]}")
    r.raise_for_status()
    return r.json()


def _http_get_json(url, params=None, headers=None, timeout=8):
    r = requests.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
    # 디버그
    print(f"[HTTP GET] {url} -> {r.status_code} {r.text[:300]}")
    r.raise_for_status()
    return r.json()


# ---------------------------
# Kakao
# ---------------------------

@require_GET
def kakao_login(request):
    cfg = settings.OAUTH["KAKAO"]
    state = secrets.token_urlsafe(16)
    request.session["oauth_state_kakao"] = state

    redirect_uri = _build_callback_abs_url(request, "users:kakao_callback")

    params = {
        "response_type": "code",
        "client_id": cfg["CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "state": state,
    }
    # ✅ scope가 비어있지 않을 때만 추가
    scopes = cfg.get("SCOPE") or []
    if scopes:
        params["scope"] = " ".join(scopes)

    auth_url = f'{cfg["AUTH_URL"]}?{urllib.parse.urlencode(params)}'
    print("[KAKAO AUTH URL]", auth_url)
    return HttpResponseRedirect(auth_url)


@require_GET
def kakao_callback(request):
    cfg = settings.OAUTH["KAKAO"]
    code = request.GET.get("code")
    state = request.GET.get("state")

    if not code or state != request.session.get("oauth_state_kakao"):
        return HttpResponseBadRequest("Invalid state or code")

    redirect_uri = _build_callback_abs_url(request, "users:kakao_callback")

    # 1) 토큰 교환
    data = {
        "grant_type": "authorization_code",
        "client_id": cfg["CLIENT_ID"],
        "redirect_uri": redirect_uri,               # 로그인 때와 동일해야 함
        "code": code,
    }
    if cfg.get("CLIENT_SECRET"):
        data["client_secret"] = cfg["CLIENT_SECRET"]

    try:
        token = _http_post_json(cfg["TOKEN_URL"], data=data)
    except requests.HTTPError as e:
        return JsonResponse(
            {"detail": "kakao token exchange failed", "error": str(e), "body": getattr(e.response, "text", "")},
            status=400,
        )

    access_token = token.get("access_token")
    if not access_token:
        return JsonResponse({"detail": "no access_token from kakao"}, status=400)

    # 2) 사용자 정보
    try:
        me = _http_get_json(
            cfg["ME_URL"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
    except requests.HTTPError as e:
        return JsonResponse(
            {"detail": "kakao userinfo failed", "error": str(e), "body": getattr(e.response, "text", "")},
            status=400,
        )

    kakao_account = me.get("kakao_account") or {}
    profile = kakao_account.get("profile") or {}
    email = kakao_account.get("email")
    nickname = profile.get("nickname") or f'kakao_{me.get("id")}'

    if not email:
        # ✅ 이메일 없이도 계정 생성 가능하도록 대체
        email = f'{me.get("id")}@kakao.local'

    user, _ = User.objects.get_or_create(
        email=email,
        defaults={"username": email.split("@")[0] or nickname},
    )

    login(request, user)
    tokens = _issue_jwt_for_user(user)
    return _redirect_after_auth(request, tokens=tokens)


# ---------------------------
# Naver
# ---------------------------

@require_GET
def naver_login(request):
    cfg = settings.OAUTH["NAVER"]
    state = secrets.token_urlsafe(16)
    request.session["oauth_state_naver"] = state

    redirect_uri = _build_callback_abs_url(request, "users:naver_callback")

    params = {
        "response_type": "code",
        "client_id": cfg["CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "state": state,
    }
    auth_url = f'{cfg["AUTH_URL"]}?{urllib.parse.urlencode(params)}'
    print("[NAVER AUTH URL]", auth_url)
    return HttpResponseRedirect(auth_url)


@require_GET
def naver_callback(request):
    cfg = settings.OAUTH["NAVER"]
    code = request.GET.get("code")
    state = request.GET.get("state")

    if not code or state != request.session.get("oauth_state_naver"):
        return HttpResponseBadRequest("Invalid state or code")

    redirect_uri = _build_callback_abs_url(request, "users:naver_callback")

    # 1) 토큰 교환 (네이버는 GET)
    params = {
        "grant_type": "authorization_code",
        "client_id": cfg["CLIENT_ID"],
        "client_secret": cfg["CLIENT_SECRET"],
        "code": code,
        "state": state,
        # redirect_uri 파라미터는 공식문서상 선택적으로 보이지만
        # 불일치 이슈 예방을 위해 함께 전달하는 것도 안전
        "redirect_uri": redirect_uri,
    }
    try:
        token = _http_get_json(cfg["TOKEN_URL"], params=params)
    except requests.HTTPError as e:
        return JsonResponse(
            {"detail": "naver token exchange failed", "error": str(e), "body": getattr(e.response, "text", "")},
            status=400,
        )

    access_token = token.get("access_token")
    if not access_token:
        return JsonResponse({"detail": "no access_token from naver"}, status=400)

    # 2) 사용자 정보
    try:
        me = _http_get_json(
            cfg["ME_URL"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
    except requests.HTTPError as e:
        return JsonResponse(
            {"detail": "naver userinfo failed", "error": str(e), "body": getattr(e.response, "text", "")},
            status=400,
        )

    resp = me.get("response") or {}
    email = resp.get("email")
    name = resp.get("name") or f'naver_{resp.get("id", "")}'

    if not email:
        email = f'{resp.get("id")}@naver.local'

    user, _ = User.objects.get_or_create(
        email=email,
        defaults={"username": email.split("@")[0] or name},
    )

    login(request, user)
    tokens = _issue_jwt_for_user(user)
    return _redirect_after_auth(request, tokens=tokens)
