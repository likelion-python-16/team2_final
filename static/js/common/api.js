// static/js/common/api.js
(function () {
  // ================================
  // API 객체
  // ================================
  const api = {};
  api.useJWT = true;

  // 내부 상태
  let refreshingPromise = null;
  let refreshTimerId = null;
  let refreshScheduled = false; // ✅ 추가: 스케줄 플래그
  const AUTH_CH = newSafeBroadcastChannel("auth");

  // UX hook
  api.onRequestStart = null;
  api.onRequestEnd = null;
  api.onRequestError = null;

  // ================================
  // Token Storage
  // ================================
  function getAccessToken() {
    try { return localStorage.getItem("access") || ""; } catch { return ""; }
  }
  function getRefreshToken() {
    try { return localStorage.getItem("refresh") || ""; } catch { return ""; }
  }

  function setAccessToken(t) {
    try {
      if (t) localStorage.setItem("access", t);
      else localStorage.removeItem("access");

      scheduleProactiveRefresh();
      broadcastAuth({ type: "access", token: t || "" });
    } catch {}
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

  function isSameOrigin(url) {
    const u = new URL(url, window.location.href);
    return u.origin === window.location.origin;
  }

  // ================================
  // JWT decode
  // ================================
  function decodeJWTPayload(token) {
    try {
      const p = token.split(".")[1];
      if (!p) return null;
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

  // ================================
  // Header builder
  // ================================
  function buildHeaders(url, body, extra = {}, forceJson = false, useJWT = api.useJWT) {
    const h = { Accept: "application/json", ...extra };

    const isFormData = body instanceof FormData;
    if (!isFormData && (forceJson || typeof body === "object" || typeof body === "string")) {
      h["Content-Type"] = "application/json";
    }

    if (useJWT) {
      const token = getAccessToken();
      if (token) h["Authorization"] = `Bearer ${token}`;
    }

    if (isSameOrigin(url)) h["X-CSRFToken"] = getCsrfToken();
    return h;
  }

  // ================================
  // Authentication
  // ================================
  api.onAuthFail = null;

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
      if (handled) return;
    }
    location.href = `/login/?next=${encodeURIComponent(next)}`;
  }

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

  api.logout = () => logoutAndRedirect();

  // ================================
  // Refresh Token
  // ================================
  async function refreshAccessTokenOnce() {
    if (refreshingPromise) return refreshingPromise;

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
        const newRefresh = data?.refresh || "";

        if (!newAccess) {
          console.warn("[refreshAccessTokenOnce] refresh returned no access");
          return null;
        }

        setAccessToken(newAccess);
        if (newRefresh) setRefreshToken(newRefresh);

        broadcastAuth({ type: "refreshed" });
        return newAccess;

      } catch (err) {
        console.error("[refreshAccessTokenOnce] error:", err);
        return null;

      } finally {
        refreshingPromise = null;
      }
    })();

    return refreshingPromise;
  }

  // ================================
  // Proactive Refresh (개선판)
  // ================================
  function clearRefreshTimer() {
    if (refreshTimerId) {
      clearTimeout(refreshTimerId);
      refreshTimerId = null;
    }
    refreshScheduled = false; // ✅ 플래그 초기화
  }

  async function scheduleProactiveRefresh() {
    // ✅ 이미 스케줄되어 있으면 스킵
    if (refreshScheduled) return;

    clearRefreshTimer();

    const token = getAccessToken();
    if (!token) return;

    const until = msUntilAccessExpiry();
    if (until == null) return;

    // 60초 전 갱신 (최소 5초, 최대 30분)
    const lead = 60000;
    const delay = Math.max(5000, Math.min(until - lead, 30 * 60000));

    if (!isFinite(delay) || delay <= 0) {
      await refreshAccessTokenOnce();
      return;
    }

    refreshScheduled = true; // ✅ 플래그 설정
    refreshTimerId = setTimeout(() => {
      refreshScheduled = false;
      refreshAccessTokenOnce();
    }, delay);
  }

  // ✅ visibilitychange: 디바운싱 추가
  let visibilityTimer = null;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;

    clearTimeout(visibilityTimer);
    visibilityTimer = setTimeout(() => {
      scheduleProactiveRefresh();
    }, 300);
  });

  // ✅ focus: 디바운싱 추가
  let focusTimer = null;
  window.addEventListener("focus", () => {
    clearTimeout(focusTimer);
    focusTimer = setTimeout(() => {
      scheduleProactiveRefresh();
    }, 300);
  });

  // ================================
  // BroadcastChannel Sync
  // ================================
  function newSafeBroadcastChannel(name) {
    try { return new BroadcastChannel(name); }
    catch { return { postMessage() {}, addEventListener() {}, close() {} }; }
  }

  function broadcastAuth(payload) {
    try { AUTH_CH.postMessage(payload); } catch {}
  }

  // ✅ BroadcastChannel: 디바운싱 추가
  let authMessageTimer = null;
  AUTH_CH.addEventListener?.("message", ({ data }) => {
    if (!data) return;

    if (data.type === "logout") {
      clearRefreshTimer();
    }

    if (data.type === "access") {
      clearTimeout(authMessageTimer);
      authMessageTimer = setTimeout(() => {
        scheduleProactiveRefresh();
      }, 300);
    }
  });

  // ✅ storage 이벤트: 디바운싱 추가
  let storageTimer = null;
  window.addEventListener("storage", (ev) => {
    if (ev.key !== "access" && ev.key !== "refresh") return;

    clearTimeout(storageTimer);
    storageTimer = setTimeout(() => {
      scheduleProactiveRefresh();
    }, 300);
  });

  // ================================
  // fetchJson — 자동 refresh + retry
  // ================================
  async function fetchJson(url, opts = {}, retry = { attempts: 2, delayMs: 400 }) {
    const method = (opts.method || "GET").toUpperCase();
    const body = opts.body;

    let finalBody = body;
    let forceJson = false;

    if (body instanceof FormData) {
      finalBody = body;
    } else if (typeof body === "string") {
      finalBody = body;
    } else if (body != null) {
      finalBody = JSON.stringify(body);
      forceJson = true;
    }

    const mkOptions = () => ({
      method,
      headers: buildHeaders(url, body, opts.headers || {}, forceJson, opts.useJWT),
      body: ["GET", "HEAD"].includes(method) ? undefined : finalBody,
      credentials: opts.credentials || "same-origin",
      signal: opts.signal,
    });

    const ctx = { url, method, useJWT: (opts.useJWT ?? api.useJWT) };
    if (api.onRequestStart) api.onRequestStart(ctx);

    let lastErr = null;

    for (let i = 0; i <= (retry.attempts ?? 0); i++) {
      try {
        let res = await fetch(url, mkOptions());

        if (res.status === 204) {
          api.onRequestEnd?.(ctx);
          return null;
        }

        // 401 처리
        if (res.status === 401 && (opts.useJWT ?? api.useJWT) && !opts.__didRefresh) {
          const newToken = await refreshAccessTokenOnce();
          if (newToken) {
            opts.__didRefresh = true;
            res = await fetch(url, mkOptions());
          } else {
            logoutAndRedirect();
            throw new Error("Unauthorized");
          }
        }

        // 재시도 대상 상태코드
        if ([429, 502, 503, 504].includes(res.status) && i < retry.attempts) {
          await sleep(retry.delayMs * Math.pow(2, i));
          continue;
        }

        const text = await res.text();
        const data = text ? safeJson(text) : null;

        if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status, data);

        api.onRequestEnd?.(ctx);
        return data;

      } catch (e) {
        lastErr = e;
        const transient = e instanceof TypeError || e.name === "AbortError";

        if (transient && i < retry.attempts) {
          await sleep(retry.delayMs * Math.pow(2, i));
          continue;
        }
        break;
      }
    }

    api.onRequestError?.(lastErr, ctx);
    throw lastErr;
  }

  // ================================
  // Helpers
  // ================================
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

  // 간편 shorthands
  api.get = (url, opts={}) => fetchJson(url, { ...opts, method: "GET" });
  api.post = (url, body, opts={}) => fetchJson(url, { ...opts, method: "POST", body });
  api.patch = (url, body, opts={}) => fetchJson(url, { ...opts, method: "PATCH", body });
  api.del = (url, opts={}) => fetchJson(url, { ...opts, method: "DELETE" });

  api.upload = (url, formData, opts={}) =>
    fetchJson(url, { ...opts, method: (opts.method || "POST"), body: formData });

  api.isAuthenticated = () => !!(getAccessToken() && getRefreshToken());

  api.buildHeaders = buildHeaders;
  api.fetchJson = fetchJson;
  api.ApiError = ApiError;

  // 경량 메시지 생성기
  api.toUserMessage = function (err) {
    if (err instanceof ApiError) {
      const s = err.status;
      const msg = err.payload?.detail || "";
      if (s === 400) return msg || "잘못된 요청입니다.";
      if (s === 401) return "로그인이 필요합니다.";
      if (s === 403) return "권한이 없습니다.";
      if (s === 404) return "데이터를 찾을 수 없습니다.";
      if (s >= 500) return "서버 오류가 발생했습니다.";
      return msg || "요청 오류가 발생했습니다.";
    }
    return err?.message || "요청 처리 중 문제가 발생했습니다.";
  };

  api.authFetch = (url, opts={}) => fetchJson(url, { ...opts, useJWT: true });

  // 초기 스케줄
  scheduleProactiveRefresh();

  window.api = api;
})();
