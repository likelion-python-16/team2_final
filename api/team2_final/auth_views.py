from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenVerifyView
)

class PublicTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]

class PublicTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

class PublicTokenVerifyView(TokenVerifyView):
    permission_classes = [AllowAny]
