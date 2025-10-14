# intakes/management/commands/import_mfds_foods.py
import csv
from pathlib import Path
import importlib.resources as pkg_resources

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from intakes.models import Food


# CSV 헤더 별칭
ALIASES = {
    "name": [
        "식품명", "식품명(국문)", "식품명(한글)", "제품명", "품목명", "제품(식품)명",
        "FoodName", "name", "Name",
    ],
    "kcal": [
        "에너지(kcal)", "에너지 (kcal)", "열량(kcal)", "열량 (kcal)", "kcal", "열량",
        "Energy(kcal)", "ENERGY_KCAL",
    ],
    "protein": [
        "단백질(g)", "단백질 (g)", "단백질", "protein(g)", "protein (g)", "Protein(g)",
    ],
    "carb": [
        "탄수화물(g)", "탄수화물 (g)", "탄수화물", "carbohydrate(g)", "carbohydrate (g)",
        "Carbohydrate(g)",
    ],
    "fat": [
        "지방(g)", "지방 (g)", "지방", "fat(g)", "fat (g)", "Fat(g)",
    ],
}


def _normalize_float(v):
    """
    '', '-', 'NA', '<0.1', '1,234.5', '  12.0  '  → float 또는 0.0
    """
    if v is None:
        return 0.0
    s = str(v).strip().strip('"').strip("'")
    if not s or s in {"-", "NA", "N/A", "na"}:
        return 0.0
    if s.startswith("<"):  # 예: <0.1 → 0.1 최소치 가정
        s = s[1:]
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _first_present(row, candidates):
    # 헤더 키는 DictReader 그대로 사용 (대소문자/공백 차이까지 감안해 두벌 체크)
    for key in candidates:
        if key in row and str(row[key]).strip() != "":
            return row[key]
    # 느슨한 매칭: 소문자/양끝공백 제거 비교
    lowered = {k.strip().lower(): k for k in row.keys()}
    for key in candidates:
        lk = key.strip().lower()
        if lk in lowered:
            v = row[lowered[lk]]
            if str(v).strip() != "":
                return v
    return None


def parse_row(row):
    """
    현재 프로젝트 Food 모델 필드에 정확히 매핑.
    CSV는 '100g당' 기준이라고 가정.
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


def _resolve_default_csv_path() -> Path:
    """
    --path 미지정 시 intakes/data/mfds_foods.csv를 기본으로 사용.
    패키지 리소스(files) → 로컬 경로 순으로 시도.
    """
    try:
        base = pkg_resources.files("intakes").joinpath("data")
        p = Path(base / "mfds_foods.csv")
        if p.exists():
            return p
    except Exception:
        pass
    # fallback: 소스 트리 기준
    return Path(__file__).resolve().parents[2] / "intakes" / "data" / "mfds_foods.csv"


def _open_text_file(path: Path):
    """
    인코딩 자동 시도. (utf-8-sig → utf-8)
    """
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return path.open("r", newline="", encoding=enc)
        except UnicodeDecodeError:
            continue
    raise CommandError("인코딩을 열 수 없습니다 (utf-8-sig / utf-8 실패).")


def _detect_dialect(sample: str):
    """
    csv.Sniffer로 구분자 감지. 실패 시 콤마 기본.
    """
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=[",", ";", "\t"])
        return dialect
    except Exception:
        class _Default(csv.Dialect):
            delimiter = ","
            quotechar = '"'
            doublequote = True
            skipinitialspace = True
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL
        return _Default


class Command(BaseCommand):
    help = "식약처 영양성분 CSV를 읽어 Food 테이블을 채웁니다 (100g 기준)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            required=False,
            help="CSV 파일 경로 (미지정 시 intakes/data/mfds_foods.csv 사용; utf-8/utf-8-sig)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB에 반영하지 않고 파싱/매핑 결과만 집계",
        )
        parser.add_argument(
            "--progress-every",
            type=int,
            default=1000,
            help="진행률 출력 간격 (기본 1000행)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="최대 몇 행까지만 처리(테스트용)",
        )


    @transaction.atomic
    def handle(self, *args, **opts):
        # 경로 결정
        path = Path(opts["path"]) if opts.get("path") else _resolve_default_csv_path()
        if not path.exists():
            raise CommandError(f"CSV 파일을 찾을 수 없습니다: {path}")

        # 파일 열기 + 샘플로 dialect 감지
        with _open_text_file(path) as fh:
            head_sample = fh.read(4096)
            fh.seek(0)
            dialect = _detect_dialect(head_sample)

            reader = csv.DictReader(fh, dialect=dialect)
            if reader.fieldnames is None:
                raise CommandError("CSV 헤더를 읽을 수 없습니다.")
            # 공백 헤더 방지(선제 정리)
            reader.fieldnames = [h.strip() if h else "" for h in reader.fieldnames]

            created, updated, skipped, seen = 0, 0, 0, 0
            dry_run = bool(opts["dry_run"])
            every = int(opts["progress_every"]) if opts["progress_every"] else 1000
            limit = opts.get("limit")

            for row in reader:
                seen += 1
                data = parse_row(row)
                if not data:
                    skipped += 1
                    # 진행 출력
                    if every and seen % every == 0:
                        self.stdout.write(f"... {seen} rows processed")
                    if limit and seen >= limit:
                        break
                    continue

                if dry_run:
                    # dry-run: 실제 DB write 없음
                    pass
                else:
                    # name 기준 upsert
                    _, is_created = Food.objects.update_or_create(
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

                # 진행 출력
                if every and seen % every == 0:
                    self.stdout.write(f"... {seen} rows processed")

                if limit and seen >= limit:
                    break

            # dry-run일 때 updated/created는 0으로 유지됨
            self.stdout.write(self.style.SUCCESS(
                f"완료! rows={seen}, created={created}, updated={updated}, skipped={skipped} "
                f"{'(dry-run)' if dry_run else ''}"
            ))

            # dry-run이면 트랜잭션 롤백
            if dry_run:
                raise CommandError("Dry-run: 트랜잭션을 롤백합니다(의도된 종료).")
