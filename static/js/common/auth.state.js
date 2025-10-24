// 로그인 상태에 따라 배너/버튼/데이터 재로딩을 제어
(function () {
  const $banner = document.getElementById("auth-banner");
  const $loginBtns = document.querySelectorAll('[data-auth="login"]');
  const $dismiss = document.querySelector('[data-auth="dismiss"]');

  // 페이지별로 “로그인 후 자동 재로딩” 하고 싶은 콜백을 등록할 수 있음
  // 예: window.onAuthRehydrate = () => reloadDashboard();
  function triggerRehydrate() {
    try { typeof window.onAuthRehydrate === "function" && window.onAuthRehydrate(); } catch {}
  }

  function isAuthed() {
    return !!(window.api?.isAuthenticated?.());
  }

  function showBanner() {
    $banner && $banner.classList.remove("hidden");
  }
  function hideBanner() {
    $banner && $banner.classList.add("hidden");
  }

  function updateUI() {
    if (isAuthed()) {
      hideBanner();
    } else {
      showBanner();
    }
  }

  // 이벤트 바인딩
  $dismiss?.addEventListener("click", () => hideBanner());

  // 탭 간/토큰 갱신 시 동기화: api.js가 BroadcastChannel/storage를 이미 사용하므로,
  // 여기서는 주기적으로 상태를 반영하면 충분.
  window.addEventListener("focus", updateUI);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") updateUI();
  });
  window.addEventListener("storage", (ev) => {
    if (ev.key === "access" || ev.key === "refresh") {
      updateUI();
      if (isAuthed()) triggerRehydrate();
    }
  });

  // api.onAuthFail 훅에서 모달 대신 리다이렉트 사용하는 경우에도, 로그인 성공 시 재수화
  if (window.api) {
    const origLoginSuccess = window.api.loginSuccess;
    window.api.loginSuccess = function (tokens) {
      origLoginSuccess?.call(window.api, tokens);
      updateUI();
      triggerRehydrate();
    };
  }

  // 초기 1회 반영
  updateUI();
})();
