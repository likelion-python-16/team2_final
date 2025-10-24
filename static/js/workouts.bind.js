/* static/js/workouts.bind.js
 * Workouts page bindings (C1~C6 + 날짜/주간/± 내비 + 체크 토글/삭제 + C7~C9 훅)
 * 원칙: "추가만" (기존 파일/템플릿 삭제 없이 동작)
 * 의존(있으면 사용): window.authHeaders, showLoading/hideLoading, toastError, formatYMD, openPlanWizard
 * HTML 훅: #wk-plan-date, #wk-load-by-date, #wk-ensure-today, #wk-days, #wk-prev-day, #wk-next-day, #wk-current-label,
 *         #wk-plan-date-label, #wk-plan-id, #wk-plan-taskcount, #wk-plan-duration, #wk-tasks-list
 */
(function () {
  "use strict";

  // ========= 공통 =========
  const API_BASE = (typeof window.API === "string" && window.API) ? window.API : "/api";

  function getCookie(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }

  function authFetch(url, options = {}) {
    const token = localStorage.getItem('access');
    const headers = { ...(options.headers || {}), Authorization: `Bearer ${token}` };
    return fetch(url, { ...options, headers });
  }


  // 🔐 안전한 헤더 래퍼
  function authHeaders() {
    if (typeof window.authHeaders === "function") return window.authHeaders();
    const headers = { "Content-Type": "application/json" };
    const csrf = getCookie("csrftoken");
    if (csrf) headers["X-CSRFToken"] = csrf;
    const access = localStorage.getItem("access");
    if (access) headers["Authorization"] = `Bearer ${access}`;
    return headers;
  }

  // ========= 날짜 유틸 (KST 기준) =========
  function toKST(d) { return new Date(d.toLocaleString("en-US", { timeZone: "Asia/Seoul" })); }
  function startOfDayKST(d) { const t = toKST(d); return new Date(t.getFullYear(), t.getMonth(), t.getDate()); }
  function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
  function fmtISO(d) {
    if (typeof window.formatYMD === "function") return window.formatYMD(d);
    const y = d.getFullYear(), m = String(d.getMonth()+1).padStart(2,"0"), dd = String(d.getDate()).padStart(2,"0");
    return `${y}-${m}-${dd}`;
  }
  const DAYS_KO = ["일","월","화","수","목","금","토"];

  // ========= 상태 =========
  const TODAY = startOfDayKST(new Date());
  const RANGE_START = addDays(TODAY, -59);
  const RANGE_END = TODAY;

  let selectedDate = TODAY;
  let isInitBound = false;
  const ENSURE_URL = `${API_BASE}/workoutplans/today/ensure/`;

  // 전역 노출(안전 게터 포함)
  window.selectedDate = selectedDate;
  if (typeof window.getSelectedDate !== 'function') {
    window.getSelectedDate = () => selectedDate;
  }

  // ========= DOM 캐시 =========
  const $daysWrap       = document.getElementById("wk-days");
  const $dateInput      = document.getElementById("wk-plan-date");
  const $loadByDate     = document.getElementById("wk-load-by-date");
  const $ensureToday    = document.getElementById("wk-ensure-today");
  const $label          = document.getElementById("wk-current-label");
  const $planDateLabel  = document.getElementById("wk-plan-date-label");
  const $planIdEl       = document.getElementById("wk-plan-id");
  const $planCntEl      = document.getElementById("wk-plan-taskcount");
  const $planMinEl      = document.getElementById("wk-plan-duration");
  const $list           = document.getElementById("wk-tasks-list");

  // ========= C6: 상태 라벨 동기화 =========
  function setStatusLabel(txt) {
    document.querySelectorAll("[data-workout-status]").forEach((el) => {
      el.textContent = txt;
      el.classList.remove("badge-started", "badge-completed");
      if (txt === "In Progress") el.classList.add("badge-started");
      if (txt === "Completed")   el.classList.add("badge-completed");
    });
  }
  function syncStatusFromItems(items) {
    const total = Array.isArray(items) ? items.length : 0;
    const done  = (Array.isArray(items) ? items : []).filter(x => !!x.completed).length;
    if (total === 0 || done === 0) { setStatusLabel("Not Started"); return; }
    if (done < total) { setStatusLabel("In Progress"); return; }
    setStatusLabel("Completed");
  }

  // ========= Week Bar 렌더 =========
  function startOfWeekMon(d) {
    const wd = d.getDay(); // 0=일
    const diff = (wd === 0) ? -6 : (1 - wd); // 월=1
    return addDays(d, diff);
  }

  function renderWeekBar(centerDate) {
    if (!$daysWrap) return;
    const start = startOfWeekMon(centerDate);
    const days  = Array.from({ length: 7 }, (_, i) => addDays(start, i));
    const selectedISO = fmtISO(selectedDate);

    $daysWrap.innerHTML = days.map((d) => {
      const isActive = fmtISO(d) === selectedISO;
      const label = `${d.getMonth()+1}/${d.getDate()}`;
      const day   = DAYS_KO[d.getDay()];
      return `
        <button type="button" class="wk-day ${isActive ? "is-active" : ""}" data-date="${fmtISO(d)}" aria-pressed="${isActive}">
          <span class="label">${day}</span>
          <span class="date">${label}</span>
        </button>
      `;
    }).join("");

    $daysWrap.querySelectorAll(".wk-day").forEach((btn) => {
      btn.addEventListener("click", () => {
        const iso = btn.dataset.date;
        const d   = new Date(iso + "T00:00:00");
        selectDate(d, { load: true, rerender: true });
      });
    });

    if ($label) $label.textContent = `${selectedDate.getMonth()+1}/${selectedDate.getDate()} (${DAYS_KO[selectedDate.getDay()]})`;

    // 선택된 날이 보이도록 정렬
    const active = $daysWrap.querySelector(".wk-day.is-active");
    active?.scrollIntoView({ block: "nearest", inline: "center" });
  }

  // ========= 날짜 선택 =========
  function clampToRange(d) {
    if (d < RANGE_START) return RANGE_START;
    if (d > RANGE_END)   return RANGE_END;
    return d;
  }

  async function selectDate(d, opts = { load: true, rerender: true }) {
    selectedDate = clampToRange(startOfDayKST(d));
    window.selectedDate = selectedDate;          // 항상 최신값 전역 동기화
    if (typeof window.getSelectedDate !== 'function') {
      window.getSelectedDate = () => selectedDate;
    }

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
      return Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : []);
    } catch (e) { return []; }
  }

  async function fetchPlansByDate(iso) {
    try {
      const r = await fetch(`${API_BASE}/workoutplans/by-date/?date=${encodeURIComponent(iso)}`, {
        headers: authHeaders(),
        credentials: "same-origin",
      });
      const data = await r.json().catch(() => []);
      const arr  = Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : []);
      return { ok: r.ok, plans: arr };
    } catch (e) { return { ok: false, plans: [] }; }
  }

  // ========= C7/C8/C9: Today Summary / Recommendations / AI Insights =========
  async function fetchJsonSafe(url) {
    try {
      const r = await fetch(url, { headers: authHeaders(), credentials: "same-origin" });
      if (!r.ok) return null;
      return await r.json().catch(() => null);
    } catch (e) { return null; }
  }

  function renderSummary(data) {
    const box = document.querySelector("[data-summary-body]");
    if (!box) return;
    if (!data) { box.textContent = "No summary available."; return; }
    const lines = [];
    if (data.total_min != null) lines.push(`Total: ${data.total_min} min`);
    if (data.tasks_count != null && data.completed_count != null) lines.push(`Progress: ${data.completed_count}/${data.tasks_count}`);
    if (data.calories != null) lines.push(`Calories: ~${data.calories} kcal`);
    if (data.note) lines.push(data.note);
    box.innerHTML = lines.length ? lines.map(x=>`<div>${x}</div>`).join("") : "No summary available.";
  }

  function renderRecommendations(list) {
    const ul = document.querySelector("[data-reco-list]");
    if (!ul) return;
    if (!Array.isArray(list) || !list.length) { ul.innerHTML = `<li class="muted">No recommendations.</li>`; return; }
    ul.innerHTML = list.map((r, i) => {
      const title = r.title || r.text || `Recommendation ${i+1}`;
      const action = (r.action_text && r.action_url)
        ? ` <a href="${r.action_url}" class="link">${r.action_text}</a>` : "";
      return `<li>${title}${action}</li>`;
    }).join("");
  }

  function renderInsights(data) {
    const box = document.querySelector("[data-insights-body]");
    if (!box) return;
    if (!data) { box.textContent = "No insights yet."; return; }
    if (Array.isArray(data.bullets)) {
      box.innerHTML = `<ul>${data.bullets.map(t=>`<li>${t}</li>`).join("")}</ul>`;
    } else if (data.message) {
      box.textContent = data.message;
    } else {
      box.textContent = "No insights yet.";
    }
  }

  async function refreshSmartPanels(iso, planId) {
    // 백엔드가 없어도 에러 없이 "No ..."로 안전 처리
    const summary = await (await authFetch(`${API_BASE}/workoutplans/summary/?date=${encodeURIComponent(iso)}`)).json();
    renderSummary(summary);

    const reco = await fetchJsonSafe(`${API_BASE}/recommendations/?date=${encodeURIComponent(iso)}${planId?`&workout_plan=${planId}`:""}`);
    renderRecommendations(Array.isArray(reco?.results) ? reco.results : reco);

    const insights = await fetchJsonSafe(`${API_BASE}/insights/today/?date=${encodeURIComponent(iso)}${planId?`&workout_plan=${planId}`:""}`);
    renderInsights(insights);
  }

  // ========= 목록 렌더 & 상호작용 =========
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

  function renderTasksList(items) {
    if (!$list) return;
    if (!Array.isArray(items) || !items.length) { $list.innerHTML = "<em>No tasks yet</em>"; syncStatusFromItems([]); return; }

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
        } catch (e) {
          (typeof toastError === "function" ? toastError("네트워크 오류") : alert("네트워크 오류"));
        }
      });
    });

    // 상태 동기화
    syncStatusFromItems(items);
  }

  function renderCurrentPlan(planLike, d) {
    const items = Array.isArray(planLike?.tasks) ? planLike.tasks : [];
    if ($planDateLabel) $planDateLabel.textContent = fmtISO(d);
    if ($planIdEl)      $planIdEl.textContent      = planLike?.id ?? "-";
    if ($planCntEl)     $planCntEl.textContent     = planLike?.tasks_count ?? items.length;

    const totalMin = planLike?.total_duration_min ?? items.reduce((s, x) => s + (Number(x.duration_min) || 0), 0);
    if ($planMinEl) $planMinEl.textContent = totalMin;

    renderTasksList(items);
  }

  // ========= 날짜 로딩 =========
  async function reloadPlanFor(d) {
    const iso = fmtISO(d);
    if (typeof showLoading === "function") showLoading("Loading workout plan...");
    try {
      const { ok, plans } = await fetchPlansByDate(iso);
      const items = await fetchDayItems(iso);

      if ($planDateLabel) $planDateLabel.textContent = iso;

      if (!ok || !plans.length) {
        if ($planIdEl)  $planIdEl.textContent  = "-";
        if ($planCntEl) $planCntEl.textContent = String(items.length);
        if ($planMinEl) $planMinEl.textContent = String(items.reduce((s,x)=> s + (Number(x.duration_min)||0), 0));
        renderTasksList(items);
        window.currentPlan = undefined;
        return;
      }

      const plan = plans[0];
      window.currentPlan = plan;

      const totalMin = (plan.total_duration_min != null)
        ? Number(plan.total_duration_min)
        : items.reduce((s, x) => s + (Number(x.duration_min) || 0), 0);

      renderCurrentPlan(
        { id: plan.id, tasks: items, tasks_count: items.length, total_duration_min: totalMin },
        d
      );

      // 상태 동기화(안전)
      syncStatusFromItems(items);
    } finally {
      if (typeof hideLoading === "function") hideLoading();
    }

    // ✅ C7~C9 패널 갱신
    await refreshSmartPanels(fmtISO(d), window.currentPlan?.id);
  }

  // ========= Ensure Today Plan (C1) =========
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
      window.currentPlan = body || window.currentPlan;
      await reloadPlanFor(TODAY);

      if (typeof window.openPlanWizard === "function") window.openPlanWizard();
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

    if ($dateInput) {
      $dateInput.min = fmtISO(RANGE_START);
      $dateInput.max = fmtISO(RANGE_END);
      $dateInput.value = fmtISO(TODAY);

      // Enter로 바로 로드
      $dateInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          $loadByDate?.click();
        }
      });
    }

    // Load by Date
    if ($loadByDate) {
      $loadByDate.addEventListener("click", async (e) => {
        e.preventDefault();
        const v = $dateInput?.value;
        if (!v) return alert("날짜를 선택해 주세요.");
        const btn = e.currentTarget;
        btn.disabled = true;
        try {
          const d = new Date(v + "T00:00:00");
          await selectDate(d, { load: true, rerender: true });
        } finally {
          btn.disabled = false;
        }
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

    // --- [옵션] B7 인라인 Task 추가 (폼이 있을 때만 동작) -------------------
    (function bindInlineAddForWorkouts(){
      const $form = document.getElementById("wk-inline-task-form");
      if (!$form) return;

      const $name = document.getElementById("wk-new-name");
      const $sets = document.getElementById("wk-new-sets");
      const $reps = document.getElementById("wk-new-reps");
      const $min  = document.getElementById("wk-new-min");

      $form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!$name.value.trim()) return $name.focus();

        // 현재 플랜 ID 확보
        let planId = window.currentPlan?.id;
        if (!planId) {
          const iso = fmtISO(selectedDate);
          const r = await fetch(`${API_BASE}/workoutplans/by-date/?date=${encodeURIComponent(iso)}`, {
            headers: authHeaders(),
            credentials: "same-origin",
          });
          const data  = await r.json().catch(() => []);
          const plans = Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : []);
          planId = plans?.[0]?.id;
        }
        if (!planId) return alert("선택한 날짜의 플랜이 없어요. 먼저 Generate/Load 해주세요.");

        const payload = {
          workout_plan: planId,
          exercise_name: $name.value.trim(),
          target_sets: $sets.value ? Number($sets.value) : null,
          target_reps: $reps.value ? Number($reps.value) : null,
          duration_min: $min.value  ? Number($min.value)  : null,
        };

        try {
          const res = await fetch(`${API_BASE}/taskitems/`, {
            method: "POST",
            headers: authHeaders(),
            credentials: "same-origin",
            body: JSON.stringify(payload),
          });
          if (!res.ok) throw new Error(`POST ${res.status}`);

          $name.value = ""; $sets.value = ""; $reps.value = ""; $min.value = "";
          $name.focus();

          await reloadPlanFor(selectedDate);
        } catch (err) {
          console.error(err);
          (window.toastError ? toastError("추가에 실패했어요.") : alert("추가에 실패했어요."));
        }
      });
    })();
  }

  async function boot() {
    initOnce();
    window.selectedDate = TODAY;
    if (typeof window.getSelectedDate !== 'function') {
      window.getSelectedDate = () => selectedDate;
    }
    await selectDate(TODAY, { load: true, rerender: true });
  }

  // 노출
  window.reloadPlanFor   = reloadPlanFor;
  window.selectDate      = selectDate;
  window.ensureTodayPlan = ensureTodayPlan;

  // 실행
  document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", boot)
    : boot();
})();
