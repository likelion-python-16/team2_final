// k6/ai_meal_debug.js
import http from 'k6/http';
import { sleep } from 'k6';

const BASE_URL = __ENV.K6_HOST || 'http://team2_local_nginx';
const TOKEN = __ENV.K6_JWT || '';

if (!TOKEN) {
  throw new Error('❌ K6_JWT 환경변수가 없습니다.');
}

// ✅ init 단계(전역)에서 단 1번 실행 → 이미지 읽기
const bin = open('./sample.jpg', 'b');

export const options = {
  vus: 1,
  duration: '1s',
};

export default function () {
  const url = `${BASE_URL}/api/ai/meal-analyze/`;

  // 실제 파일 업로드
  const formData = {
    image: http.file(bin, 'sample.jpg', 'image/jpeg'),
    meal_time: 'breakfast',
  };

  const res = http.post(url, formData, {
    headers: {
      Authorization: `Bearer ${TOKEN}`,
    },
  });

  console.log("===== REQUEST DEBUG =====");
  console.log("URL:", url);
  console.log("STATUS:", res.status);
  console.log("BODY:", String(res.body).slice(0, 400));
  console.log("==========================");

  sleep(1);
}
