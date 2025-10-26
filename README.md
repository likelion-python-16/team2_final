# 🏋️ Team2 Final — Healthcare Todo App

AI 기반 **운동·식단·생활 루틴 관리 웹앱**
Django + DRF + Postgres + Docker Compose 기반 프로젝트

---

## 🚀 기능 요약

- **Workout 관리**
  - 주간 운동 플랜 생성/수정
  - TaskItem(세트, 반복수, 강도, 완료여부) 저장
  - Dashboard에서 오늘 운동 진척도 확인

- **식단 관리**
  - 사진 업로드 → AI 자동 분석 (칼로리·영양소 추출)
  - NutritionLog 집계 + DailyGoal 반영

- **Dashboard**
  - 오늘의 운동/식단/목표 합계
  - 진행도 Progress Ring 시각화

- **AI 인사이트**
  - Hugging Face 이미지/텍스트 모델 연동
  - 개인 맞춤 식단/운동 추천

- **기타**
  - JWT 로그인 (SimpleJWT)
  - 관리자 페이지(/admin/)
  - OpenAPI 문서 (/docs, /redoc, /openapi.json)
  - Prometheus 메트릭 지원 (옵션)

---

# 🚀 Team2 Final — AWS 배포 종합 가이드
(EC2 + Docker Compose + Gunicorn/Nginx + RDS + IAM/S3 + 모니터링 준비)

> 이 문서는 EC2, RDS(Postgres), Docker Compose, Gunicorn/Nginx, IAM Role, S3 연동을 기반으로 한 **운영 배포 절차 및 트러블슈팅 가이드**입니다.
> 주요 명령어, 확인 포인트, 오류와 해결책을 포함합니다.

---

## 0) 서버 접속 & 디렉토리
```bash
ssh -i ~/.ssh/team2-final-key.pem ubuntu@<EC2_PUBLIC_IP>
cd ~/app/team_final-main
1) EC2 관리
상태 확인
bash
코드 복사
uname -a
top -b -n1 | head -20
free -m
df -h /
메모리 여유: 150MB 이상 권장

디스크 사용률: 80%↑ 시 Docker prune 필요

EC2 삭제(예시)
bash
코드 복사
aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress]' --output table
aws ec2 terminate-instances --instance-ids <INSTANCE_ID>
2) Docker Compose 운영
bash
코드 복사
# 기동 및 빌드
sudo docker compose up -d --build

# 상태 확인
docker compose ps

# Nginx 테스트 & 재시작
docker compose exec -T nginx nginx -t && docker compose restart nginx

# 전체 재시작
sudo docker compose down
sudo docker compose up -d

# 용량 정리
docker system prune -af
docker volume prune -f
3) Nginx ↔ Gunicorn 튜닝
Nginx 주요 포인트
upstream keepalive 적용

proxy timeout / next_upstream 설정

healthz/readyz는 GET 사용

bash
코드 복사
curl -s http://127.0.0.1/healthz
curl -s http://127.0.0.1/readyz
Gunicorn 옵션 (docker-compose.yml)
yaml
코드 복사
GUNICORN_CMD_ARGS: >
  --bind=0.0.0.0:8000
  --workers=2
  --threads=2
  --timeout=60
  --keep-alive=15
4) 헬스체크 & 스모크 테스트
bash
코드 복사
# 헬스 확인
curl -s http://127.0.0.1/healthz
curl -s http://127.0.0.1/readyz

# API 스모크
ACCESS=$(curl -s -X POST http://127.0.0.1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"<USER>","password":"<PASS>"}' \
| python3 -c 'import sys,json;print(json.load(sys.stdin)["access"])')

DATE=$(date +%F)

curl -s -H "Authorization: Bearer $ACCESS" \
  "http://127.0.0.1/api/workoutplans/summary/?date=$DATE"
5) RDS(Postgres) 전환
.env.prod 예시
dotenv
코드 복사
DB_ENGINE=django.db.backends.postgresql
DB_HOST=team2-final-db.c6l0a4weokiv.us-east-1.rds.amazonaws.com
DB_PORT=5432
POSTGRES_DB=team2final
POSTGRES_USER=team2
POSTGRES_PASSWORD=<SECRET>
연결 확인
bash
코드 복사
docker compose exec -T api bash -lc '
python - <<PY
import psycopg2, os
print("Trying DB:", os.environ["DB_HOST"])
conn = psycopg2.connect(
  host=os.environ["DB_HOST"],
  dbname=os.environ["POSTGRES_DB"],
  user=os.environ["POSTGRES_USER"],
  password=os.environ["POSTGRES_PASSWORD"],
  connect_timeout=5
)
print("RDS OK:", conn.get_dsn_parameters())
conn.close()
PY
'
6) IAM Role & S3
IAM Role 확인
bash
코드 복사
curl -s http://169.254.169.254/latest/meta-data/iam/info
aws sts get-caller-identity
S3 업로드 확인
bash
코드 복사
docker compose exec -T api bash -lc '
python - <<PY
import boto3
bucket="team2-final-media-0118"
key="test/healthcheck.txt"
s3 = boto3.client("s3")
s3.put_object(Bucket=bucket, Key=key, Body=b"ok")
head = s3.head_object(Bucket=bucket, Key=key)
print("S3 HEAD ok, size=", head["ContentLength"])
PY
'
7) 자주 발생하는 문제 & 해결
DJANGO_ALLOWED_HOSTS 경고
→ .env.prod 에 DJANGO_ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS 추가

Nginx connect()/recv() failed
→ Gunicorn keep-alive/timeout 옵션 조정

SSH 느림
→ 재부팅 or Stop/Start, t3.small 업그레이드

S3 404/AccessDenied
→ IAM Role 권한 확인, 버킷명/리전 점검

DB 연결 실패
→ RDS 보안그룹 5432 확인, 환경변수 값 재검증

8) 빠른 진단 번들
bash
코드 복사
docker compose ps
docker compose logs --since=3m api | tail -n 100
docker compose logs --since=3m nginx | egrep -i "error|connect|recv" || true
9) 체크리스트
 EC2 접속/리소스 확인

 Docker Compose 서비스 Healthy

 헬스체크 200 OK

 RDS 연결 OK

 IAM Role + S3 업로드 OK
