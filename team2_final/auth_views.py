# team2_final/auth_views.py
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)


# ✅ 핵심: authentication_classes = [] 로 세션/CSRF 체인 완전히 비활성화
class PublicTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    authentication_classes = []  # <- 중요


class PublicTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    authentication_classes = []  # <- 중요


class PublicTokenVerifyView(TokenVerifyView):
    permission_classes = [AllowAny]
    authentication_classes = []  # <- 중요
