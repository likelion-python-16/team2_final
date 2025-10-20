// static/js/common/api.js
(function () {
  const api = {};
  api.useJWT = false; // 기본은 세션 우선. 필요 시 true로 전환해서 Bearer 사용.

  // --- Token / CSRF ---
  function getAccessToken() {
    try { return localStorage.getItem("access") || ""; } catch { return ""; }
  }
  function getCsrfToken() {
    const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  // 요청 URL 기준 same-origin 판단
  function isSameOrigin(url) {
    const u = new URL(url, window.location.href);
    return u.origin === window.location.origin;
  }

  // --- Headers 빌더 ---
  function buildHeaders(url, body, extra = {}, forceJson = false, useJWT = api.useJWT) {
    const h = { Accept: "application/json", ...extra };

    // Body 타입에 따라 Content-Type 결정
    const isFormData = (typeof FormData !== "undefined") && (body instanceof FormData);
    if (!isFormData && (forceJson || typeof body === "object" || typeof body === "string")) {
      h["Content-Type"] = h["Content-Type"] || "application/json";
    }
    // JWT는 옵션으로만 붙임
    if (useJWT) {
      const token = getAccessToken();
      if (token) h["Authorization"] = `Bearer ${token}`;
    }
    // same-origin이면 CSRF 자동 부착 (POST/PUT/PATCH/DELETE에서만 의미)
    if (isSameOrigin(url)) {
      h["X-CSRFToken"] = getCsrfToken();
    }
    return h;
  }

  // --- Fetch with retry ---
  async function fetchJson(url, opts = {}, retry = { attempts: 2, delayMs: 400 }) {
    const method = (opts.method || "GET").toUpperCase();

    // body 직렬화: FormData면 그대로, 문자열은 그대로, 객체면 JSON
    let body = opts.body;
    let finalBody = body;
    let forceJson = false;
    if (typeof FormData !== "undefined" && body instanceof FormData) {
      finalBody = body; // 그대로
    } else if (typeof body === "string") {
      finalBody = body;
    } else if (body != null) {
      finalBody = JSON.stringify(body);
      forceJson = true;
    }

    const options = {
      method,
      headers: buildHeaders(url, body, opts.headers || {}, forceJson, opts.useJWT),
      body: ["GET", "HEAD"].includes(method) ? undefined : finalBody,
      credentials: opts.credentials || "same-origin", // 세션 쿠키 포함
      signal: opts.signal,
    };

    let lastErr;
    for (let i = 0; i <= (retry?.attempts ?? 0); i++) {
      try {
        const res = await fetch(url, options);
        if (res.status === 204) return null;

        // 재시도 대상
        if ([429, 502, 503, 504].includes(res.status) && i < retry.attempts) {
          await sleep((retry.delayMs ?? 400) * Math.pow(2, i));
          continue;
        }

        const text = await res.text();
        const data = text ? safeJson(text) : null;
        if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status, data);
        return data;
      } catch (err) {
        lastErr = err;
        const transient = err instanceof TypeError || err.name === "AbortError";
        if (transient && i < (retry?.attempts ?? 0)) {
          await sleep((retry?.delayMs ?? 400) * Math.pow(2, i));
          continue;
        }
        break;
      }
    }
    throw lastErr;
  }

  function safeJson(t) { try { return JSON.parse(t); } catch { return { raw: t }; } }
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
  api.get   = (url, opts={})       => fetchJson(url, { ...opts, method: "GET" });
  api.post  = (url, body, opts={}) => fetchJson(url, { ...opts, method: "POST", body });
  api.patch = (url, body, opts={}) => fetchJson(url, { ...opts, method: "PATCH", body });
  api.del   = (url, opts={})       => fetchJson(url, { ...opts, method: "DELETE" });

  // 파일 업로드 전용 (FormData, Content-Type 자동 생략)
  api.upload = (url, formData, opts={}) =>
    fetchJson(url, { ...opts, method: (opts.method || "POST"), body: formData });

  // 외부 노출
  api.buildHeaders = buildHeaders;
  api.fetchJson = fetchJson;
  api.ApiError = ApiError;

  window.api = api;
})();
