// k6/ai_meal.js — 로컬/배포 공통 부하 테스트
import http from 'k6/http';
import { check, sleep } from 'k6';

/**
 * BASE_URL 우선순위
 * 1) __ENV.K6_HOST        ← k6 실행 시 -e K6_HOST=...
 * 2) http://team2_nginx   ← 배포 nginx 서비스
 *
 * 로컬에서는 지금처럼 -e K6_HOST="http://team2_local_nginx" 로 덮어쓰기.
 */
const BASE_URL = __ENV.K6_HOST || 'http://team2_nginx';

/**
 * JWT 토큰 (필수)
 */
const TOKEN = __ENV.K6_JWT || '';
if (!TOKEN) {
  throw new Error('❌ K6_JWT 환경변수가 없습니다.');
}

/**
 * 실제 음식 이미지 바이너리
 * - init 단계에서 단 1번만 읽음
 * - ./k6/sample.jpg 를 기준으로 함
 */
const bin = open('./sample.jpg', 'b');

// ✅ 2-4-3: 로컬 baseline 부하 시나리오 (30 VU, 5분)
export const options = {
  scenarios: {
    ai_meal_baseline: {
      executor: 'constant-vus',
      vus: 30,         // 동시 30명
      duration: '5m',  // 5분 동안 부하
    },
  },
};

export default function () {
  const url = `${BASE_URL}/api/ai/meal-analyze/`;

  const formData = {
    image: http.file(bin, 'sample.jpg', 'image/jpeg'),
    meal_time: 'breakfast',
  };

  const res = http.post(url, formData, {
    headers: {
      Authorization: `Bearer ${TOKEN}`,
    },
  });

  // 간단한 체크: 2xx 여야 성공
  check(res, {
    'status is 2xx': (r) => r.status >= 200 && r.status < 300,
  });

  // 디버깅용 로그 (필요할 때만 잠깐 열기)
  // console.log(
  //   `k6 ai_meal: status=${res.status} body=${String(res.body).slice(0, 200)}`
  // );

  sleep(1);
}
