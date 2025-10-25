# users/urls.py
from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import oauth_views
from .views import RegisterView, UserViewSet

app_name = "users"

# -------------------------------------------------
# 1) DRF Router (ViewSet)
#    - /api/ 밑에 붙이면 /api/users/ 로 노출
# -------------------------------------------------
router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")

# 이 리스트를 프로젝트 urls.py에서
#   path("api/", include((api_urlpatterns, "users"), namespace="users_api"))
# 로 마운트하면 /api/users/ 가 된다.
api_urlpatterns = [
    path("", include(router.urls)),
]

# -------------------------------------------------
# 2) Auth (회원가입 API)
#    - /auth/ 밑에 붙이면 /auth/register/ 로 노출
# -------------------------------------------------
auth_urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
]

# -------------------------------------------------
# 3) Pages (OAuth / Logout)
#    - /users/ 밑에 붙이면 /users/oauth/... /users/logout/ 로 노출
# -------------------------------------------------
page_urlpatterns = [
    # OAuth (카카오/네이버)
    path("oauth/kakao/login/", oauth_views.kakao_login, name="kakao_login"),
    path("oauth/kakao/callback/", oauth_views.kakao_callback, name="kakao_callback"),
    path("oauth/naver/login/", oauth_views.naver_login, name="naver_login"),
    path("oauth/naver/callback/", oauth_views.naver_callback, name="naver_callback"),
    # Logout (POST 전용; 템플릿에서 <form method="post">로 호출 권장)
    path(
        "logout/",
        LogoutView.as_view(next_page=getattr(settings, "LOGOUT_REDIRECT_URL", "/")),
        name="logout",
    ),
]

# 기본 urlpatterns는 비워두고,
# 루트 urls.py에서 명시적으로 각 그룹을 원하는 prefix로 include 하세요.
urlpatterns = []
