# ai/utils.py
# intakes/data/mfds_foods.csv에서 평균값을 집계해 가늠 영양소(macros)를 추정.
# MFDS 한글 헤더 자동 인식 + 정규화 + 영→한 동의어 + 퍼지 매칭(rapidfuzz) 지원

from __future__ import annotations

import csv
import re
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional, List, Tuple

from django.conf import settings

try:
    # 퍼지 매칭 (설치되어 있지 않으면 None 처리)
    from rapidfuzz import fuzz, process
except Exception:  # pragma: no cover
    fuzz = None
    process = None

__all__ = [
    "estimate_macros_from_csv",
    "load_mfds_rows",
    "_match_csv_by_label",
]

# ───────────────── 환경/옵션 ─────────────────
FUZZY_SCORE_THRESHOLD = float(getattr(settings, "FUZZY_SCORE_THRESHOLD", 88.0))  # 0~100 추천 82~90
FUZZY_CANDIDATES_LIMIT = int(getattr(settings, "FUZZY_CANDIDATES_LIMIT", 5))

# ───────────────── 동의어(영→한) 매핑 ─────────────────
EN_KO_SYNONYMS = {
    "hamburger": "햄버거",
    "cheeseburger": "치즈버거",
    "spaghetti bolognese": "볼로네제 스파게티",
    "bolognese": "볼로네제",
    "spaghetti": "스파게티",
    "pasta": "파스타",
    "carbonara": "까르보나라",
    "ramen": "라면",
    "udon": "우동",
    "soba": "소바",
    "sushi": "스시",
    "kimbap": "김밥",
    "gimbap": "김밥",
    "fried chicken": "치킨",
    "pork cutlet": "돈까스",
    "tonkatsu": "돈까스",
    "donkatsu": "돈까스",
    "tteokbokki": "떡볶이",
    "rice cake": "떡",
}

# ---------- 내부 유틸 ----------

def _safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default

def _to_float_any(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return None if (math.isnan(x) or math.isinf(x)) else x
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(",", "")  # 1,234.5 → 1234.5
    try:
        x = float(s)
        return None if (math.isnan(x) or math.isinf(x)) else x
    except Exception:
        return None

# 한글/영문/숫자만 남기고, 하이픈/언더스코어는 공백으로 치환
_norm_pat = re.compile(r"[^\w가-힣]+")

def _normalize_label(s: str) -> str:
    """
    간단 라벨 정규화:
      - 소문자화
      - _, - 를 공백으로
      - 한글/영문/숫자 외 기호 제거
      - 연속 공백 축소
    """
    if not s:
        return ""
    s = s.strip().lower().replace("_", " ").replace("-", " ")
    s = _norm_pat.sub(" ", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _pick_key(row: Dict[str, str], patterns: List[re.Pattern]) -> Optional[str]:
    """
    row의 컬럼키들 중 정규식 리스트 중 하나라도 매칭되는 첫 키 반환 (우선순위: 앞에서 뒤로)
    """
    keys = list(row.keys())
    for p in patterns:
        for k in keys:  # 원문 키
            if k and p.search(str(k)):
                return k
        for k in keys:  # 정규화 키(소문자/공백제거)
            kk = re.sub(r"\s+", "", str(k).lower())
            if kk and p.search(kk):
                return k
    return None

@lru_cache(maxsize=1)
def load_mfds_rows() -> Iterable[Dict[str, str]]:
    """
    MFDS CSV를 메모리에 로드. (간단 캐시)
    권장 컬럼(있으면 자동 추출):
      - 식품명, 대표식품명
      - 에너지(kcal), 단백질(g), 탄수화물(g), 지방(g)
    """
    p = getattr(settings, "MFDS_FOOD_CSV", None)
    path: Optional[Path] = None
    if p:
        try:
            path = Path(p)
        except Exception:
            path = None
    if not path:
        # 백업 경로
        try:
            path = Path(settings.BASE_DIR) / "intakes" / "data" / "mfds_foods.csv"
        except Exception:
            path = None
    if not path or not path.exists():
        return []

    rows = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except FileNotFoundError:
        return []
    return rows

# ---------- 퍼블릭 API ----------

def estimate_macros_from_csv(label_ko: str) -> Optional[Dict[str, float]]:
    """
    주어진 한글 라벨(예: '김밥', '샐러드')을 CSV에서 찾아
    평균 칼로리/단백질/탄수화물/지방을 추정해 반환.
    매칭 규칙(순서대로 시도):
      1) 정규화된 완전일치
      2) 부분일치(포함 관계)
    일치가 하나도 없으면 None.
    """
    if not label_ko:
        return None

    target_norm = _normalize_label(label_ko)
    if not target_norm:
        return None

    rows = load_mfds_rows()
    if not rows:
        return None

    exact_hits = []
    partial_hits = []

    for row in rows:
        # MFDS 한글 우선
        name = (row.get("식품명") or row.get("대표식품명") or row.get("name_ko") or row.get("label_ko") or "").strip()
        if not name:
            continue

        name_norm = _normalize_label(name)
        if not name_norm:
            continue

        if name_norm == target_norm:
            exact_hits.append(row)
        elif (target_norm in name_norm) or (name_norm in target_norm):
            partial_hits.append(row)

    def _aggregate(hit_rows: Iterable[Dict[str, str]]) -> Optional[Dict[str, float]]:
        totals = defaultdict(float)
        count = 0
        for r in hit_rows:
            # _row_to_macros를 통일 사용 (헤더 편차 대응)
            m = _row_to_macros(r)
            totals["calories"] += m["calories"]
            totals["protein"]  += m["protein"]
            totals["carb"]     += m["carb"]
            totals["fat"]      += m["fat"]
            count += 1
        if count == 0:
            return None
        return {
            "calories": round(totals["calories"] / count, 2),
            "protein":  round(totals["protein"]  / count, 2),
            "carb":     round(totals["carb"]     / count, 2),
            "fat":      round(totals["fat"]      / count, 2),
        }

    # 1) 완전일치 우선
    agg = _aggregate(exact_hits)
    if agg:
        return agg

    # 2) 부분일치 백업
    agg = _aggregate(partial_hits)
    if agg:
        return agg

    return None

# ---------- MFDS 한글 헤더 최적화: 행 → 표준 macros ----------

def _row_to_macros(row: Dict[str, str]) -> Dict[str, float]:
    """
    MFDS 한글 헤더 최적화:
    1순위: 정확 키로 추출
      - 이름: 식품명 (없으면 대표식품명)
      - kcal: 에너지(kcal)
      - 단백질: 단백질(g)
      - 탄수화물: 탄수화물(g)
      - 지방: 지방(g)
    2순위: 정규식 패턴으로 폴백 (100g 변형 열 포함)
    """
    # ── 이름 ──
    name_ko = (row.get("식품명") or row.get("대표식품명") or row.get("name_ko") or row.get("label_ko") or "").strip()
    if not name_ko:
        name_key = _pick_key(row, [
            re.compile(r"(식품명|대표식품명|name_?ko|label_?ko|품목명|한글명|제품명)", re.I),
        ])
        name_ko = (row.get(name_key) or "").strip() if name_key else ""

    # ── 정확 키 우선 ──
    def _get_num(*keys) -> Optional[float]:
        for k in keys:
            if k in row:
                v = _to_float_any(row.get(k))
                if v is not None:
                    return v
        return None

    kcal    = _get_num("에너지(kcal)", "kcal", "calories", "energy_kcal")
    protein = _get_num("단백질(g)", "protein", "protein_g")
    carb    = _get_num("탄수화물(g)", "carb", "carbs", "carbohydrate", "carbohydrate_g")
    fat     = _get_num("지방(g)", "fat", "fat_g")

    # ── 패턴 폴백 ──
    if kcal is None:
        kcal_key = _pick_key(row, [
            re.compile(r"(에너지|열량|kcal)", re.I),
            re.compile(r"(energy.*kcal|calories?)", re.I),
        ])
        if kcal_key: kcal = _to_float_any(row.get(kcal_key))

    if protein is None:
        protein_key = _pick_key(row, [re.compile(r"(단백질|protein(_g)?)", re.I)])
        if protein_key: protein = _to_float_any(row.get(protein_key))

    if carb is None:
        carb_key = _pick_key(row, [re.compile(r"(탄수화물|carbo(hydrate)?s?)", re.I)])
        if carb_key: carb = _to_float_any(row.get(carb_key))

    if fat is None:
        fat_key = _pick_key(row, [re.compile(r"(지방|fat(_g)?)", re.I)])
        if fat_key: fat = _to_float_any(row.get(fat_key))

    # ── 100g 변형 열 폴백 ──
    if kcal is None:
        kcal100_key = _pick_key(row, [re.compile(r"(100g.*에너지|에너지.*100g|kcal.*100g|100g.*kcal)", re.I)])
        if kcal100_key: kcal = _to_float_any(row.get(kcal100_key))
    if protein is None:
        pro100_key = _pick_key(row, [re.compile(r"(100g.*단백질|단백질.*100g|protein.*100g)", re.I)])
        if pro100_key: protein = _to_float_any(row.get(pro100_key))
    if carb is None:
        carb100_key = _pick_key(row, [re.compile(r"(100g.*탄수화물|탄수화물.*100g|carb.*100g)", re.I)])
        if carb100_key: carb = _to_float_any(row.get(carb100_key))
    if fat is None:
        fat100_key = _pick_key(row, [re.compile(r"(100g.*지방|지방.*100g|fat.*100g)", re.I)])
        if fat100_key: fat = _to_float_any(row.get(fat100_key))

    # 폴백: 없으면 0
    kcal    = round(kcal or 0.0, 1)
    protein = round(protein or 0.0, 1)
    carb    = round(carb or 0.0, 1)
    fat     = round(fat or 0.0, 1)

    return {
        "label_ko": name_ko,
        "calories": kcal,
        "protein":  protein,
        "carb":     carb,
        "fat":      fat,
    }

# ---------- CSV 매칭(영/한/동의어 + 퍼지) ----------

def _match_csv_by_label(pred_label: str) -> Optional[Dict[str, float]]:
    """
    AI 라벨과 CSV의 이름(ko/en/synonyms)을 최대한 매칭
    - 우선순위: exact en → exact ko → synonyms → 부분 포함(en/ko) → 🔥 퍼지 매칭(ko 목록)
    - 영라벨은 EN_KO_SYNONYMS를 통해 한글로 치환 후 시도
    """
    rows = load_mfds_rows()
    if not rows:
        return None

    # 0) 입력 정규화
    label_raw = (pred_label or "").strip()
    label = _normalize_label(label_raw)
    if not label:
        return None

    # 0-1) 영→한 동의어 치환
    for en, ko in EN_KO_SYNONYMS.items():
        if _normalize_label(en) == label:
            label_raw = ko
            label = _normalize_label(label_raw)
            break

    # 1) exact en
    for r in rows:
        if _normalize_label(r.get("name_en") or "") == label:
            return _row_to_macros(r)

    # 2) exact ko (MFDS 한글 키 포함)
    for r in rows:
        if _normalize_label(r.get("식품명") or "") == label:
            return _row_to_macros(r)
        if _normalize_label(r.get("대표식품명") or "") == label:
            return _row_to_macros(r)
        if _normalize_label(r.get("name_ko") or "") == label:
            return _row_to_macros(r)
        if _normalize_label(r.get("label_ko") or "") == label:
            return _row_to_macros(r)

    # 3) synonyms (쉼표/세미콜론 구분)
    for r in rows:
        syn = r.get("synonyms") or r.get("alias") or ""
        if syn:
            cand = [_normalize_label(x) for x in str(syn).replace(";", ",").split(",") if x.strip()]
            if label in cand:
                return _row_to_macros(r)

    # 4) 부분 포함 (en/ko)
    for r in rows:
        if label and (
            label in _normalize_label(r.get("name_en") or "") or
            label in _normalize_label(r.get("식품명") or "") or
            label in _normalize_label(r.get("대표식품명") or "") or
            label in _normalize_label(r.get("name_ko") or "") or
            label in _normalize_label(r.get("label_ko") or "")
        ):
            return _row_to_macros(r)

    # 5) 🔥 퍼지 매칭 (실제 항목명만 후보로 → 오탐 감소)
    if process and fuzz:
        ko_names: List[str] = []
        idx_map: Dict[str, List[int]] = {}
        for i, r in enumerate(rows):
            for key in ("식품명", "대표식품명", "name_ko", "label_ko"):
                nm = (r.get(key) or "").strip()
                if not nm:
                    continue
                if nm not in idx_map:
                    idx_map[nm] = []
                    ko_names.append(nm)
                idx_map[nm].append(i)

        def _score(a: str, b: str) -> float:
            # 정규화된 질의 vs 원문 후보
            return max(
                fuzz.token_set_ratio(a, _normalize_label(b)),
                fuzz.partial_ratio(a, _normalize_label(b)),
            )

        matches: List[Tuple[str, float, int]] = process.extract(
            query=_normalize_label(label_raw),   # 정규화된 질의
            choices=ko_names,                   # 원문 후보(정규화는 scorer에서 수행)
            scorer=_score,
            limit=FUZZY_CANDIDATES_LIMIT,
        )

        for name, score, _ in matches:
            if score >= FUZZY_SCORE_THRESHOLD:
                for row_idx in idx_map.get(name, []):
                    return _row_to_macros(rows[row_idx])

    # 퍼지 매칭 불가 or 임계 미달 → 실패
    return None
