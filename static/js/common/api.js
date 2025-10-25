// static/js/common/api.js
(function () {
  const api = {};
  // CHANGE: 기본 모드를 JWT 사용으로 전환 (로컬/배포 동일 흐름)
  api.useJWT = true;

  // --- 내부 상태 ---
  let refreshingPromise = null;     // refresh 동시호출 방지
  let refreshTimerId = null;        // 만료 전 자동 갱신 타이머
  const AUTH_CH = newSafeBroadcastChannel("auth"); // 탭 간 동기화 채널

  // --- 전역 UX 훅 (토스트/스피너 연결용) ---
  api.onRequestStart = null; // (ctx) => {}
  api.onRequestEnd   = null; // (ctx) => {}
  api.onRequestError = null; // (error, ctx) => {}

  // --- Token / CSRF ---
  function getAccessToken() {
    try { return localStorage.getItem("access") || ""; } catch { return ""; }
  }
  function setAccessToken(t) {
    try {
      if (t) localStorage.setItem("access", t);
      else localStorage.removeItem("access");
      scheduleProactiveRefresh();          // access 변경 시 자동 리스케줄
      broadcastAuth({ type: "access", token: t || "" });
    } catch {}
  }
  function getRefreshToken() {
    try { return localStorage.getItem("refresh") || ""; } catch { return ""; }
  }
  function setRefreshToken(t) {
    try {
      if (t) localStorage.setItem("refresh", t);
      else localStorage.removeItem("refresh");
      broadcastAuth({ type: "refresh", token: t || "" });
    } catch {}
  }
  function getCsrfToken() {
    const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  // same-origin 판단
  function isSameOrigin(url) {
    const u = new URL(url, window.location.href);
    return u.origin === window.location.origin;
  }

  // --- JWT 유틸: exp 디코드 & 남은 시간 ---
  function decodeJWTPayload(token) {
    try {
      const p = token.split(".")[1];
      if (!p) return null;
      // NOTE: atob는 유니코드 처리에 주의. 여기서는 URL-safe 보정만.
      const json = atob(p.replace(/-/g, "+").replace(/_/g, "/"));
      return JSON.parse(json);
    } catch { return null; }
  }
  function getAccessExpiryMs() {
    const t = getAccessToken();
    const payload = t && decodeJWTPayload(t);
    if (!payload?.exp) return null;
    return payload.exp * 1000;
  }
  function msUntilAccessExpiry() {
    const exp = getAccessExpiryMs();
    return exp ? exp - Date.now() : null;
  }

  // --- Headers 빌더 ---
  function buildHeaders(url, body, extra = {}, forceJson = false, useJWT = api.useJWT) {
    const h = { Accept: "application/json", ...extra };

    // Body 타입에 따라 Content-Type 결정
    const isFormData = (typeof FormData !== "undefined") && (body instanceof FormData);
    if (!isFormData && (forceJson || typeof body === "object" || typeof body === "string")) {
      h["Content-Type"] = h["Content-Type"] || "application/json";
    }

    // JWT는 옵션으로만 부착
    if (useJWT) {
      const token = getAccessToken();
      if (token) h["Authorization"] = `Bearer ${token}`;
    }

    // same-origin이면 CSRF 자동 부착 (변경 메서드에서 의미)
    if (isSameOrigin(url)) {
      h["X-CSRFToken"] = getCsrfToken();
    }
    return h;
  }

  // --- 인증 실패 공통 처리 훅 & 로그아웃/리다이렉트 ---
  api.onAuthFail = null; // 필요 시 페이지 단에서 가로채기 가능

  function logoutAndRedirect(nextUrl) {
    try {
      clearRefreshTimer();
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
    } catch {}
    broadcastAuth({ type: "logout" });

    const next = nextUrl || (location.pathname + location.search);
    if (typeof api.onAuthFail === "function") {
      const handled = !!api.onAuthFail({ next });
      if (handled) return; // 커스텀 처리 시 내부 리다이렉트 생략
    }
    location.href = `/login/?next=${encodeURIComponent(next)}`;
  }

  // --- 로그인/로그아웃 헬퍼 (페이지에서 직접 호출 가능) ---
  // CHANGE: 표준 로그인 헬퍼 추가 (/auth/token/ 사용)
  api.login = async function (username, password) {
    const res = await fetch("/auth/token/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
      credentials: "same-origin",
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new ApiError("Login failed", res.status, safeJson(txt));
    }
    const data = await res.json();
    api.loginSuccess({ access: data.access, refresh: data.refresh });
    return data;
  };

  api.loginSuccess = function ({ access, refresh }) {
    if (access) setAccessToken(access);
    if (refresh) setRefreshToken(refresh);
    broadcastAuth({ type: "login" });
  };
  api.logout = function () {
    logoutAndRedirect();
  };

  // --- refresh 토큰: 동시호출 방지용 공유 프라미스 ---
  async function refreshAccessTokenOnce() {
    if (refreshingPromise) return refreshingPromise; // 이미 진행 중이면 공유

    const refresh = getRefreshToken();
    if (!refresh) return null;

    refreshingPromise = (async () => {
      try {
        const res = await fetch("/auth/token/refresh/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh }),
          credentials: "same-origin",
        });
        if (!res.ok) return null;
        const data = await res.json();
        const newAccess = data?.access || "";
        if (newAccess) {
          setAccessToken(newAccess);
          // (옵션) 서버가 refresh도 함께 갱신해서 내려줄 때를 대비
          if (data.refresh) setRefreshToken(data.refresh);
          broadcastAuth({ type: "refreshed" });
        }
        return newAccess || null;
      } catch {
        return null;
      } finally {
        refreshingPromise = null;
      }
    })();

    return refreshingPromise;
  }

  // --- 만료 전 자동 갱신 (프로액티브) ---
  function clearRefreshTimer() {
    if (refreshTimerId) {
      clearTimeout(refreshTimerId);
      refreshTimerId = null;
    }
  }
  async function scheduleProactiveRefresh() {
    clearRefreshTimer();

    // access 없으면 스킵
    const token = getAccessToken();
    if (!token) return;

    const untilMs = msUntilAccessExpiry();
    if (untilMs == null) return;

    // 만료 60초 전(최소 5초, 최대 30분 전)으로 스케줄
    const lead = 60_000;
    const delay = Math.max(5_000, Math.min(untilMs - lead, 30 * 60_000));
    if (!isFinite(delay) || delay <= 0) {
      // 이미 임박/만료 → 즉시 갱신 시도 (실패 시 401 흐름으로 처리)
      try { await refreshAccessTokenOnce(); } catch {}
      return;
    }

    refreshTimerId = setTimeout(async () => {
      await refreshAccessTokenOnce();
    }, delay);
  }

  // --- 페이지/탭 상태 이벤트: 깨어나면 토큰 확인 ---
  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState === "visible") {
      const until = msUntilAccessExpiry();
      if (until != null && until < 90_000) { // 1.5분 이내면 선제 갱신
        await refreshAccessTokenOnce();
      }
      scheduleProactiveRefresh();
    }
  });
  window.addEventListener("focus", async () => {
    const until = msUntilAccessExpiry();
    if (until != null && until < 90_000) {
      await refreshAccessTokenOnce();
    }
    scheduleProactiveRefresh();
  });

  // --- 탭 간 동기화 (BroadcastChannel + storage 이벤트 폴백) ---
  function newSafeBroadcastChannel(name) {
    try { return new BroadcastChannel(name); } catch { return { postMessage() {}, addEventListener() {}, close() {} }; }
  }
  function broadcastAuth(payload) {
    try { AUTH_CH.postMessage(payload); } catch {}
  }
  AUTH_CH.addEventListener?.("message", (e) => {
    const msg = e?.data || {};
    if (msg.type === "logout") {
      clearRefreshTimer();
    } else if (msg.type === "access") {
      // 다른 탭에서 access 갱신됨 → 내 탭도 타이머 리스케줄
      scheduleProactiveRefresh();
    }
  });
  window.addEventListener("storage", (ev) => {
    if (ev.key === "access" || ev.key === "refresh") {
      scheduleProactiveRefresh();
    }
  });

  // --- Fetch with retry (+ 401 자동 갱신 & 실패 시 로그아웃) ---
  async function fetchJson(url, opts = {}, retry = { attempts: 2, delayMs: 400 }) {
    const method = (opts.method || "GET").toUpperCase();

    // body 직렬화: FormData면 그대로, 문자열은 그대로, 객체면 JSON
    let body = opts.body;
    let finalBody = body;
    let forceJson = false;
    if (typeof FormData !== "undefined" && body instanceof FormData) {
      finalBody = body;
    } else if (typeof body === "string") {
      finalBody = body;
    } else if (body != null) {
      finalBody = JSON.stringify(body);
      forceJson = true;
    }

    // headers는 매 요청마다 재생성(갱신된 access 반영)
    const mkOptions = () => ({
      method,
      headers: buildHeaders(url, body, opts.headers || {}, forceJson, opts.useJWT),
      body: ["GET", "HEAD"].includes(method) ? undefined : finalBody,
      credentials: opts.credentials || "same-origin", // 세션 쿠키 포함
      signal: opts.signal,
    });

    // 첫 시도 시작 시점에만 onRequestStart 호출
    const ctx = { url, method, useJWT: (opts.useJWT ?? api.useJWT) };
    if (typeof api.onRequestStart === "function") { try { api.onRequestStart(ctx); } catch {} }

    let lastErr;
    for (let i = 0; i <= (retry?.attempts ?? 0); i++) {
      try {
        let res = await fetch(url, mkOptions());
        if (res.status === 204) {
          if (typeof api.onRequestEnd === "function") { try { api.onRequestEnd(ctx); } catch {} }
          return null;
        }

        // 401 처리: JWT 모드에서만, 아직 리프레시 재시도 안 했으면 1회 시도
        if (res.status === 401 && (opts.useJWT ?? api.useJWT) && !opts.__didRefresh) {
          const newToken = await refreshAccessTokenOnce();
          if (newToken) {
            res = await fetch(url, mkOptions());
            if (res.status === 204) {
              if (typeof api.onRequestEnd === "function") { try { api.onRequestEnd(ctx); } catch {} }
              return null;
            }
          } else {
            // refresh 실패 → 토큰 정리 & 로그인 페이지로
            logoutAndRedirect();
          }
          opts.__didRefresh = true; // 무한 루프 방지
        }

        // 재시도 대상 상태 코드
        if ([429, 502, 503, 504].includes(res.status) && i < (retry?.attempts ?? 0)) {
          await sleep((retry.delayMs ?? 400) * Math.pow(2, i));
          continue;
        }

        const text = await res.text();
        const data = text ? safeJson(text) : null;
        if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status, data);

        if (typeof api.onRequestEnd === "function") { try { api.onRequestEnd(ctx); } catch {} }
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

    // 최종 실패 시 훅 알림 후 throw
    if (typeof api.onRequestError === "function") {
      try { api.onRequestError(lastErr instanceof Error ? lastErr : new Error(String(lastErr)), ctx); } catch {}
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

  // 파일 업로드 (FormData, Content-Type 자동 생략)
  api.upload = (url, formData, opts={}) =>
    fetchJson(url, { ...opts, method: (opts.method || "POST"), body: formData });

  // 선택: 로그인 상태 확인 헬퍼(간단)
  api.isAuthenticated = () => !!(localStorage.getItem("access") && localStorage.getItem("refresh"));

  // 외부 노출
  api.buildHeaders = buildHeaders;
  api.fetchJson = fetchJson;
  api.ApiError = ApiError;

  // --- Error Normalizer (DRF/Validation/Generic) ---
  function parseErrorObject(err) {
    const out = { status: 0, code: "", message: "", fields: {} };
    if (!err) return out;

    if (err instanceof api.ApiError) {
      out.status = err.status || 0;

      if (typeof err.payload === "string") {
        out.message = String(err.payload);
        return out;
      }

      const p = err.payload || {};
      if (p.detail) {
        if (typeof p.detail === "string") {
          out.message = p.detail;
        } else if (p.detail.message) {
          out.message = p.detail.message;
          out.code = p.detail.code || "";
        }
      }

      const src = p.errors || p;
      for (const k of Object.keys(src || {})) {
        if (k === "detail") continue;
        const v = src[k];
        if (Array.isArray(v)) {
          out.fields[k] = v.map(String);
        } else if (typeof v === "string") {
          out.fields[k] = [v];
        }
      }

      if (!out.message) {
        if (out.fields.non_field_errors?.length) out.message = out.fields.non_field_errors[0];
        else {
          const firstField = Object.keys(out.fields)[0];
          if (firstField) out.message = out.fields[firstField][0];
        }
      }
    } else if (err instanceof Error) {
      out.message = err.message || "요청 처리 중 오류가 발생했습니다.";
    } else {
      out.message = "요청 처리 중 오류가 발생했습니다.";
    }
    return out;
  }

  function toUserMessage(err) {
    const e = parseErrorObject(err);
    const s = e.status || 0;
    const base = (t) => t || "요청 처리 중 문제가 발생했습니다.";

    if (s === 0) return base("네트워크 오류가 발생했습니다. 연결을 확인해 주세요.");
    if (s === 400) return base(e.message || "잘못된 요청입니다. 입력값을 확인해 주세요.");
    if (s === 401) return "로그인이 필요합니다.";
    if (s === 403) return "권한이 없습니다.";
    if (s === 404) return "요청하신 자원을 찾을 수 없습니다.";
    if (s === 409) return base(e.message || "충돌이 발생했습니다. 이미 존재하는 데이터일 수 있어요.");
    if (s === 413) return "업로드 용량 제한을 초과했습니다.";
    if (s === 422) return base(e.message || "검증에 실패했습니다. 입력값을 확인해 주세요.");
    if (s === 429) return "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.";
    if (s >= 500) return "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";

    if (e.message) return e.message;
    return base();
  }

  // 외부 노출 (ui.toast.js에서 사용)
  api.parseError = parseErrorObject;
  api.toUserMessage = toUserMessage;

  // CHANGE: authFetch 헬퍼 제공 (항상 JWT 사용하도록 강제)
  api.authFetch = (url, opts = {}) => fetchJson(url, { ...opts, useJWT: true });

  // 초기 스케줄 (페이지 로드 시 1회)
  scheduleProactiveRefresh();

  // 전역 노출
  window.api = api;
})();
