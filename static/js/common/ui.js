// static/js/common/ui.js
// 공통 UI 유틸: 로딩 오버레이, 토스트, 권한 안내 배너 (추가만; 전역 window.ui 노출)

(function () {
  if (window.ui) return; // 중복 방지

  // ---- Root 생성 (최초 1회) ----
  function ensureRoot() {
    let root = document.getElementById("ui-root");
    if (root) return root;
    root = document.createElement("div");
    root.id = "ui-root";
    root.setAttribute("aria-live", "polite");
    root.style.position = "fixed";
    root.style.inset = "0";
    root.style.pointerEvents = "none"; // 기본적으로 클릭 막지 않음
    root.style.zIndex = "9999";
    document.body.appendChild(root);
    return root;
  }

  // ---- 로딩 오버레이 ----
  let loadingCount = 0;
  let overlayEl = null;
  function showLoading(text = "Loading...") {
    loadingCount++;
    const root = ensureRoot();
    if (!overlayEl) {
      overlayEl = document.createElement("div");
      overlayEl.style.position = "fixed";
      overlayEl.style.inset = "0";
      overlayEl.style.background = "rgba(15,15,20,0.35)";
      overlayEl.style.backdropFilter = "blur(2px)";
      overlayEl.style.display = "flex";
      overlayEl.style.alignItems = "center";
      overlayEl.style.justifyContent = "center";
      overlayEl.style.pointerEvents = "auto"; // 로딩 중 클릭 차단
      const box = document.createElement("div");
      box.style.minWidth = "180px";
      box.style.maxWidth = "80vw";
      box.style.padding = "16px 18px";
      box.style.borderRadius = "14px";
      box.style.boxShadow = "0 8px 30px rgba(0,0,0,0.25)";
      box.style.background = "white";
      box.style.font = "500 14px/1.45 Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
      box.style.display = "flex";
      box.style.alignItems = "center";
      box.style.gap = "10px";

      const spinner = document.createElement("div");
      spinner.style.width = "18px";
      spinner.style.height = "18px";
      spinner.style.border = "3px solid #e5e7eb";
      spinner.style.borderTopColor = "#6b7280";
      spinner.style.borderRadius = "999px";
      spinner.style.animation = "ui-spin 0.9s linear infinite";

      const label = document.createElement("span");
      label.textContent = text;

      box.appendChild(spinner);
      box.appendChild(label);
      overlayEl.appendChild(box);
      root.appendChild(overlayEl);

      // 간단한 keyframes 주입 (1회)
      injectKeyframesOnce();
    } else {
      overlayEl.querySelector("span")?.replaceWith(Object.assign(document.createElement("span"), { textContent: text }));
    }
    overlayEl.style.opacity = "1";
  }
  function hideLoading() {
    loadingCount = Math.max(0, loadingCount - 1);
    if (loadingCount === 0 && overlayEl) {
      overlayEl.style.opacity = "0";
      // 살짝 지연 후 제거해도 되지만, 오버레이는 재사용하므로 유지
    }
  }

  // ---- 토스트 ----
  let toastHost = null;
  function ensureToastHost() {
    if (toastHost) return toastHost;
    const root = ensureRoot();
    toastHost = document.createElement("div");
    toastHost.style.position = "fixed";
    toastHost.style.bottom = "18px";
    toastHost.style.left = "50%";
    toastHost.style.transform = "translateX(-50%)";
    toastHost.style.display = "flex";
    toastHost.style.flexDirection = "column";
    toastHost.style.gap = "8px";
    toastHost.style.pointerEvents = "none";
    root.appendChild(toastHost);
    return toastHost;
  }

  function toast(message, type = "info", ms = 2500) {
    const host = ensureToastHost();
    const el = document.createElement("div");
    el.style.pointerEvents = "auto";
    el.style.padding = "12px 14px";
    el.style.borderRadius = "12px";
    el.style.font = "500 14px/1.45 Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
    el.style.boxShadow = "0 8px 30px rgba(0,0,0,0.18)";
    el.style.background = (type === "error") ? "#fee2e2" : (type === "success") ? "#dcfce7" : "#e5f0ff";
    el.style.border = "1px solid rgba(0,0,0,0.06)";
    el.textContent = message;

    // 진입 애니메이션
    el.style.opacity = "0";
    el.style.transform = "translateY(8px)";
    requestAnimationFrame(() => {
      el.style.transition = "opacity .18s ease, transform .18s ease";
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    });

    host.appendChild(el);

    // 자동 제거
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(8px)";
      setTimeout(() => el.remove(), 200);
    }, ms);
  }
  function toastError(msg, ms)   { toast(msg, "error",   ms); }
  function toastSuccess(msg, ms) { toast(msg, "success", ms); }
  function toastInfo(msg, ms)    { toast(msg, "info",    ms); }

  // ---- 권한 안내 배너 ----
  // container: 엘리먼트 또는 셀렉터(문자열). 제공 안하면 body 최상단에 삽입.
  function injectAuthBanner(container, opts = {}) {
    const target = (typeof container === "string")
      ? document.querySelector(container)
      : (container || document.body);

    // 중복 방지
    if (document.getElementById("auth-banner")) return;

    const wrap = document.createElement("div");
    wrap.id = "auth-banner";
    wrap.role = "alert";
    wrap.style.display = "flex";
    wrap.style.alignItems = "center";
    wrap.style.gap = "10px";
    wrap.style.padding = "10px 12px";
    wrap.style.background = "#fff7ed";
    wrap.style.border = "1px solid #fed7aa";
    wrap.style.color = "#7c2d12";
    wrap.style.font = "500 14px/1.4 Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
    wrap.style.borderRadius = "10px";
    wrap.style.margin = "10px 12px";

    const msg = document.createElement("span");
    msg.textContent = opts.text || "로그인이 필요합니다. 로그인 후 다시 시도해주세요.";

    const btn = document.createElement("a");
    btn.href = opts.loginUrl || "/users/login/";
    btn.textContent = "로그인하기";
    btn.style.padding = "6px 10px";
    btn.style.background = "#fdba74";
    btn.style.borderRadius = "8px";
    btn.style.color = "#111827";
    btn.style.textDecoration = "none";
    btn.style.fontWeight = "600";

    wrap.appendChild(msg);
    wrap.appendChild(btn);

    // 기본은 body 맨 위
    if (target === document.body) {
      document.body.insertBefore(wrap, document.body.firstChild);
    } else {
      target.prepend(wrap);
    }
  }

  // ApiError(401/403)일 때 배너 자동 삽입 헬퍼
  function handleAuthError(err, container, loginUrl) {
    if (!err) return false;
    const status = err.status || err?.payload?.status;
    if (status === 401 || status === 403) {
      injectAuthBanner(container, { loginUrl });
      return true;
    }
    return false;
  }

  // ---- keyframes 1회 주입 (spinner용) ----
  let keyframed = false;
  function injectKeyframesOnce() {
    if (keyframed) return;
    keyframed = true;
    const style = document.createElement("style");
    style.textContent = `
    @keyframes ui-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    `;
    document.head.appendChild(style);
  }

  // ---- 외부 노출 ----
  window.ui = {
    showLoading, hideLoading,
    toast, toastError, toastSuccess, toastInfo,
    injectAuthBanner, handleAuthError
  };
})();
