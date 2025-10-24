// static/js/common/ui.auth.js
(function () {
  const $modal = document.getElementById("auth-modal");
  const $form = document.getElementById("auth-modal-form");
  const $err = document.getElementById("auth-modal-error");
  const $cancel = document.getElementById("auth-modal-cancel");

  function openAuthModal(next) {
    try { $form.elements.next.value = next || location.pathname + location.search; } catch {}
    $err.textContent = "";
    $modal.classList.remove("hidden");
    $form.elements.username?.focus();
    document.documentElement.style.overflow = "hidden";
  }
  function closeAuthModal() {
    $modal.classList.add("hidden");
    document.documentElement.style.overflow = "";
  }

  // 로그인 시도
  async function submitLogin(e) {
    e.preventDefault();
    $err.textContent = "";
    const username = $form.elements.username.value.trim();
    const password = $form.elements.password.value;
    const next = $form.elements.next.value || "/";

    if (!username || !password) {
      $err.textContent = "아이디/비밀번호를 입력하세요.";
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
        $err.textContent = "로그인 실패. 아이디/비밀번호를 확인해 주세요.";
        return;
      }
      const data = await res.json();

      // 2) 저장 + 타이머 스케줄(우리 api.js의 helper 이용)
      window.api?.loginSuccess?.({ access: data.access, refresh: data.refresh });

      // 3) 원래 위치로 복귀
      closeAuthModal();
      location.href = next;
    } catch (err) {
      console.error(err);
      $err.textContent = "네트워크 오류가 발생했습니다.";
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
})();
