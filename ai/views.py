# 임계값: settings.MEAL_MATCH_THRESHOLD (기본 70.0)
# 임계값 미달 허용 옵션: settings.ALLOW_FALLBACK_SAVE_BELOW (기본 False)
# CSV 가늠 실패 시 최소 kcal: settings.DEFAULT_FALLBACK_KCAL (기본 300.0)
# 자동 저장(프리뷰 아님)은 임계값을 통과(passed) 해야만 진행되도록 수정

# ai/views.py
import csv
import mimetypes
from datetime import date
from typing import Dict, Any, List, Optional

import requests
from django.conf import settings
from django.utils import timezone
from django.db import transaction, IntegrityError
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response

from intakes.models import Food, Meal, MealItem, NutritionLog
from ai.utils import estimate_macros_from_csv  # ✅ CSV 가늠값 사용

# ==============================================
# Hugging Face helpers
# ==============================================
HF_BASE = "https://api-inference.huggingface.co"


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
    """허깅페이스 이미지 분류 호출"""
    model_id = getattr(settings, "HF_IMAGE_MODEL", None)
    if not model_id:
        raise HFError("HF_IMAGE_MODEL 이 설정되지 않았습니다.")
    url = f"{HF_BASE}/models/{model_id}"

    try:
        r = requests.post(url, headers=_hf_headers_binary(), data=image_bytes, timeout=60)
    except requests.RequestException as e:
        raise HFError(f"요청 실패: {e}")

    if r.status_code >= 400:
        raise HFError(f"HF 응답 오류: {r.status_code} {r.text}")

    data = r.json()
    if isinstance(data, list) and data and isinstance(data[0], dict) and "label" in data[0]:
        return data[:top_k]
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


def _extract_macros_from_row(row: Dict[str, Any]) -> Dict[str, float]:
    """
    CSV가 어떤 컬럼명을 쓰든 최대한 유연하게 집계:
      - kcal / calories / energy_kcal
      - protein / protein_g
      - carb / carbs / carbohydrate / carbohydrate_g
      - fat / fat_g
    """
    name_ko = row.get("name_ko") or row.get("ko") or row.get("name") or row.get("food_ko")
    name_en = row.get("name_en") or row.get("en") or row.get("food_en")

    kcal = (
        _to_float(row.get("kcal"))
        or _to_float(row.get("calories"))
        or _to_float(row.get("energy_kcal"))
        or 0.0
    )
    protein = (
        _to_float(row.get("protein"))
        or _to_float(row.get("protein_g"))
        or 0.0
    )
    carbs = (
        _to_float(row.get("carb"))
        or _to_float(row.get("carbs"))
        or _to_float(row.get("carbohydrate"))
        or _to_float(row.get("carbohydrate_g"))
        or 0.0
    )
    fat = (
        _to_float(row.get("fat"))
        or _to_float(row.get("fat_g"))
        or 0.0
    )

    return {
        "label_ko": str(name_ko or name_en or "").strip(),
        "calories": round(kcal or 0.0, 1),
        "protein": round(protein or 0.0, 1),
        "carb": round(carbs or 0.0, 1),
        "fat": round(fat or 0.0, 1),
    }


def _match_csv_by_label(pred_label: str) -> Optional[Dict[str, Any]]:
    """
    AI 라벨과 CSV의 이름(ko/en/synonyms)을 최대한 매칭
    - 우선순위: exact en → exact ko → synonyms → 부분 포함(en/ko)
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
        if _norm(r.get("name_ko")) == label:
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
        if label and (label in _norm(r.get("name_en")) or label in _norm(r.get("name_ko"))):
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
            ctype = getattr(f, "content_type", None) or mimetypes.guess_type(getattr(f, "name", ""))[0]
            if ctype is None or (ctype and ctype.startswith("image/")):
                return f
    # 2) 전체에서 이미지 탐색
    for f in files.values():
        ctype = getattr(f, "content_type", None) or mimetypes.guess_type(getattr(f, "name", ""))[0]
        if ctype and ctype.startswith("image/"):
            return f
    return None


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
        - commit 플래그 지원:
          * 'preview' / '0' / 'false' / 'no' → 저장하지 않고 미리보기만
          * 그 외(기본): 로그인 사용자는 (임계 통과 시) 자동 저장
        - 프리뷰 응답에는 can_save + save_payload 포함 (커밋 버튼에서 그대로 사용)
        """
        # 0) 커밋 모드 파싱
        raw = (request.POST.get("commit") or request.data.get("commit") or "auto").strip().lower()
        commit_preview = raw in ("0", "false", "preview", "no")

        # 1) 파일 (image/photo/file 모두 허용)
        file_obj = _pick_image_file(request)
        if not file_obj:
            return Response({"error": "이미지 파일을 업로드해 주세요. (허용 키: image/photo/file)"}, status=400)
        try:
            image_bytes = file_obj.read()
            if not image_bytes:
                raise ValueError("empty file")
        except Exception:
            return Response({"error": "이미지 파일을 읽을 수 없습니다."}, status=400)

        # 2) HF 추론
        try:
            predictions = hf_image_classify(image_bytes, top_k=5)
        except HFError as e:
            return Response({"error": f"AI 분석 중 오류: {e}"}, status=400)
        except Exception:
            return Response({"error": "server error"}, status=500)

        if not predictions:
            return Response({"error": "인식 결과가 없습니다."}, status=400)

        # 3) 결과 파싱
        def _normalize_label(s: str) -> str:
            return _norm(s)

        top_label = str(predictions[0].get("label", "")).strip()
        try:
            best_score = float(predictions[0].get("score", 0.0))
        except Exception:
            best_score = 0.0

        alternatives = []
        for p in predictions[1:]:
            if not isinstance(p, dict) or not p.get("label"):
                continue
            try:
                score = float(p.get("score", 0.0))
            except Exception:
                score = 0.0
            alternatives.append({"label": p.get("label"), "score": score})

        # 4) DB 매칭
        label_ko: Optional[str] = None
        macros: Dict[str, float] = {}
        found_food = None

        for p in predictions:
            raw_label = p.get("label")
            if not raw_label:
                continue

            food_obj = _find_food_by_label(raw_label)
            if food_obj:
                found_food = food_obj
                label_ko = (getattr(food_obj, "name_ko", None) or getattr(food_obj, "name", None) or "").strip() or top_label
                macros = {
                    "calories": float(getattr(food_obj, "kcal_per_100g", 0.0) or 0.0),
                    "protein":  float(getattr(food_obj, "protein_g_per_100g", 0.0) or 0.0),
                    "carb":     float(getattr(food_obj, "carb_g_per_100g", 0.0) or 0.0),
                    "fat":      float(getattr(food_obj, "fat_g_per_100g", 0.0) or 0.0),
                }
                break

        # 5) CSV 매칭 (DB 실패 시)
        if not macros:
            for p in predictions:
                raw_label = p.get("label")
                if not raw_label:
                    continue
                csv_hit = _match_csv_by_label(raw_label)
                if csv_hit:
                    label_ko = (csv_hit.get("label_ko") or "").strip() or top_label
                    macros = {
                        "calories": float(csv_hit.get("calories", 0.0) or 0.0),
                        "protein":  float(csv_hit.get("protein", 0.0) or 0.0),
                        "carb":     float(csv_hit.get("carb", 0.0) or 0.0),
                        "fat":      float(csv_hit.get("fat", 0.0) or 0.0),
                    }
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

        matched = bool(macros)

        # ✅ 임계/옵션 계산
        threshold = float(getattr(settings, "MEAL_MATCH_THRESHOLD", 70.0))
        allow_fallback_below = bool(getattr(settings, "ALLOW_FALLBACK_SAVE_BELOW", False))
        fallback_kcal = float(getattr(settings, "DEFAULT_FALLBACK_KCAL", 300.0) or 300.0)
        confidence_pct = round(best_score * 100.0, 1)
        passed = bool(matched and (confidence_pct >= threshold))

        # 6) 프리뷰 응답: 미리보기이거나, 비로그인이거나, (임계 미달 포함) 일반적으로 여기서 반환
        if commit_preview or (not request.user.is_authenticated) or (not passed):
            # 기본 응답 값
            source = "unmatched"
            if matched:
                source = "db" if found_food else "csv"

            can_save = False
            save_payload = None
            macros_out = {}

            if request.user.is_authenticated:
                if passed:
                    # 임계 통과 → 정상 저장 가능
                    can_save = True
                    macros_out = macros or {}
                    save_payload = {
                        "label_ko": (label_ko or top_label),
                        "macros": macros_out,
                        "meal_type": meal_type,
                        "source": source,
                        "food_id": getattr(found_food, "id", None),
                    }
                elif allow_fallback_below:
                    # 임계 미달인데 옵션 허용 → CSV 가늠값(없으면 기본 kcal)으로 저장 허용
                    est = estimate_macros_from_csv(label_ko or top_label) if (label_ko or top_label) else None
                    if est and (est.get("calories", 0) or 0) > 0:
                        can_save = True
                        source = "csv_estimate"
                        macros_out = est
                        save_payload = {
                            "label_ko": (label_ko or top_label),
                            "macros": est,
                            "meal_type": meal_type,
                            "source": source,
                            "food_id": None,
                        }
                    else:
                        can_save = True
                        source = "default"
                        macros_out = {"calories": fallback_kcal, "protein": 0.0, "carb": 0.0, "fat": 0.0}
                        save_payload = {
                            "label_ko": (label_ko or top_label),
                            "macros": macros_out,
                            "meal_type": meal_type,
                            "source": source,
                            "food_id": None,
                        }

            return Response(
                {
                    "saved": False,
                    "source": source,
                    "label": top_label,
                    "label_ko": label_ko or top_label,
                    "confidence": confidence_pct,
                    "macros": macros if matched else {},
                    "alternatives": alternatives,
                    "meal_type": meal_type,
                    "can_save": can_save,
                    "has_payload": bool(save_payload),
                    "save_payload": save_payload,
                    # 🔎 디버그
                    "debug": {
                        "is_auth": bool(request.user.is_authenticated),
                        "matched": bool(macros),
                        "db_hit": bool(found_food),
                        "csv_count": len(_load_mfds_rows()),
                        "top_label": top_label,
                        "confidence_pct": confidence_pct,
                        "threshold": threshold,
                        "allow_fallback_below": allow_fallback_below,
                        "fallback_kcal": fallback_kcal,
                    },
                },
                status=200,
            )

        # 7) 자동 저장 (로그인 + 프리뷰 아님 + ✅임계 통과)
        try:
            with transaction.atomic():
                today = date.today()
                meal, _ = Meal.objects.get_or_create(
                    user=request.user,
                    log_date=today,
                    meal_type=meal_type,
                )
                meal_item = MealItem.objects.create(
                    meal=meal,
                    food=found_food,
                    name=(label_ko or top_label),
                    kcal=macros["calories"],
                    protein_g=macros["protein"],
                    carb_g=macros["carb"],
                    fat_g=macros["fat"],
                )
                log, _ = NutritionLog.objects.get_or_create(user=request.user, date=today)
                try:
                    log.recalc()
                except Exception:
                    pass

            updated_consumed = {
                "calories": round(getattr(log, "kcal_total", 0.0) or 0.0, 1),
                "protein":  round(getattr(log, "protein_total_g", 0.0) or 0.0, 1),
                "carbs":    round(getattr(log, "carb_total_g", 0.0) or 0.0, 1),
                "fat":      round(getattr(log, "fat_total_g", 0.0) or 0.0, 1),
            }

            return Response(
                {
                    "saved": True,
                    "source": "db" if found_food else "csv",
                    "updated_consumed": updated_consumed,
                    "label": top_label,
                    "label_ko": label_ko or top_label,
                    "confidence": confidence_pct,
                    "macros": macros,
                    "alternatives": alternatives,
                    "meal_type": meal_type,
                    "meal_item_id": meal_item.id,
                    # 🔎 디버그
                    "debug": {
                        "is_auth": True,
                        "matched": True,
                        "db_hit": bool(found_food),
                        "csv_count": len(_load_mfds_rows()),
                        "top_label": top_label,
                        "confidence_pct": confidence_pct,
                        "threshold": threshold,
                    },
                },
                status=200,
            )
        except IntegrityError as e:
            return Response({"error": f"DB 오류: {e}"}, status=400)
        except Exception as e:
            return Response({"error": f"서버 내부 오류: {e}"}, status=500)

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
          "macros": {"calories": 350, "protein": 20, "carb": 25, "fat": 15},
          "meal_type": "아침|점심|저녁|간식",
          "source": "db|csv|csv_estimate|default",
          "food_id": 123  # 선택
        }
        """
        data = request.data

        label_ko = (data.get("label_ko") or "").strip()
        meal_type = (data.get("meal_type") or "").strip() or "간식"
        source = (data.get("source") or "").strip() or "csv"
        food_id = data.get("food_id")

        macros = data.get("macros") or {}
        try:
            kcal = float(macros.get("calories", 0) or 0)
            protein = float(macros.get("protein", 0) or 0)
            carb = float(macros.get("carb", 0) or 0)
            fat = float(macros.get("fat", 0) or 0)
        except Exception:
            return Response({"error": "macros 형식이 올바르지 않습니다."}, status=400)

        if not label_ko or (kcal == 0 and protein == 0 and carb == 0 and fat == 0):
            return Response({"error": "라벨 또는 영양정보가 비어 있습니다."}, status=400)

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
                meal_item = MealItem.objects.create(
                    meal=meal,
                    food=food_obj,
                    name=label_ko,
                    kcal=kcal,
                    protein_g=protein,
                    carb_g=carb,
                    fat_g=fat,
                )
                log, _ = NutritionLog.objects.get_or_create(user=request.user, date=today)
                try:
                    log.recalc()
                except Exception:
                    pass

            updated_consumed = {
                "calories": round(getattr(log, "kcal_total", 0.0) or 0.0, 1),
                "protein":  round(getattr(log, "protein_total_g", 0.0) or 0.0, 1),
                "carbs":    round(getattr(log, "carb_total_g", 0.0) or 0.0, 1),
                "fat":      round(getattr(log, "fat_total_g", 0.0) or 0.0, 1),
            }

            return Response(
                {
                    "ok": True,
                    "saved": True,
                    "source": source,
                    "meal_item_id": meal_item.id,
                    "updated_consumed": updated_consumed,
                },
                status=200,
            )
        except IntegrityError as e:
            return Response({"error": f"DB 오류: {e}"}, status=400)
        except Exception as e:
            return Response({"error": f"서버 내부 오류: {e}"}, status=500)

    @action(
        detail=False,
        methods=["delete"],
        url_path=r"meal-entry/(?P<item_id>\d+)",
        permission_classes=[IsAuthenticated],
    )
    def delete_meal_entry(self, request, item_id=None):
        """식사 항목 삭제 후 요약 재계산"""
        try:
            meal_item = MealItem.objects.select_related("meal").get(pk=item_id, meal__user=request.user)
        except MealItem.DoesNotExist:
            return Response({"error": "삭제할 식사를 찾을 수 없습니다."}, status=404)

        meal = meal_item.meal
        meal_item.delete()

        log, _ = NutritionLog.objects.get_or_create(user=request.user, date=meal.log_date)
        try:
            log.recalc()
        except Exception:
            pass

        updated_consumed = {
            "calories": round(getattr(log, "kcal_total", 0.0) or 0.0, 1),
            "protein":  round(getattr(log, "protein_total_g", 0.0) or 0.0, 1),
            "carbs":    round(getattr(log, "carb_total_g", 0.0) or 0.0, 1),
            "fat":      round(getattr(log, "fat_total_g", 0.0) or 0.0, 1),
        }

        return Response({"ok": True, "updated_consumed": updated_consumed})
