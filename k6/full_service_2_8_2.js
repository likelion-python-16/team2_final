// k6/full_service_2_8_2.js
// 2-8-2 전체 서비스 부하 테스트 (8개 엔드포인트)

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

// BASE_URL 우선순위
// 1) __ENV.K6_HOST        ← k6 실행 시 -e K6_HOST=...
// 2) http://team2_nginx   ← 배포 nginx 서비스
const BASE_URL = __ENV.K6_HOST || 'http://team2_nginx';

// JWT 토큰 (필수)
const TOKEN = __ENV.K6_JWT || '';
if (!TOKEN) {
  throw new Error('❌ K6_JWT 환경변수가 없습니다.');
}

// 날짜: 기본은 오늘, K6_DATE로 오버라이드 가능
const DEFAULT_DATE = (() => {
  if (__ENV.K6_DATE) return __ENV.K6_DATE;
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
})();

// 실제 음식 이미지 바이너리 (init 단계에서 1번만 읽힘)
// ./k6/sample.jpg 기준 (ai_meal.js와 동일)
const bin = open('./sample.jpg', 'b');

// 공통 메트릭
const allDuration = new Trend('all_req_duration', true);
const allFailed = new Rate('all_req_failed');

// 2-8-2 VU 패턴
export const options = {
  scenarios: {
    full_service_2_8_2: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 100 }, // ramp-up (0 → 100)
        { duration: '8m', target: 100 }, // steady (100)
        { duration: '2m', target: 0 },   // ramp-down (100 → 0)
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    all_req_failed: ['rate<0.05'],     // 전체 에러율 5% 미만
    all_req_duration: ['p(95)<1000'],  // 전체 p95 1초 미만
  },
};

// 공통 헤더/기록 유틸
function authParams(extraHeaders = {}) {
  return {
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      ...extraHeaders,
    },
  };
}

function record(res, label) {
  allDuration.add(res.timings.duration, { label });
  allFailed.add(res.status >= 400, { label });
  check(res, {
    [`${label}: status is 2xx/3xx`]: (r) => r.status >= 200 && r.status < 400,
  });
}

// ---- 8개 엔드포인트 호출 함수 ----

// 1) healthz (nginx 루트)
function getHealthz() {
  const url = `${BASE_URL}/healthz`;
  const res = http.get(url);
  record(res, 'healthz');
}

// 2) 내 정보
function getMe() {
  const url = `${BASE_URL}/api/users/me/`;
  const res = http.get(url, authParams());
  record(res, 'users_me');
}

// 3) 플랜 요약 (by date)
function getWorkoutSummary(date) {
  const url = `${BASE_URL}/api/workoutplans/summary/?date=${date}`;
  const res = http.get(url, authParams());
  record(res, 'workout_summary');
}

// 4) 플랜 상세 (by date)
function getWorkoutByDate(date) {
  const url = `${BASE_URL}/api/workoutplans/by-date/?date=${date}`;
  const res = http.get(url, authParams());
  record(res, 'workout_by_date');
}

// 5) 오늘 플랜
function getWorkoutToday() {
  const url = `${BASE_URL}/api/workoutplans/today/`;
  const res = http.get(url, authParams());
  record(res, 'workout_today');
}

// 6) Goals
function getGoals() {
  const url = `${BASE_URL}/api/goals/`;
  const res = http.get(url, authParams());
  record(res, 'goals');
}

// 7) 주간 진행률 (Tasks)
function getTasksWeeklyProgress() {
  const url = `${BASE_URL}/api/tasks/weekly_progress/`;
  const res = http.get(url, authParams());
  record(res, 'tasks_weekly_progress');
}

// 8) AI 식단 분석 (meal-analyze) — ai_meal.js와 동일한 형식
function postAiMealAnalyze() {
  const url = `${BASE_URL}/api/ai/meal-analyze/`;

  const formData = {
    image: http.file(bin, 'sample.jpg', 'image/jpeg'),
    meal_time: 'breakfast',
  };

  const res = http.post(url, formData, authParams());
  record(res, 'ai_meal_analyze');
}

// ---- VU 시나리오 본문 ----

export default function () {
  const date = DEFAULT_DATE; // 매 iteration에서 동일 날짜 사용

  // 1) 헬스 체크
  getHealthz();

  // 2) 유저 정보
  getMe();

  // 3) 플랜 관련 (요약 → 상세 → 오늘)
  getWorkoutSummary(date);
  getWorkoutByDate(date);
  getWorkoutToday();

  // 4) 목표 + 주간 진행률
  getGoals();
  getTasksWeeklyProgress();

  // 5) AI 식단 분석은 일부 요청에서만 수행 (0.3 확률)
  if (Math.random() < 0.3) {
    postAiMealAnalyze();
  }

  // 각 VU 루프 간 간격
  sleep(1);
}
