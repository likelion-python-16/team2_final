"""Utility helpers for looking up nutrition information from the MFDS CSV.

The CSV is relatively large (~MB) so we lazily load and cache the parsed
structure on first use.  We expose a single ``find_food`` helper that accepts a
string label (either Korean or English) and returns a dictionary with a Korean
label and macro information if we can map the label to a known food.

If the CSV lookup fails we fall back to a small hand-curated dictionary so that
common English labels returned by the vision model still resolve to reasonable
macros.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional

CSV_PATH = Path(__file__).resolve().parent / "mfds_foods.csv"

_NORMALIZE_RE = re.compile(r"[^0-9a-zA-Z가-힣]")


def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    return _NORMALIZE_RE.sub("", text).lower()


def _to_float(value: str) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class FoodEntry:
    label_ko: str
    serving_size: Optional[str]
    macros: Dict[str, Optional[float]]
    source: str = "csv"


def _iter_synonyms(row: Dict[str, str]) -> Iterable[str]:
    names = set()
    for key in ("식품명", "대표식품명", "식품중분류명", "식품소분류명"):
        value = (row.get(key) or "").strip()
        if not value:
            continue
        names.add(value)
        names.update(part.strip() for part in value.replace("_", " ").split() if part.strip())
    return names


@lru_cache(maxsize=1)
def _build_index():
    index: Dict[str, FoodEntry] = {}
    aliases = []

    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                label = (row.get("식품명") or "").strip()
                if not label:
                    continue

                macros = {
                    "calories": _to_float(row.get("에너지(kcal)")),
                    "protein": _to_float(row.get("단백질(g)")),
                    "carb": _to_float(row.get("탄수화물(g)")),
                    "fat": _to_float(row.get("지방(g)")),
                }
                entry = FoodEntry(
                    label_ko=label,
                    serving_size=(row.get("영양성분함량기준량") or "").strip() or None,
                    macros=macros,
                    source="csv",
                )

                for synonym in _iter_synonyms(row):
                    key = _normalize(synonym)
                    if not key:
                        continue
                    if key not in index:
                        index[key] = entry
                        aliases.append(key)

    return index, aliases


# Fallback dictionary for common English labels the CSV does not cover directly.
_ENGLISH_FALLBACK = {
    "bibimbap": FoodEntry("비빔밥", None, {"calories": 550, "protein": 22, "carb": 72, "fat": 18}, source="fallback"),
    "bulgogi": FoodEntry("불고기", None, {"calories": 480, "protein": 32, "carb": 28, "fat": 24}, source="fallback"),
    "kimbap": FoodEntry("김밥", None, {"calories": 390, "protein": 13, "carb": 52, "fat": 12}, source="fallback"),
    "ramen": FoodEntry("라면", None, {"calories": 470, "protein": 15, "carb": 64, "fat": 16}, source="fallback"),
    "kimchijjigae": FoodEntry("김치찌개", None, {"calories": 320, "protein": 20, "carb": 16, "fat": 18}, source="fallback"),
    "tteokbokki": FoodEntry("떡볶이", None, {"calories": 520, "protein": 11, "carb": 86, "fat": 12}, source="fallback"),
    "friedchicken": FoodEntry("치킨", None, {"calories": 640, "protein": 34, "carb": 32, "fat": 40}, source="fallback"),
    "pizza": FoodEntry("피자", None, {"calories": 620, "protein": 26, "carb": 64, "fat": 26}, source="fallback"),
    "salad": FoodEntry("샐러드", None, {"calories": 220, "protein": 8, "carb": 18, "fat": 12}, source="fallback"),
    "sushi": FoodEntry("스시", None, {"calories": 320, "protein": 24, "carb": 42, "fat": 6}, source="fallback"),
    "sandwich": FoodEntry("샌드위치", None, {"calories": 430, "protein": 20, "carb": 48, "fat": 16}, source="fallback"),
    "pasta": FoodEntry("파스타", None, {"calories": 520, "protein": 20, "carb": 74, "fat": 14}, source="fallback"),
    "yogurt": FoodEntry("요거트", None, {"calories": 180, "protein": 12, "carb": 18, "fat": 6}, source="fallback"),
    "toast": FoodEntry("토스트", None, {"calories": 310, "protein": 10, "carb": 38, "fat": 12}, source="fallback"),
    "steak": FoodEntry("스테이크", None, {"calories": 680, "protein": 55, "carb": 0, "fat": 50}, source="fallback"),
    "hamburger": FoodEntry("햄버거", None, {"calories": 540, "protein": 28, "carb": 45, "fat": 28}, source="fallback"),
    "curry": FoodEntry("카레", None, {"calories": 490, "protein": 18, "carb": 60, "fat": 20}, source="fallback"),
    "apple": FoodEntry("사과", None, {"calories": 95, "protein": 0.5, "carb": 25, "fat": 0.3}, source="fallback"),
    "banana": FoodEntry("바나나", None, {"calories": 105, "protein": 1.3, "carb": 27, "fat": 0.4}, source="fallback"),
    "coffee": FoodEntry("커피", None, {"calories": 5, "protein": 0.1, "carb": 0, "fat": 0}, source="fallback"),
}

DEFAULT_ENTRY = FoodEntry(
    label_ko="일반 식사",
    serving_size=None,
    macros={"calories": 450, "protein": 20, "carb": 55, "fat": 16},
    source="default",
)


def find_food(label: Optional[str]) -> Optional[FoodEntry]:
    key = _normalize(label)
    if not key:
        return None

    index, aliases = _build_index()
    entry = index.get(key)
    if entry:
        return entry

    # For Korean labels that are not an exact match, attempt a fuzzy lookup.
    candidates = get_close_matches(key, aliases, n=1, cutoff=0.9)
    if candidates:
        match = candidates[0]
        candidate_entry = index.get(match)
        if candidate_entry:
            return candidate_entry

    # English fallback dictionary.
    fallback = _ENGLISH_FALLBACK.get(key)
    if fallback:
        return fallback

    return None


__all__ = ["find_food", "DEFAULT_ENTRY"]
