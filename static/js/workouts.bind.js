/* static/js/workouts.bind.js
 * Workouts page bindings (C1~C6 + 날짜/주간/± 내비)
 * - 원칙: "추가만" (기존 코드/파일은 수정하지 않음)
 * - 의존(있으면 사용): window.authHeaders, showLoading/hideLoading, toastError, formatYMD, openPlanWizard
 * - HTML 훅: #wk-plan-date, #wk-load-by-date, #wk-ensure-today, #wk-days, #wk-prev-day, #wk-next-day, #wk-current-label,
 *            #wk-plan-date-label, #wk-plan-id, #wk-plan-taskcount, #wk-plan-duration, #wk-tasks-list
 */
(function () {
  "use strict";

  // ========= 공통 =========
  const API_BASE = (typeof window.API === "string" && window.API) ? window.API : "/api";

  // CSRF (템플릿 세션 사용 시 대비)
  function getCookie(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }

  // 🔐 안전한 헤더 래퍼: 프로젝트의 공통 authHeaders()가 있으면 우선 사용
  function authHeaders() {
    if (typeof window.authHeaders === "function") return window.authHeaders();
    const headers = { "Content-Type": "application/json" };
    const csrf = getCookie("csrftoken");
    if (csrf) headers["X-CSRFToken"] = csrf;
    // JWT를 localStorage에 저장하는 패턴일 경우(백엔드가 JWT) Fallback
    const access = localStorage.getItem("access");
    if (access) headers["Authorization"] = `Bearer ${access}`;
    return headers;
  }

  // ========= 날짜 유틸 (KST 기준) =========
  function toKST(d) {
    return new Date(d.toLocaleString("en-US", { timeZone: "Asia/Seoul" }));
  }
  function startOfDayKST(d) {
    const t = toKST(d);
    return new Date(t.getFullYear(), t.getMonth(), t.getDate());
  }
  function addDays(d, n) {
    const x = new Date(d);
    x.setDate(x.getDate() + n);
    return x;
  }
  function fmtISO(d) {
    if (typeof window.formatYMD === "function") return window.formatYMD(d);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${dd}`;
  }
  const DAYS_KO = ["일", "월", "화", "수", "목", "금", "토"];

  // ========= 상태 =========
  const TODAY = startOfDayKST(new Date());
  const RANGE_START = addDays(TODAY, -59); // 최근 60일
  const RANGE_END = TODAY;

  let selectedDate = TODAY;         // 현재 선택 날짜
  let isInitBound = false;          // 이벤트 중복 방지
  let ENSURE_URL = `${API_BASE}/workoutplans/today/ensure/`;

  // ========= DOM 캐시 =========
  const $daysWrap = document.getElementById("wk-days");
  const $dateInput = document.getElementById("wk-plan-date");
  const $loadByDate = document.getElementById("wk-load-by-date");
  const $ensureToday = document.getElementById("wk-ensure-today");
  const $label = document.getElementById("wk-current-label");

  const $planDateLabel = document.getElementById("wk-plan-date-label");
  const $planIdEl = document.getElementById("wk-plan-id");
  const $planCntEl = document.getElementById("wk-plan-taskcount");
  const $planMinEl = document.getElementById("wk-plan-duration");
  const $list = document.getElementById("wk-tasks-list");

  // ========= Week Bar 렌더 =========
  function startOfWeekMon(d) {
    const wd = d.getDay(); // 0=일
    const diff = (wd === 0) ? -6 : (1 - wd); // 월=1
    return addDays(d, diff);
  }

  function renderWeekBar(centerDate) {
    if (!$daysWrap) return;

    const start = startOfWeekMon(centerDate);
    const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));

    const selectedISO = fmtISO(selectedDate);
    $daysWrap.innerHTML = days.map((d) => {
      const isActive = fmtISO(d) === selectedISO;
      const label = `${d.getMonth() + 1}/${d.getDate()}`;
      const day = DAYS_KO[d.getDay()];
      return `
        <button type="button" class="wk-day ${isActive ? "is-active" : ""}" data-date="${fmtISO(d)}" aria-pressed="${isActive}">
          <span class="label">${day}</span>
          <span class="date">${label}</span>
        </button>
      `;
    }).join("");

    // 버튼 핸들러 부착
    $daysWrap.querySelectorAll(".wk-day").forEach((btn) => {
      btn.addEventListener("click", () => {
        const iso = btn.dataset.date;
        const d = new Date(iso + "T00:00:00");
        selectDate(d, { load: true, rerender: true });
      });
    });

    if ($label) {
      $label.textContent = `${selectedDate.getMonth() + 1}/${selectedDate.getDate()} (${DAYS_KO[selectedDate.getDay()]})`;
    }
  }

  // ========= 날짜 범위 보정 =========
  function clampToRange(d) {
    if (d < RANGE_START) return RANGE_START;
    if (d > RANGE_END) return RANGE_END;
    return d;
  }

  // ========= 날짜 선택 처리 =========
  async function selectDate(d, opts = { load: true, rerender: true }) {
    selectedDate = clampToRange(startOfDayKST(d));
    if ($dateInput) {
      $dateInput.min = fmtISO(RANGE_START);
      $dateInput.max = fmtISO(RANGE_END);
      $dateInput.value = fmtISO(selectedDate);
    }
    if (opts.rerender) renderWeekBar(selectedDate);
    if (opts.load) await reloadPlanFor(selectedDate);
  }

  // ========= 데이터 가져오기 =========
  async function fetchDayItems(iso) {
    try {
      const r = await fetch(`${API_BASE}/taskitems/?date=${encodeURIComponent(iso)}`, {
        headers: authHeaders(),
        credentials: "same-origin",
      });
      if (!r.ok) return [];
      const data = await r.json().catch(() => []);
      // pagination 호환
      return Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : []);
    } catch {
      return [];
    }
  }

  // by-date → plans (여러 개면 첫 번째)
  async function fetchPlansByDate(iso) {
    try {
      const r = await fetch(`${API_BASE}/workoutplans/by-date/?date=${encodeURIComponent(iso)}`, {
        headers: authHeaders(),
        credentials: "same-origin",
      });
      const data = await r.json().catch(() => []);
      const arr = Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : []);
      return { ok: r.ok, plans: arr };
    } catch {
      return { ok: false, plans: [] };
    }
  }

  // ========= 플랜 로딩(날짜 기준) & 렌더 =========
  async function reloadPlanFor(d) {
    const iso = fmtISO(d);
    if (typeof showLoading === "function") showLoading("Loading workout plan...");

    try {
      // 1) 플랜 후보 조회
      const { ok, plans } = await fetchPlansByDate(iso);

      // 2) 해당 날짜 TaskItem 조회 (플랜 없을 때도 목록은 보여주기 위함)
      const items = await fetchDayItems(iso);

      // 라벨 업데이트
      if ($planDateLabel) $planDateLabel.textContent = iso;

      if (!ok || !plans.length) {
        // 플랜이 없어도 TaskItem이 있으면 그것만 표시
        if ($planIdEl) $planIdEl.textContent = "-";
        if ($planCntEl) $planCntEl.textContent = String(items.length);
        if ($planMinEl) {
          const totalMin = items.reduce((s, x) => s + (Number(x.duration_min) || 0), 0);
          $planMinEl.textContent = String(totalMin);
        }
        renderTasksList(items);
        window.currentPlan = undefined;
        return;
      }

      // 3) 플랜 1개 선택
      const plan = plans[0];
      window.currentPlan = plan;

      // 4) 합계/카운트 계산 후 렌더
      const totalMin = (plan.total_duration_min != null)
        ? Number(plan.total_duration_min)
        : items.reduce((s, x) => s + (Number(x.duration_min) || 0), 0);

      renderCurrentPlan(
        { id: plan.id, tasks: items, tasks_count: items.length, total_duration_min: totalMin },
        d
      );
    } finally {
      if (typeof hideLoading === "function") hideLoading();
    }
  }

  // ========= 목록 렌더 =========
  function renderTasksList(items) {
    if (!$list) return;
    if (!Array.isArray(items) || !items.length) {
      $list.innerHTML = "<em>No tasks yet</em>";
      return;
    }

    $list.innerHTML = items.map((t) => `
      <div class="task row between" data-id="${t.id}">
        <div>
          <b>${t?.exercise_detail?.name || t?.exercise_name || "(exercise)"}</b>
          <span class="muted">
            ${(t?.target_sets ?? "-")}x${(t?.target_reps ?? "-")}
            · ${t?.intensity ?? "-"} · ${t?.duration_min ?? 0}m
          </span>
        </div>
        <div class="row" style="gap:6px;">
          <button class="btn btn--ghost" data-action="delete" aria-label="Delete Task">Delete</button>
        </div>
      </div>
    `).join("");

    // 삭제 동작
    $list.querySelectorAll("[data-action='delete']").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        const el = e.currentTarget.closest(".task");
        const id = Number(el?.dataset?.id);
        if (!id) return;
        if (!confirm("삭제할까요?")) return;
        try {
          const r = await fetch(`${API_BASE}/taskitems/${id}/`, {
            method: "DELETE",
            headers: authHeaders(),
            credentials: "same-origin",
          });
          if (r.ok || r.status === 204) {
            await reloadPlanFor(selectedDate);
          } else {
            if (typeof toastError === "function") toastError("삭제 실패");
            else alert("삭제 실패");
          }
        } catch {
          if (typeof toastError === "function") toastError("네트워크 오류");
          else alert("네트워크 오류");
        }
      });
    });
  }

  function renderCurrentPlan(planLike, d) {
    const items = Array.isArray(planLike?.tasks) ? planLike.tasks : [];

    if ($planDateLabel) $planDateLabel.textContent = fmtISO(d);
    if ($planIdEl) $planIdEl.textContent = planLike?.id ?? "-";
    if ($planCntEl) $planCntEl.textContent = planLike?.tasks_count ?? items.length;

    const totalMin = planLike?.total_duration_min ?? items.reduce((s, x) => s + (Number(x.duration_min) || 0), 0);
    if ($planMinEl) $planMinEl.textContent = totalMin;

    renderTasksList(items);

    // 외부에서 재사용할 수 있게 노출
    window.renderCurrentPlan = renderCurrentPlan;
  }

  // ========= Ensure Today Plan =========
  async function ensureTodayPlan() {
    try {
      if (typeof showLoading === "function") showLoading("Ensuring today plan...");
      const res = await fetch(ENSURE_URL, {
        method: "POST",
        headers: authHeaders(),
        credentials: "same-origin",
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = body?.detail || `Ensure failed (HTTP ${res.status})`;
        if (typeof toastError === "function") toastError(msg);
        throw new Error(msg);
      }
      // 오늘 날짜로 리로드
      const today = TODAY;
      window.currentPlan = body || window.currentPlan;
      await reloadPlanFor(today);

      // 플랜 위자드가 있으면 열기
      if (typeof window.openPlanWizard === "function") {
        window.openPlanWizard();
      }
    } catch (err) {
      console.error(err);
    } finally {
      if (typeof hideLoading === "function") hideLoading();
    }
  }

  // ========= 초기화 =========
  function initOnce() {
    if (isInitBound) return;
    isInitBound = true;

    // date input 초기값/범위
    if ($dateInput) {
      $dateInput.min = fmtISO(RANGE_START);
      $dateInput.max = fmtISO(RANGE_END);
      $dateInput.value = fmtISO(TODAY);
    }

    // 날짜 로드
    if ($loadByDate) {
      $loadByDate.addEventListener("click", (e) => {
        e.preventDefault();
        const v = $dateInput?.value;
        if (!v) return alert("날짜를 선택해 주세요.");
        const d = new Date(v + "T00:00:00");
        selectDate(d, { load: true, rerender: true });
      });
    }

    // Ensure Today
    if ($ensureToday) {
      $ensureToday.addEventListener("click", async (e) => {
        e.preventDefault();
        const btn = e.currentTarget;
        btn.disabled = true;
        try {
          await selectDate(TODAY, { load: false, rerender: true });
          await ensureTodayPlan();
        } finally {
          btn.disabled = false;
        }
      });
    }

    // Prev/Next
    document.getElementById("wk-prev-day")?.addEventListener("click", () => {
      selectDate(addDays(selectedDate, -1), { load: true, rerender: true });
    });
    document.getElementById("wk-next-day")?.addEventListener("click", () => {
      selectDate(addDays(selectedDate, 1), { load: true, rerender: true });
    });

    // 위자드에서 플랜 생성/수정 완료 → 현재/오늘 갱신
    window.addEventListener("plan:updated", (ev) => {
      const plan = ev.detail || {};
      const created = plan?.created_at ? new Date(plan.created_at) : TODAY;
      const sameDay = fmtISO(created) === fmtISO(selectedDate);
      if (sameDay) reloadPlanFor(selectedDate);
      else if (fmtISO(created) === fmtISO(TODAY)) selectDate(TODAY);
    });
  }

  async function boot() {
    initOnce();
    // 초기 진입: 오늘 기준
    await selectDate(TODAY, { load: true, rerender: true });
  }

  // 노출 (다른 스크립트에서 사용할 수 있게)
  window.reloadPlanFor = reloadPlanFor;
  window.selectDate = selectDate;
  window.ensureTodayPlan = ensureTodayPlan;

  // 실행
  document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", boot)
    : boot();
})();

// --- [옵션] Task 완료 토글 (C5) ---------------------------------------------
async function toggleTaskCompletion(taskId, completed) {
  try {
    const r = await fetch(`${API_BASE}/taskitems/${taskId}/`, {
      method: "PATCH",
      headers: authHeaders(),
      credentials: "same-origin",
      body: JSON.stringify({ completed: !!completed })
    });
    if (!r.ok) throw new Error(`PATCH ${r.status}`);
    await reloadPlanFor(selectedDate);
  } catch (e) {
    if (typeof toastError === "function") toastError("토글 실패");
    else alert("토글 실패");
  }
}

// 렌더 시 체크박스 추가 & 토글 바인딩 (renderTasksList 교체용 헬퍼)
function renderTasksList(items) {
  if (!$list) return;
  if (!Array.isArray(items) || !items.length) {
    $list.innerHTML = "<em>No tasks yet</em>";
    return;
  }

  $list.innerHTML = items.map((t) => {
    const done = !!t.completed;
    return `
      <div class="task row between" data-id="${t.id}">
        <label class="row" style="gap:8px; align-items:center; cursor:pointer;">
          <input type="checkbox" data-action="toggle" ${done ? "checked" : ""} aria-label="Complete Task">
          <div>
            <b>${t?.exercise_detail?.name || t?.exercise_name || "(exercise)"}</b>
            <span class="muted">
              ${(t?.target_sets ?? "-")}x${(t?.target_reps ?? "-")}
              · ${t?.intensity ?? "-"} · ${t?.duration_min ?? 0}m
            </span>
          </div>
        </label>
        <div class="row" style="gap:6px;">
          <button class="btn btn--ghost" data-action="delete" aria-label="Delete Task">Delete</button>
        </div>
      </div>
    `;
  }).join("");

  // 체크 토글
  $list.querySelectorAll("[data-action='toggle']").forEach((cb) => {
    cb.addEventListener("change", async (e) => {
      const el = e.currentTarget.closest(".task");
      const id = Number(el?.dataset?.id);
      await toggleTaskCompletion(id, e.currentTarget.checked);
    });
  });

  // 삭제
  $list.querySelectorAll("[data-action='delete']").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const el = e.currentTarget.closest(".task");
      const id = Number(el?.dataset?.id);
      if (!id) return;
      if (!confirm("삭제할까요?")) return;
      try {
        const r = await fetch(`${API_BASE}/taskitems/${id}/`, {
          method: "DELETE",
          headers: authHeaders(),
          credentials: "same-origin",
        });
        if (r.ok || r.status === 204) await reloadPlanFor(selectedDate);
        else (typeof toastError === "function" ? toastError("삭제 실패") : alert("삭제 실패"));
      } catch {
        (typeof toastError === "function" ? toastError("네트워크 오류") : alert("네트워크 오류"));
      }
    });
  });
}

