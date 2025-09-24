from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import (
    NotAuthenticated, AuthenticationFailed, ValidationError, NotFound
)
from .errors import SERVER_ERROR, UNAUTHORIZED, FORBIDDEN, NOT_FOUND as E_NOT_FOUND, BAD_REQUEST

def custom_exception_handler(exc, context):
    """
    DRF의 기본 exception_handler로 1차 변환 후,
    우리 프로젝트의 통일된 에러 포맷으로 감싸서 반환.
    """
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            code, msg, http_status = UNAUTHORIZED.code, UNAUTHORIZED.message, status.HTTP_401_UNAUTHORIZED
        elif isinstance(exc, PermissionDenied):
            code, msg, http_status = FORBIDDEN.code, FORBIDDEN.message, status.HTTP_403_FORBIDDEN
        elif isinstance(exc, NotFound):
            code, msg, http_status = E_NOT_FOUND.code, E_NOT_FOUND.message, status.HTTP_404_NOT_FOUND
        elif isinstance(exc, ValidationError):
            code, msg, http_status = BAD_REQUEST.code, response.data, status.HTTP_400_BAD_REQUEST
        else:
            code, msg, http_status = SERVER_ERROR.code, response.data, response.status_code

        response.data = {
            "error": {
                "code": code,
                "message": msg,
                "status_code": http_status,
            }
        }
        response.status_code = http_status
        return response

    # DRF가 처리하지 못한 예외는 500으로 통일
    return Response(
        {
            "error": {
                "code": SERVER_ERROR.code,
                "message": SERVER_ERROR.message,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )