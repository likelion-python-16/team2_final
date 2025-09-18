FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 시스템 의존성 (필요 최소)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

# 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스
COPY . .

# 포트
EXPOSE 8001

# 헬스체크(옵션)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:8001/healthz || exit 1

# 실행
CMD ["bash", "-lc", "python manage.py migrate && python manage.py runserver 0.0.0.0:8001"]
