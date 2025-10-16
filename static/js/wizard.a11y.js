// static/js/wizard.a11y.js
(function () {
  const $ = (s, p=document) => p.querySelector(s);
  function announce(msg) {
    const live = $("#wizard-aria-live");
    if (!live) return;
    live.textContent = "";
    // 텍스트 교체로 라이브리전 트리거
    setTimeout(() => { live.textContent = msg; }, 10);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const wiz = $("#planWizard");
    if (!wiz) return;

    wiz.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-next],[data-prev],[data-submit],[data-close]");
      if (!btn) return;

      if (btn.hasAttribute("data-next")) announce("다음 단계로 이동합니다.");
      if (btn.hasAttribute("data-prev")) announce("이전 단계로 이동합니다.");
      if (btn.hasAttribute("data-submit")) announce("플랜을 생성 중입니다.");
      if (btn.hasAttribute("data-close")) announce("위자드를 닫았습니다.");
    });

    // 외부 바인더가 성공 이벤트를 쏘면 읽어주기
    document.addEventListener("plan:updated", () => announce("플랜이 생성되어 갱신되었습니다."));
    document.addEventListener("wizard:error", (ev) => announce(ev.detail?.message || "오류가 발생했습니다."));
  });
})();
