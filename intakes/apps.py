# intakes/apps.py
from django.apps import AppConfig

class IntakesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "intakes"

    def ready(self):
        # ⚠️ import 시점에 signals 등록
        #    (함수 호출 아님, 모듈 임포트만으로 데코레이터가 연결됨)
        import intakes.signals  # noqa: F401
