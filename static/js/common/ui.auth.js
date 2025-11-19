// static/js/common/ui.auth.js
(function () {
  const $modal = document.getElementById("auth-modal");
  const $form = document.getElementById("auth-modal-form");
  const $err = document.getElementById("auth-modal-error");
  const $cancel = document.getElementById("auth-modal-cancel");

  function openAuthModal(next) {
    try {
      $form.elements.next.value = next || location.pathname + location.search;
    } catch {}
    if ($err) $err.textContent = "";
    if ($modal) $modal.classList.remove("hidden");
    try {
      $form.elements.username?.focus();
    } catch {}
    document.documentElement.style.overflow = "hidden";
  }

  function closeAuthModal() {
    if ($modal) $modal.classList.add("hidden");
    document.documentElement.style.overflow = "";
  }

  // 로그인 시도 (일반 아이디/비밀번호)
  async function submitLogin(e) {
    e.preventDefault();
    if ($err) $err.textContent = "";

    const username = $form.elements.username.value.trim();
    const password = $form.elements.password.value;
    const next = $form.elements.next.value || "/";

    if (!username || !password) {
      if ($err) $err.textContent = "아이디/비밀번호를 입력하세요.";
      return;
    }

    try {
      // 1) 토큰 발급
      const res = await fetch("/auth/token/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
        credentials: "same-origin",
      });

      if (!res.ok) {
        if ($err) $err.textContent = "로그인 실패. 아이디/비밀번호를 확인해 주세요.";
        return;
      }

      const data = await res.json();

      // 2) 저장 + 타이머 스케줄(our api.js helper)
      window.api?.loginSuccess?.({ access: data.access, refresh: data.refresh });

      // 3) 원래 위치로 복귀
      closeAuthModal();
      location.href = next;
    } catch (err) {
      console.error(err);
      if ($err) $err.textContent = "네트워크 오류가 발생했습니다.";
    }
  }

  $form?.addEventListener("submit", submitLogin);
  $cancel?.addEventListener("click", closeAuthModal);

  // Step 20에서 등록한 훅 사용: true 반환 시 내부 리다이렉트 방지
  if (window.api) {
    window.api.onAuthFail = ({ next }) => {
      openAuthModal(next);
      return true; // 모달로 처리했으므로 기본 리다이렉트 막기
    };
  }

  // 전역 노출(필요하면 수동 열기)
  window.AuthModal = { open: openAuthModal, close: closeAuthModal };

  // ============================
  // 🔍 시연용: 소셜 로그인 디버깅
  // ============================
  function logOAuthStart(provider, href) {
    console.log(`🔥 [${provider}] 소셜 로그인 시작`);
    console.log("➡️ redirect URL:", href);

    try {
      const u = new URL(href, window.location.origin);
      const p = u.searchParams;
      console.log("  response_type:", p.get("response_type"));
      console.log("  client_id:", p.get("client_id"));
      console.log("  redirect_uri:", p.get("redirect_uri"));
      console.log("  state:", p.get("state"));
    } catch (e) {
      console.warn("  URL 파싱 실패:", e);
    }

    console.log("---------------------------");
  }

  function attachOAuthDebug() {
    // 템플릿에서:
    // <a href="{% url 'users:kakao_login' %}" data-oauth="kakao">...</a>
    // <a href="{% url 'users:naver_login' %}" data-oauth="naver">...</a>
    const kakao = document.querySelector('[data-oauth="kakao"]');
    const naver = document.querySelector('[data-oauth="naver"]');

    if (kakao) {
      kakao.addEventListener("click", () => {
        const href = kakao.getAttribute("href") || "";
        logOAuthStart("KAKAO", href);
      });
    }

    if (naver) {
      naver.addEventListener("click", () => {
        const href = naver.getAttribute("href") || "";
        logOAuthStart("NAVER", href);
      });
    }
  }

  // DOM 로드 상태에 따라 디버그 이벤트 바인딩
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachOAuthDebug);
  } else {
    attachOAuthDebug();
  }
})();
