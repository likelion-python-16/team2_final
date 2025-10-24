// static/js/common/ui.toast.js
(function () {
  const $root = document.getElementById("toast-root");
  const $spin = document.getElementById("spinner-root");
  let inFlight = 0;

  function showToast(msg, type = "ok", ms = 3000) {
    if (!$root) return;
    const el = document.createElement("div");
    el.className = `toast toast--${type}`;
    el.textContent = msg;
    $root.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(6px)";
      setTimeout(() => el.remove(), 300);
    }, ms);
  }

  function showLoading() {
    inFlight++;
    if ($spin) $spin.classList.remove("hidden");
  }
  function hideLoading() {
    inFlight = Math.max(0, inFlight - 1);
    if ($spin && inFlight === 0) $spin.classList.add("hidden");
  }

  // api.js와 연결
  if (window.api) {
    window.api.onRequestStart = (ctx) => showLoading();
    window.api.onRequestEnd   = (ctx) => hideLoading();
    window.api.onRequestError = (err, ctx) => {
      hideLoading();

      // 401은 모달/리다이렉트에 맡김
      const status = err?.status || 0;
      if (status === 401) return;

      // 표준화된 사용자 메시지 생성
      const msg = (typeof window.api.toUserMessage === "function")
        ? window.api.toUserMessage(err)
        : (err?.message || "요청 처리 중 문제가 발생했습니다.");

      // 타입 매핑
      let type = "warn";
      if (status >= 500) type = "error";
      else if (status === 403) type = "warn";
      else if (status === 429) type = "warn";
      else if (status === 0)   type = "error"; // 네트워크

      showToast(msg, type);
    };
  }

  // 전역 노출
  window.Toast = { show: showToast, loading: { show: showLoading, hide: hideLoading } };
})();
