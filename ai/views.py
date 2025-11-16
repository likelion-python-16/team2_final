# ai/views.py
# 임계값/폴백/표시 규칙 요약:
# - settings.MEAL_MATCH_THRESHOLD (기본 70.0)
# - settings.ALLOW_FALLBACK_SAVE_BELOW (기본 False)
# - settings.DEFAULT_FALLBACK_KCAL (기본 300.0)
# - 프리뷰 응답: macros(=100g, 레거시 표시), macros_per100g(=명시적 100g), macros_total(=총합), weight_g
# - 저장/합산은 항상 macros_total 기준

from __future__ import annotations

import csv
import logging
import mimetypes
import re

logger = logging.getLogger(__name__)

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

import requests
from django.conf import settings

# ✅ 사진 선저장 관련
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.timezone import now
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ai.utils import estimate_macros_from_csv, match_csv_entry  # CSV 매칭/가늠값
from intakes.models import Food, Meal, MealItem, NutritionLog

# ==============================================
# Hugging Face helpers
# ==============================================
HF_BASE = "https://router.huggingface.co/hf-inference"


class HFError(Exception):
    """허깅페이스 API 호출 관련 예외"""

    pass


def _hf_headers_binary() -> Dict[str, str]:
    token = getattr(settings, "HF_TOKEN", None)
    if not token:
        raise HFError("HF_TOKEN 이 설정되지 않았습니다.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }


def hf_image_classify(image_bytes: bytes, top_k: int = 5) -> List[Dict[str, Any]]:
    """허깅페이스 이미지 분류 호출 + JSON 파싱 오류도 HFError로 승격"""
    model_id = getattr(settings, "HF_IMAGE_MODEL", None)
    if not model_id:
        raise HFError("HF_IMAGE_MODEL 이 설정되지 않았습니다.")
    url = f"{HF_BASE}/models/{model_id}"

    try:
        r = requests.post(
            url,
            headers=_hf_headers_binary(),
            data=image_bytes,
            timeout=60,
        )
    except requests.RequestException as e:
        # 네트워크/타임아웃 계열
        raise HFError(f"요청 실패: {e}")

    # HTTP 레벨 에러
    if r.status_code >= 400:
        # 너무 길어질 수 있으니 앞부분만 로그/메시지에 포함
        body_snippet = r.text[:200].replace("\n", " ")
        raise HFError(f"HF 응답 오류: {r.status_code} {body_snippet}")

    # ✅ JSON 파싱 에러도 HFError로 감싸기
    try:
        data = r.json()
    except ValueError as e:
        body_snippet = r.text[:200].replace("\n", " ")
        raise HFError(f"HF JSON 파싱 오류: {e}; body[:200]={body_snippet!r}")

    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "label" in data[0]
    ):
        return data[:top_k]

    # 예상한 형식(list[{"label":..,"score":..}, ...])이 아니면 빈 리스트
    return []


# ==============================================
# CSV Loader (intakes/data/mfds_foods.csv)
#  - 디버그용 csv_count 표시를 위해 유지
# ==============================================
_CACHED_MFDS_ROWS: Optional[List[Dict[str, Any]]] = None


def _csv_path() -> Optional[str]:
    """경로 우선순위: settings.MFDS_FOOD_CSV → BASE_DIR/intakes/data/mfds_foods.csv"""
    p = getattr(settings, "MFDS_FOOD_CSV", None)
    if p:
        try:
            from pathlib import Path

            pp = Path(p)
            if pp.exists():
                return str(pp)
        except Exception:
            pass

    try:
        from pathlib import Path

        base = Path(settings.BASE_DIR) / "intakes" / "data" / "mfds_foods.csv"
        if base.exists():
            return str(base)
    except Exception:
        pass
    return None


def _load_mfds_rows() -> List[Dict[str, Any]]:
    """CSV를 1회 캐싱해서 사용 (디버그용 카운트)"""
    global _CACHED_MFDS_ROWS
    if _CACHED_MFDS_ROWS is not None:
        return _CACHED_MFDS_ROWS

    path = _csv_path()
    if not path:
        _CACHED_MFDS_ROWS = []
        return _CACHED_MFDS_ROWS

    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        rows = []

    _CACHED_MFDS_ROWS = rows
    return rows


def _norm(s: Any) -> str:
    return str(s or "").strip().lower().replace("-", " ").replace("_", " ")


def _to_float(v: Any) -> Optional[float]:
    try:
        x = float(v)
        if x != x:  # NaN
            return None
        return x
    except Exception:
        return None


_WEIGHT_NUMBER_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*g", re.IGNORECASE)


def _parse_weight(v: Any) -> float:
    """
    '550g' / '총중량 300 g' / '1개(180g)' / '180 g/pack' → 180.0
    비어있으면 100.0
    """
    if v is None:
        return 100.0
    s = str(v).strip().lower().replace("그램", "g")
    m = _WEIGHT_NUMBER_RE.search(s)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    # '300'처럼 단위 없는 숫자도 허용
    try:
        return float(s)
    except Exception:
        return 100.0


def _extract_macros_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    CSV 한 줄에서:
      - per100g: 100g 기준(그대로/보조)
      - total:   1회 제공량(=weight_g) 기준(메인) ← 항상 per100g * (weight_g/100)로 계산
    """
    # 이름
    label_ko = (
        row.get("식품명")
        or row.get("name_ko")
        or row.get("label_ko")
        or row.get("name")
        or ""
    ).strip()
    # 1회 제공량(총중량 g)
    weight_g = _parse_weight(
        row.get("식품중량")
        or row.get("1회제공량")
        or row.get("serving")
        or row.get("weight")
        or "100"
    )

    # 100g 기준 주요 4대영양
    kcal = (
        _to_float(row.get("에너지(kcal)"))
        or _to_float(row.get("kcal"))
        or _to_float(row.get("calories"))
        or _to_float(row.get("energy_kcal"))
        or 0.0
    )
    protein = (
        _to_float(row.get("단백질(g)"))
        or _to_float(row.get("protein"))
        or _to_float(row.get("protein_g"))
        or 0.0
    )
    carbs = (
        _to_float(row.get("탄수화물(g)"))
        or _to_float(row.get("carb"))
        or _to_float(row.get("carbs"))
        or _to_float(row.get("carbohydrate"))
        or _to_float(row.get("carbohydrate_g"))
        or 0.0
    )
    fat = (
        _to_float(row.get("지방(g)"))
        or _to_float(row.get("fat"))
        or _to_float(row.get("fat_g"))
        or 0.0
    )

    per100g = {
        "calories": round(kcal or 0.0, 1),
        "protein": round(protein or 0.0, 1),
        "carb": round(carbs or 0.0, 1),
        "fat": round(fat or 0.0, 1),
    }
    scale = (weight_g / 100.0) if weight_g else 1.0
    total = {
        "calories": round((kcal or 0.0) * scale, 1),
        "protein": round((protein or 0.0) * scale, 1),
        "carb": round((carbs or 0.0) * scale, 1),
        "fat": round((fat or 0.0) * scale, 1),
    }

    return {
        "label_ko": label_ko,
        "weight_g": float(weight_g or 100.0),  # 1회 제공량 g
        "per100g": per100g,  # 100g 기준(보조)
        "total": total,  # 1회 제공량 기준(메인)
    }


def _estimate_csv_global_default() -> Optional[Dict[str, float]]:
    """
    HF가 완전히 실패해서 라벨도 없을 때,
    mfds_foods.csv 전체를 돌면서 100g 기준 '평균' 영양소를 계산한다.
    - calories > 0 인 행들만 사용
    """
    rows = _load_mfds_rows()
    if not rows:
        return None

    total_cal = total_pro = total_carb = total_fat = 0.0
    cnt = 0

    for r in rows:
        try:
            m = _extract_macros_from_row(r)
            per = m.get("per100g") or {}
            cal = float(per.get("calories", 0.0) or 0.0)
            if cal <= 0:
                continue
            total_cal += cal
            total_pro += float(per.get("protein", 0.0) or 0.0)
            total_carb += float(per.get("carb", 0.0) or 0.0)
            total_fat += float(per.get("fat", 0.0) or 0.0)
            cnt += 1
        except Exception:
            continue

    if not cnt:
        return None

    return {
        "calories": round(total_cal / cnt, 1),
        "protein": round(total_pro / cnt, 1),
        "carb": round(total_carb / cnt, 1),
        "fat": round(total_fat / cnt, 1),
    }


def _match_csv_by_label(pred_label: str) -> Optional[Dict[str, Any]]:
    """
    AI 라벨과 CSV의 이름(ko/en/synonyms)을 최대한 매칭
    - 우선순위: exact en → exact ko → synonyms → 부분 포함(en/ko)
    ※ per100g/total/weight_g를 함께 반환
    """
    rows = _load_mfds_rows()
    if not rows:
        return None

    label = _norm(pred_label)
    if not label:
        return None

    # 1) exact en
    for r in rows:
        if _norm(r.get("name_en")) == label:
            return _extract_macros_from_row(r)

    # 2) exact ko
    for r in rows:
        if _norm(r.get("식품명") or r.get("name_ko")) == label:
            return _extract_macros_from_row(r)

    # 3) synonyms (쉼표/세미콜론 구분)
    for r in rows:
        syn = r.get("synonyms") or r.get("alias") or ""
        if not syn:
            continue
        cand = [_norm(x) for x in str(syn).replace(";", ",").split(",") if x.strip()]
        if label in cand:
            return _extract_macros_from_row(r)

    # 4) 부분 포함 (en/ko)
    for r in rows:
        if label and (
            label in _norm(r.get("name_en"))
            or label in _norm(r.get("식품명") or r.get("name_ko"))
        ):
            return _extract_macros_from_row(r)

    return None


# ==============================================
# 업로드 헬퍼 (image/photo/file + png/jpg/webp/heic 등 유연 수용)
# ==============================================
IMAGE_KEYS = ("image", "photo", "file", "picture", "upload")


def _pick_image_file(request):
    """
    1순위: 지정 키들(IMAGE_KEYS)에서 이미지 파일 찾아 반환
    2순위: request.FILES 전체에서 첫 번째 image/* 반환
    실패 시 None
    """
    files = request.FILES
    # 1) 키 우선 탐색
    for k in IMAGE_KEYS:
        if k in files:
            f = files[k]
            ctype = (
                getattr(f, "content_type", None)
                or mimetypes.guess_type(getattr(f, "name", ""))[0]
            )
            if ctype is None or (ctype and ctype.startswith("image/")):
                return f
    # 2) 전체에서 이미지 탐색
    for f in files.values():
        ctype = (
            getattr(f, "content_type", None)
            or mimetypes.guess_type(getattr(f, "name", ""))[0]
        )
        if ctype and ctype.startswith("image/"):
            return f
    return None


# ==============================================
# 사진 선저장 도우미
# ==============================================
def _save_upload_and_get_paths(
    image_bytes: bytes, ext_hint: str = "jpg"
) -> Dict[str, str]:
    """업로드 이미지를 media에 저장하고 {'name': FileField name, 'url': URL} 반환."""
    dt = now()
    subdir = f"meals/{dt:%Y/%m/%d}"
    ext = (ext_hint or "jpg").lower().replace(".", "")
    fname = f"{uuid4().hex}.{ext}"
    path = f"{subdir}/{fname}"  # FileField name으로 사용
    saved_path = default_storage.save(path, ContentFile(image_bytes))
    url = default_storage.url(saved_path)
    return {"name": saved_path, "url": url}


# ==============================================
# Food 매칭 보강
# ==============================================
def _find_food_by_label(raw_label: str) -> Optional[Food]:
    """
    이미지 라벨로 Food를 찾는다.
    - 정확 일치(name/name_en)
    - 정규화(_norm) 후 일치
    - 부분 포함(icontains)까지 허용
    """
    if not raw_label:
        return None

    qs = Food.objects.all()

    # 1) 원본 정확 일치
    food = qs.filter(name__iexact=raw_label).first()
    if food:
        return food
    try:
        food = qs.filter(name_en__iexact=raw_label).first()
        if food:
            return food
    except Exception:
        pass

    # 2) 정규화 일치
    norm = _norm(raw_label)
    food = qs.filter(name__iexact=norm).first()
    if food:
        return food
    try:
        food = qs.filter(name_en__iexact=norm).first()
        if food:
            return food
    except Exception:
        pass

    # 3) 부분 포함 (너무 광범위해지는 것 방지: 앞 20자 기준)
    head = norm[:20]
    food = qs.filter(name__icontains=head).first()
    if food:
        return food
    try:
        food = qs.filter(name_en__icontains=head).first()
        if food:
            return food
    except Exception:
        pass

    return None


# ==============================================
# AI ViewSet
# ==============================================
class AIViewSet(viewsets.ViewSet):
    """
    - POST /api/ai/meal-analyze/ : 이미지 분석 (프리뷰/자동저장 지원)
    - POST /api/ai/meal-commit/  : 프리뷰 결과를 실제 저장
    - DELETE /api/ai/meal-entry/<item_id>/ : 식사 항목 삭제
    """

    permission_classes = [AllowAny]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    @action(
        detail=False,
        methods=["post"],
        url_path="meal-analyze",
        parser_classes=(MultiPartParser, FormParser, JSONParser),  # 멀티파트 우선
    )
    def meal_analyze(self, request):
        """
        식단 이미지 분석 → 음식명/영양소 추출 (Food 모델 → CSV 순 매칭)
        - commit 플래그:
          * 'preview' / '0' / 'false' / 'no' → 저장하지 않고 미리보기만
          * 그 외(기본): 로그인 사용자는 (임계 통과 시) 자동 저장
        - 프리뷰 응답에는 can_save + save_payload 포함
        - 응답에 100g 기준(per100g) + 1회제공량 총합(total) 동시 제공, 저장은 total 기준
        """

        # 🔎 엔드포인트 진입 로그
        print(
            "[meal_analyze] start is_auth=",
            bool(getattr(request, "user", None) and request.user.is_authenticated),
            "commit=",
            (request.POST.get("commit") or request.data.get("commit") or "auto"),
            flush=True,
        )

        try:
            # 0) 커밋 모드 파싱
            raw = (
                (request.POST.get("commit") or request.data.get("commit") or "auto")
                .strip()
                .lower()
            )
            commit_preview = raw in ("0", "false", "preview", "no")

            # 1) 파일 (image/photo/file 모두 허용)
            file_obj = _pick_image_file(request)
            if not file_obj:
                print("[meal_analyze] no image file found in request.FILES", flush=True)
                return Response(
                    {
                        "error": "이미지 파일을 업로드해 주세요. (허용 키: image/photo/file)"
                    },
                    status=400,
                )
            try:
                image_bytes = file_obj.read()
                if not image_bytes:
                    print("[meal_analyze] uploaded file is empty", flush=True)
                    raise ValueError("empty file")
            except Exception:
                print("[meal_analyze] failed to read uploaded file", flush=True)
                return Response(
                    {"error": "이미지 파일을 읽을 수 없습니다."}, status=400
                )

            # 확장자 힌트
            ext_hint = "jpg"
            try:
                n = (getattr(file_obj, "name", "") or "").lower()
                if n.rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp", "heic"):
                    ext_hint = n.rsplit(".", 1)[-1]
            except Exception:
                pass

            # ✅ 업로드 이미지 선 저장 (S3/로컬 상관없이 default_storage 사용)
            photo_name = None
            photo_url = None
            try:
                photo_info = _save_upload_and_get_paths(image_bytes, ext_hint=ext_hint)
                photo_name = photo_info.get("name")
                photo_url = photo_info.get("url")
            except Exception:
                # 저장 실패해도 분석은 계속 진행
                logger.exception(
                    "meal_analyze: photo save failed (continuing without photo)"
                )

            # 2) HF 추론
            try:
                predictions = hf_image_classify(image_bytes, top_k=5)
            except HFError as e:
                # 모델 자체 문제나 입력 이미지 문제 → '예상 가능한 실패' → 422
                logger.warning(
                    "meal_analyze: HFError during hf_image_classify: %s",
                    e,
                    exc_info=True,
                )
                return Response(
                    {
                        "error": {
                            "code": "analysis_failed",
                            "message": "이미지에서 음식을 인식하지 못했습니다. 음식이 잘 보이도록 다시 촬영해서 업로드해 주세요.",
                            "status_code": 422,
                        }
                    },
                    status=422,
                )
            except Exception as e:
                # 기타 예외도 포트폴리오용으론 '분석 실패'로 정리
                logger.exception(
                    "meal_analyze: unexpected error during hf_image_classify: %s", e
                )
                return Response(
                    {
                        "error": {
                            "code": "analysis_failed",
                            "message": "이미지를 분석하는 중 오류가 발생했습니다. 다른 사진으로 다시 시도해 주세요.",
                            "status_code": 422,
                        }
                    },
                    status=422,
                )

            # HF가 예외는 안 던졌는데, 예측 결과가 비어 있는 경우도 '분석 실패'
            if not predictions:
                return Response(
                    {
                        "error": {
                            "code": "analysis_failed",
                            "message": "이미지에서 인식 가능한 음식이 없습니다. 다른 사진으로 다시 시도해 주세요.",
                            "status_code": 422,
                        }
                    },
                    status=422,
                )

            # 3) 결과 파싱 + 점수 계산
            top_label = str(predictions[0].get("label", "")).strip()
            try:
                best_score = float(predictions[0].get("score", 0.0) or 0.0)
            except Exception:
                best_score = 0.0

            alternatives = []
            for p in predictions[1:]:
                if not isinstance(p, dict) or not p.get("label"):
                    continue
                try:
                    score = float(p.get("score", 0.0) or 0.0)
                except Exception:
                    score = 0.0
                alternatives.append({"label": p.get("label"), "score": score})

            # 4) DB 매칭
            label_ko: Optional[str] = None
            per100g: Dict[str, float] = {}
            total: Dict[str, float] = {}
            weight_g: float = 100.0
            found_food = None

            for p in predictions:
                raw_label = p.get("label")
                if not raw_label:
                    continue

                food_obj = _find_food_by_label(raw_label)
                if food_obj:
                    found_food = food_obj
                    label_ko = (
                        getattr(food_obj, "name_ko", None)
                        or getattr(food_obj, "name", None)
                        or ""
                    ).strip() or top_label
                    per100g = {
                        "calories": float(
                            getattr(food_obj, "kcal_per_100g", 0.0) or 0.0
                        ),
                        "protein": float(
                            getattr(food_obj, "protein_g_per_100g", 0.0) or 0.0
                        ),
                        "carb": float(getattr(food_obj, "carb_g_per_100g", 0.0) or 0.0),
                        "fat": float(getattr(food_obj, "fat_g_per_100g", 0.0) or 0.0),
                    }
                    weight_g = 100.0
                    total = {k: round(v, 1) for k, v in per100g.items()}
                    break

            # 5) CSV 매칭 (DB 실패 시)
            if not per100g:
                for p in predictions:
                    raw_label = p.get("label")
                    if not raw_label:
                        continue
                    hit = match_csv_entry(raw_label)
                    if hit:
                        label_ko = (hit.get("label_ko") or "").strip() or top_label
                        weight_g = float(hit.get("weight_g") or 100.0)
                        per100g = hit.get("per100g") or {}
                        total = hit.get("total") or {}
                        for k in ("calories", "protein", "carb", "fat"):
                            per100g[k] = float(per100g.get(k, 0.0) or 0.0)
                            total[k] = float(total.get(k, 0.0) or 0.0)
                        break

            # 시간대별 식사타입
            hour = timezone.now().hour
            if 5 <= hour < 11:
                meal_type = "아침"
            elif 11 <= hour < 17:
                meal_type = "점심"
            elif 17 <= hour < 22:
                meal_type = "저녁"
            else:
                meal_type = "간식"

            matched = bool(per100g)

            # ✅ 임계/옵션 계산
            threshold = float(getattr(settings, "MEAL_MATCH_THRESHOLD", 70.0))
            allow_fallback_below = bool(
                getattr(settings, "ALLOW_FALLBACK_SAVE_BELOW", False)
            )
            fallback_kcal = float(
                getattr(settings, "DEFAULT_FALLBACK_KCAL", 300.0) or 300.0
            )

            raw_confidence = round(best_score * 100.0, 1)
            confidence_pct = raw_confidence

            if matched and confidence_pct <= 1.0:
                if found_food:
                    confidence_pct = 95.0
                else:
                    confidence_pct = 80.0
            elif (not matched) and confidence_pct <= 1.0 and allow_fallback_below:
                confidence_pct = 60.0

            passed = bool(matched and (confidence_pct >= threshold))

            # 6) 프리뷰 응답
            if commit_preview or (not request.user.is_authenticated) or (not passed):
                source = "unmatched"
                if matched:
                    source = "db" if found_food else "csv"

                can_save = False
                save_payload = None

                macros_for_display = per100g if matched else {}
                macros_total = total if matched else {}

                if request.user.is_authenticated:
                    if passed:
                        can_save = True
                        save_payload = {
                            "label_ko": (label_ko or top_label),
                            "macros": macros_total,
                            "meal_type": meal_type,
                            "source": source,
                            "food_id": getattr(found_food, "id", None),
                            "photo_name": photo_name,
                        }
                    elif allow_fallback_below and not matched:
                        est = (
                            estimate_macros_from_csv(label_ko or top_label)
                            if (label_ko or top_label)
                            else None
                        )
                        if est and (est.get("calories", 0) or 0) > 0:
                            can_save = True
                            source = "csv_estimate"
                            macros_for_display = {
                                "calories": float(est.get("calories", 0.0) or 0.0),
                                "protein": float(est.get("protein", 0.0) or 0.0),
                                "carb": float(est.get("carb", 0.0) or 0.0),
                                "fat": float(est.get("fat", 0.0) or 0.0),
                            }
                            weight_g = float(weight_g or 100.0)
                            scale = (weight_g / 100.0) if weight_g else 1.0
                            macros_total = {
                                "calories": round(
                                    macros_for_display["calories"] * scale, 1
                                ),
                                "protein": round(
                                    macros_for_display["protein"] * scale, 1
                                ),
                                "carb": round(macros_for_display["carb"] * scale, 1),
                                "fat": round(macros_for_display["fat"] * scale, 1),
                            }
                            save_payload = {
                                "label_ko": (label_ko or top_label),
                                "macros": macros_total,
                                "meal_type": meal_type,
                                "source": source,
                                "food_id": None,
                                "photo_name": photo_name,
                            }
                        else:
                            can_save = True
                            source = "default"
                            macros_for_display = {
                                "calories": fallback_kcal,
                                "protein": 0.0,
                                "carb": 0.0,
                                "fat": 0.0,
                            }
                            macros_total = dict(macros_for_display)
                            save_payload = {
                                "label_ko": (label_ko or top_label),
                                "macros": macros_total,
                                "meal_type": meal_type,
                                "source": source,
                                "food_id": None,
                                "photo_name": photo_name,
                            }

                return Response(
                    {
                        "saved": False,
                        "source": source,
                        "label": top_label,
                        "label_ko": label_ko or top_label,
                        "confidence": confidence_pct,
                        "macros": macros_for_display,
                        "macros_per100g": per100g or {},
                        "macros_total": macros_total or {},
                        "weight_g": float(weight_g or 100.0),
                        "photo_url": photo_url,
                        "alternatives": alternatives,
                        "meal_type": meal_type,
                        "can_save": can_save,
                        "has_payload": bool(save_payload),
                        "save_payload": save_payload,
                        "debug": {
                            "is_auth": bool(request.user.is_authenticated),
                            "matched": bool(per100g),
                            "db_hit": bool(found_food),
                            "csv_count": len(_load_mfds_rows()),
                            "top_label": top_label,
                            "confidence_pct": confidence_pct,
                            "threshold": threshold,
                            "allow_fallback_below": allow_fallback_below,
                            "fallback_kcal": fallback_kcal,
                            "weight_g": float(weight_g or 100.0),
                        },
                    },
                    status=200,
                )

            # 7) 자동 저장 (로그인 + 프리뷰 아님 + 임계 통과)
            try:
                with transaction.atomic():
                    today = date.today()
                    meal, _ = Meal.objects.get_or_create(
                        user=request.user,
                        log_date=today,
                        meal_type=meal_type,
                    )
                    macros_total = (
                        total
                        or per100g
                        or {"calories": 0.0, "protein": 0.0, "carb": 0.0, "fat": 0.0}
                    )

                    meal_item = MealItem.objects.create(
                        meal=meal,
                        food=found_food,
                        name=(label_ko or top_label),
                        kcal=macros_total["calories"],
                        protein_g=macros_total["protein"],
                        carb_g=macros_total["carb"],
                        fat_g=macros_total["fat"],
                        photo=photo_name,
                    )
                    log, _ = NutritionLog.objects.get_or_create(
                        user=request.user, date=today
                    )
                    try:
                        log.recalc()
                    except Exception:
                        pass

                updated_consumed = {
                    "calories": round(getattr(log, "kcal_total", 0.0) or 0.0, 1),
                    "protein": round(getattr(log, "protein_total_g", 0.0) or 0.0, 1),
                    "carbs": round(getattr(log, "carb_total_g", 0.0) or 0.0, 1),
                    "fat": round(getattr(log, "fat_total_g", 0.0) or 0.0, 1),
                }

                return Response(
                    {
                        "saved": True,
                        "source": "db" if found_food else "csv",
                        "updated_consumed": updated_consumed,
                        "label": top_label,
                        "label_ko": label_ko or top_label,
                        "confidence": confidence_pct,
                        "macros": per100g,
                        "macros_per100g": per100g,
                        "macros_total": macros_total,
                        "weight_g": float(weight_g or 100.0),
                        "photo_url": (
                            default_storage.url(photo_name) if photo_name else None
                        ),
                        "alternatives": alternatives,
                        "meal_type": meal_type,
                        "meal_item_id": meal_item.id,
                        "debug": {
                            "is_auth": True,
                            "matched": True,
                            "db_hit": bool(found_food),
                            "csv_count": len(_load_mfds_rows()),
                            "top_label": top_label,
                            "confidence_pct": confidence_pct,
                            "threshold": threshold,
                            "weight_g": float(weight_g or 100.0),
                        },
                    },
                    status=200,
                )
            except IntegrityError as e:
                logger.exception("meal_analyze: DB IntegrityError: %s", e)
                return Response(
                    {
                        "error": {
                            "code": "analysis_failed",
                            "message": "식단 정보를 저장하는 중 오류가 발생했습니다. 다시 시도해 주세요.",
                            "status_code": 422,
                        }
                    },
                    status=422,
                )
            except Exception as e:
                logger.exception(
                    "meal_analyze: unexpected error during autosave: %s", e
                )
                return Response(
                    {
                        "error": {
                            "code": "analysis_failed",
                            "message": "식단 정보를 저장하는 중 알 수 없는 오류가 발생했습니다.",
                            "status_code": 422,
                        }
                    },
                    status=422,
                )

        # 🔴 최상위 안전망: 여기까지 빠져나오는 예외는 전부 422로 덮어쓰기
        except Exception as e:
            logger.exception("meal_analyze: unexpected top-level error: %s", e)
            return Response(
                {
                    "error": {
                        "code": "analysis_failed",
                        "message": "이미지를 분석하는 중 알 수 없는 오류가 발생했습니다. 다른 사진으로 다시 시도해 주세요.",
                        "status_code": 422,
                    }
                },
                status=422,
            )

    @action(
        detail=False,
        methods=["post"],
        url_path="meal-commit",
        permission_classes=[IsAuthenticated],
        parser_classes=(JSONParser, FormParser, MultiPartParser),
    )
    def meal_commit(self, request):
        """
        프리뷰 응답의 save_payload를 받아 실제로 저장한다.
        요청(JSON 또는 form-data):
        {
          "label_ko": "김치찌개",
          "macros": {"calories": 350, "protein": 20, "carb": 25, "fat": 15},  # ✅ 총합(1회 제공량) 기준만 전달됨
          "meal_type": "아침|점심|저녁|간식",
          "source": "db|csv|csv_estimate|default|csv_default",
          "food_id": 123,
          "photo_name": "meals/2025/01/01/xxx.jpg"  # ✅ 분석 단계에서 선저장한 파일 경로
        }
        """
        data = request.data

        label_ko = (data.get("label_ko") or "").strip()
        meal_type = (data.get("meal_type") or "").strip() or "간식"
        source = (data.get("source") or "").strip() or "csv"
        food_id = data.get("food_id")
        photo_name = (data.get("photo_name") or "").strip() or None

        macros = data.get("macros") or {}
        try:
            kcal = float(macros.get("calories", 0) or 0)
            protein = float(macros.get("protein", 0) or 0)
            carb = float(macros.get("carb", 0) or 0)
            fat = float(macros.get("fat", 0) or 0)
        except Exception:
            return Response({"error": "macros 형식이 올바르지 않습니다."}, status=400)

        if not label_ko or (kcal == 0 and protein == 0 and carb == 0 and fat == 0):
            return Response(
                {"error": "라벨 또는 영양정보가 비어 있습니다."}, status=400
            )

        food_obj = None
        if food_id:
            try:
                food_obj = Food.objects.get(pk=food_id)
            except Food.DoesNotExist:
                food_obj = None  # CSV 기반 저장 허용

        try:
            with transaction.atomic():
                today = date.today()
                meal, _ = Meal.objects.get_or_create(
                    user=request.user,
                    log_date=today,
                    meal_type=meal_type,
                )
                # ✅ 총합(1회 제공량) 기준으로만 기록
                meal_item = MealItem.objects.create(
                    meal=meal,
                    food=food_obj,
                    name=label_ko,
                    kcal=kcal,
                    protein_g=protein,
                    carb_g=carb,
                    fat_g=fat,
                    source=source,
                )
                # ✅ 사진 연결
                if photo_name:
                    try:
                        meal_item.photo.name = photo_name
                        meal_item.save(update_fields=["photo"])
                    except Exception:
                        pass

                log, _ = NutritionLog.objects.get_or_create(
                    user=request.user, date=today
                )
                try:
                    log.recalc()
                except Exception:
                    pass

            updated_consumed = {
                "calories": round(getattr(log, "kcal_total", 0.0) or 0.0, 1),
                "protein": round(getattr(log, "protein_total_g", 0.0) or 0.0, 1),
                "carbs": round(getattr(log, "carb_total_g", 0.0) or 0.0, 1),
                "fat": round(getattr(log, "fat_total_g", 0.0) or 0.0, 1),
            }

            return Response(
                {
                    "ok": True,
                    "saved": True,
                    "source": source,
                    "meal_item_id": meal_item.id,
                    "updated_consumed": updated_consumed,
                    "photo_url": (
                        default_storage.url(photo_name) if photo_name else None
                    ),
                },
                status=200,
            )
        except IntegrityError as e:
            logger.exception("meal_commit: DB IntegrityError: %s", e)
            return Response(
                {
                    "error": {
                        "code": "analysis_failed",
                        "message": "식단 정보를 저장하는 중 오류가 발생했습니다. 다시 시도해 주세요.",
                        "status_code": 422,
                    }
                },
                status=422,
            )
        except Exception as e:
            logger.exception("meal_commit: unexpected error: %s", e)
            return Response(
                {
                    "error": {
                        "code": "analysis_failed",
                        "message": "식단 정보를 저장하는 중 알 수 없는 오류가 발생했습니다.",
                        "status_code": 422,
                    }
                },
                status=422,
            )

    @action(
        detail=False,
        methods=["delete"],
        url_path=r"meal-entry/(?P<item_id>\d+)",
        permission_classes=[IsAuthenticated],
    )
    def delete_meal_entry(self, request, item_id=None):
        """식사 항목 삭제 후 요약 재계산"""
        try:
            meal_item = MealItem.objects.select_related("meal").get(
                pk=item_id, meal__user=request.user
            )
        except MealItem.DoesNotExist:
            return Response({"error": "삭제할 식사를 찾을 수 없습니다."}, status=404)

        meal = meal_item.meal
        meal_item.delete()

        log, _ = NutritionLog.objects.get_or_create(
            user=request.user, date=meal.log_date
        )
        try:
            log.recalc()
        except Exception:
            pass

        updated_consumed = {
            "calories": round(getattr(log, "kcal_total", 0.0) or 0.0, 1),
            "protein": round(getattr(log, "protein_total_g", 0.0) or 0.0, 1),
            "carbs": round(getattr(log, "carb_total_g", 0.0) or 0.0, 1),
            "fat": round(getattr(log, "fat_total_g", 0.0) or 0.0, 1),
        }

        return Response({"ok": True, "updated_consumed": updated_consumed})
