from rest_framework import viewsets, permissions, status, decorators
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import transaction
from .serializers import UserSerializer

User = get_user_model()

class IsSelfOrAdmin(permissions.BasePermission):
    """
    오브젝트 권한:
    - 관리자는 누구나 접근
    - 일반 유저는 자기 것만 접근 가능
    """
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.id == request.user.id

class UserViewSet(viewsets.ModelViewSet):
    """
    사용자 뷰셋 (JWT 필요)
    - 목록/상세: 관리자만 전체, 일반 사용자는 자기 자신만
    - 생성: 기본은 관리자만(일반 회원가입은 별도 엔드포인트로 빼는 게 보통)
    - 수정/삭제: 자기 자신만, 또는 관리자
    - 비활성화(휴면)/재활성화: 커스텀 액션 제공
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    # ---- 공통 쿼리셋 제한 ----
    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    # ---- 생성: 기본은 관리자만 허용(원하면 회원가입 전용 API 따로 만드세요) ----
    def create(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "관리자만 사용자 생성이 가능합니다."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    # ---- 부분 수정/전체 수정: 자기 자신 또는 관리자 ----
    def update(self, request, *args, **kwargs):
        self.check_object_permissions(request, self.get_object())
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self.check_object_permissions(request, self.get_object())
        return super().partial_update(request, *args, **kwargs)

    # ---- 하드 삭제(탈퇴): 자기 자신은 비밀번호 확인 요구, 관리자는 바로 가능 ----
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if not request.user.is_staff:
            # 자기 계정 삭제 시 현재 비밀번호 검증 (보안)
            current_password = request.data.get("current_password")
            if not current_password or not request.user.check_password(current_password):
                return Response({"detail": "현재 비밀번호가 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    # ---- /users/api/users/me/ : 내 정보 전용 엔드포인트(GET/PATCH/DELETE) ----
    @decorators.action(detail=False, methods=["get", "patch", "delete"], url_path="me")
    def me(self, request):
        """
        GET   : 내 정보 조회
        PATCH : 내 정보 일부 수정 (email, first/last_name)
        DELETE: 내 계정 하드 삭제(탈퇴) - 비밀번호 확인 필요
        """
        user = request.user

        if request.method == "GET":
            return Response(self.get_serializer(user).data)

        if request.method == "PATCH":
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        if request.method == "DELETE":
            current_password = request.data.get("current_password")
            if not current_password or not user.check_password(current_password):
                return Response({"detail": "현재 비밀번호가 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    # ---- /users/api/users/{id}/deactivate/ : 휴면(비활성화) 전환 ----
    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsSelfOrAdmin])
    @transaction.atomic
    def deactivate(self, request, pk=None):
        """
        본인 또는 관리자가 호출 가능.
        - 일반 유저: 본인 비활성화 시 비밀번호 확인 권장
        - 결과: is_active=False (로그인/토큰 발급 불가)
        """
        user = self.get_object()
        if not request.user.is_staff:
            current_password = request.data.get("current_password")
            if not current_password or not request.user.check_password(current_password):
                return Response({"detail": "현재 비밀번호가 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response({"detail": "계정이 비활성화되었습니다.", "is_active": user.is_active})

    # ---- /users/api/users/{id}/reactivate/ : 재활성화 ----
    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    @transaction.atomic
    def reactivate(self, request, pk=None):
        """
        기본적으로 관리자만 재활성화(업무 규칙에 따라 self 허용도 가능).
        """
        if not request.user.is_staff:
            return Response({"detail": "관리자만 재활성화할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response({"detail": "계정이 재활성화되었습니다.", "is_active": user.is_active})
