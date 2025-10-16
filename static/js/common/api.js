// static/js/common/api.js
// 추가만 하는 공통 API 유틸. 전역 네임스페이스 오염 최소화를 위해 window.api 아래로 노출.
// Bearer 토큰(localStorage.access)과 CSRF(동일 출처 POST용) 자동 부착 + 재시도 로직 포함.

(function () {
  const api = {};

  // --- Token / CSRF ---
  function getAccessToken() {
    try { return localStorage.getItem("access") || ""; } catch { return ""; }
  }

  function getCsrfToken() {
    // Django 기본 csrftoken 쿠키
    const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  // --- Headers ---
  function authHeaders(extra = {}) {
    const h = { "Content-Type": "application/json", ...extra };
    const token = getAccessToken();
    if (token) h["Authorization"] = `Bearer ${token}`;
    // same-origin인 경우에만 CSRF 붙이기 (안전하게 시도: 붙여도 무해)
    const isSameOrigin =
      location.origin.startsWith("http://127.0.0.1") ||
      location.origin.startsWith("http://localhost") ||
      location.hostname.endsWith(window.location.hostname);
    if (isSameOrigin) h["X-CSRFToken"] = getCsrfToken();
    return h;
  }

  // --- Fetch with retry ---
  async function fetchJson(url, opts = {}, retry = { attempts: 2, delayMs: 400 }) {
    const options = {
      method: opts.method || "GET",
      headers: authHeaders(opts.headers || {}),
      body: opts.body ? (typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body)) : undefined,
      credentials: opts.credentials || "same-origin",
      signal: opts.signal,
    };

    let lastErr;
    for (let i = 0; i <= retry.attempts; i++) {
      try {
        const res = await fetch(url, options);
        if (res.status === 204) return null; // no content
        // 재시도 대상 상태코드
        if ([429, 502, 503, 504].includes(res.status) && i < retry.attempts) {
          await sleep(retry.delayMs * Math.pow(2, i));
          continue;
        }
        // JSON 파싱 시도
        const text = await res.text();
        const data = text ? safeJson(text) : null;
        if (!res.ok) {
          const err = new ApiError(`HTTP ${res.status}`, res.status, data);
          throw err;
        }
        return data;
      } catch (err) {
        lastErr = err;
        // 네트워크/Abort 재시도
        const transient = err instanceof TypeError || err.name === "AbortError";
        if (transient && i < retry.attempts) {
          await sleep(retry.delayMs * Math.pow(2, i));
          continue;
        }
        break;
      }
    }
    throw lastErr;
  }

  function safeJson(t) {
    try { return JSON.parse(t); } catch { return { raw: t }; }
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  class ApiError extends Error {
    constructor(message, status, payload) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.payload = payload;
    }
  }

  // --- Shorthands ---
  api.get  = (url, opts={}) => fetchJson(url, { ...opts, method: "GET" });
  api.post = (url, body, opts={}) => fetchJson(url, { ...opts, method: "POST", body });
  api.patch= (url, body, opts={}) => fetchJson(url, { ...opts, method: "PATCH", body });
  api.del  = (url, opts={}) => fetchJson(url, { ...opts, method: "DELETE" });

  // 외부 노출
  api.authHeaders = authHeaders;
  api.fetchJson = fetchJson;
  api.ApiError = ApiError;

  // 글로벌 등록
  window.api = api;
})();
