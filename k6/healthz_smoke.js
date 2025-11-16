import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 3,            // 동시 3명
  duration: '20s',   // 20초만 돌려보기
};

export default function () {
  const res = http.get('http://team2_nginx/healthz'); // 실제 컨테이너 이름

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
