from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import UserViewSet, setup_view, profile_view, signup_view

router = DefaultRouter()
# 사용자 CRUD + me/deactivate/reactivate 액션
router.register(r'api/users', UserViewSet, basename='user')

urlpatterns = [
    # JWT (최소 셋업: 로그인/리프레시)
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Setup page
    path("signup/", signup_view, name="user_signup"),
    path("setup/", setup_view, name="user_setup"),
    path("profile/", profile_view, name="user_profile"),

    # User 라우터
    path("", include(router.urls)),
]
