from dataclasses import dataclass

@dataclass(frozen=True)
class ErrorDef:
    code: str
    message: str

SERVER_ERROR = ErrorDef("server_error", "서버 내부 오류가 발생했습니다.")
UNAUTHORIZED = ErrorDef("unauthorized", "인증이 필요합니다.")
FORBIDDEN = ErrorDef("forbidden", "권한이 없습니다.")
NOT_FOUND = ErrorDef("not_found", "요청한 리소스를 찾을 수 없습니다.")
BAD_REQUEST = ErrorDef("bad_request", "요청 값이 올바르지 않습니다.")