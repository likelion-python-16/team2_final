import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

export const options = {
  scenarios: {
    load_150_for_5m: {
      executor: 'constant-vus',
      vus: 150,
      duration: '5m',
      gracefulStop: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],   // 실패율 < 1%
    http_req_duration: ['p(95)<500'], // P95 < 500ms
  },
};

const t_all = new Trend('api_healthz_duration');

export default function () {
  const res = http.get('http://nginx/healthz'); // compose 내부 호출
  check(res, { 'status is 200': (r) => r.status === 200 });
  t_all.add(res.timings.duration);
  sleep(1); // VU당 1 rps ≈ 총 ~150 rps
}
