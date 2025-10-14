import csv
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from intakes.models import Food


ALIASES = {
    "name": [
        "식품명", "식품명(국문)", "식품명(한글)", "제품명", "품목명", "제품(식품)명", "FoodName"
    ],
    "kcal": [
        "에너지(kcal)", "에너지 (kcal)", "열량(kcal)", "열량 (kcal)", "kcal", "열량"
    ],
    "protein": [
        "단백질(g)", "단백질 (g)", "단백질", "protein(g)", "protein (g)"
    ],
    "carb": [
        "탄수화물(g)", "탄수화물 (g)", "탄수화물", "carbohydrate(g)", "carbohydrate (g)"
    ],
    "fat": [
        "지방(g)", "지방 (g)", "지방", "fat(g)", "fat (g)"
    ],
}


def _normalize_float(v):
    """
    CSV에 흔한 형태들:
    '', '-', 'NA', '<0.1', '1,234.5', '  12.0  '
    → float 또는 0.0
    """
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s or s in {"-", "NA", "N/A", "na"}:
        return 0.0
    if s.startswith("<"):
        # 예: <0.1 → 0.1로 최소치 가정
        s = s[1:]
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _first_present(row, candidates):
    for key in candidates:
        if key in row and str(row[key]).strip() != "":
            return row[key]
    return None


def parse_row(row):
    """
    현재 프로젝트의 Food 모델 필드명에 딱 맞춘 매핑.
    CSV는 '100g당' 영양성분을 기준으로 들어있다고 가정.
    (다른 단위면 사전에 해당 CSV 컬럼을 100g 기준으로 변환해 주세요.)
    """
    name = _first_present(row, ALIASES["name"])
    kcal = _normalize_float(_first_present(row, ALIASES["kcal"]))
    protein = _normalize_float(_first_present(row, ALIASES["protein"]))
    carb = _normalize_float(_first_present(row, ALIASES["carb"]))
    fat = _normalize_float(_first_present(row, ALIASES["fat"]))

    if not name:
        return None  # 이름 없으면 스킵

    return {
        "name": str(name).strip(),
        "kcal_per_100g": kcal,
        "protein_g_per_100g": protein,
        "carb_g_per_100g": carb,
        "fat_g_per_100g": fat,
    }


class Command(BaseCommand):
    help = "식약처 영양성분 CSV를 읽어 Food 테이블을 채웁니다 (100g 기준)."

    def add_arguments(self, parser):
        parser.add_argument("--path", required=True, help="CSV 파일 경로 (utf-8 또는 utf-8-sig)")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["path"])
        if not path.exists():
            raise CommandError(f"CSV 파일을 찾을 수 없습니다: {path}")

        # utf-8-sig을 우선 시도 → BOM 제거
        for enc in ("utf-8-sig", "utf-8"):
            try:
                f = path.open("r", newline="", encoding=enc)
                break
            except UnicodeDecodeError:
                f = None
        if f is None:
            raise CommandError("인코딩을 열 수 없습니다 (utf-8-sig / utf-8 실패).")

        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise CommandError("CSV 헤더를 읽을 수 없습니다.")

        created, updated, skipped = 0, 0, 0

        for idx, row in enumerate(reader, start=2):  # 1행 헤더라 가정
            data = parse_row(row)
            if not data:
                skipped += 1
                continue

            # name 기준 upsert
            obj, is_created = Food.objects.update_or_create(
                name=data["name"],
                defaults={
                    "kcal_per_100g": data["kcal_per_100g"],
                    "protein_g_per_100g": data["protein_g_per_100g"],
                    "carb_g_per_100g": data["carb_g_per_100g"],
                    "fat_g_per_100g": data["fat_g_per_100g"],
                },
            )
            if is_created:
                created += 1
            else:
                updated += 1

            # 간헐적으로 진행상황 출력(대용량 대비)
            if (created + updated + skipped) % 1000 == 0:
                self.stdout.write(f"... {created+updated+skipped} rows processed")

        self.stdout.write(self.style.SUCCESS(
            f"완료! created={created}, updated={updated}, skipped={skipped}"
        ))
