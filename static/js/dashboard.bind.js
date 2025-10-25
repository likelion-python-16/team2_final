// static/js/dashboard.bind.js
// Scope: Dashboard B1~B7
// - B1: 오늘 플랜 로드
// - B2: 제목 주입
// - B3: 진행도/링/상태/체크리스트
// - 접기/펼치기, 유형별 아코디언, DOM 중복 제거, 토글 PATCH/삭제 DELETE
// - (선택) 인라인 추가(B7): data-inline-task-form 있으면 자동 활성화
// 원칙: 템플릿/스타일은 "추가만", 삭제/대수정 없음

(function () {
  "use strict";

  // ─────────────────────────────────────────────────────────────
  // A1 Fallback API (api.js 부재 대비)
  // ─────────────────────────────────────────────────────────────
  const api = (function ensureApi() {
    if (window.api?.get && window.api?.patch && window.api?.post && window.api?.del) return window.api;

    const headers = () => (window.authHeaders ? window.authHeaders() : { "Content-Type": "application/json" });
    async function fetchJson(url, opts = {}) {
      const res = await fetch(url, { credentials: "same-origin", headers: headers(), ...opts });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const err = new Error(data?.detail || `HTTP ${res.status}`);
        err.status = res.status;
        err.data = data;
        throw err;
      }
      return data;
    }
    return {
      get:  (url)      => fetchJson(url),
      patch:(url,body) => fetchJson(url, { method:"PATCH", body: JSON.stringify(body||{}) }),
      post: (url,body) => fetchJson(url, { method:"POST",  body: JSON.stringify(body||{}) }),
      del:  (url)      => fetchJson(url, { method:"DELETE" }),
    };
  })();

  const ui = window.ui || {};
  const dateUtils = window.dateUtils || {};

  // ─────────────────────────────────────────────────────────────
  // B1: 오늘 플랜 로드
  // ─────────────────────────────────────────────────────────────
  async function loadTodayPlan() {
    const today = dateUtils.todayISO?.() || new Date().toISOString().slice(0, 10);
    try {
      const list = await api.get(`/api/workoutplans/by-date/?date=${today}`);
      const plans = Array.isArray(list) ? list : (Array.isArray(list?.results) ? list.results : []);
      if (!plans?.length) {
        console.info("[B1] 오늘 플랜 없음:", today);
        return null;
      }
      const planId = plans[0].id;
      const plan = await api.get(`/api/workoutplans/${planId}/`);
      return plan;
    } catch (err) {
      if (!ui.handleAuthError?.(err)) ui.toastError?.("오늘 플랜을 불러오지 못했습니다.");
      return null;
    }
  }
  window.loadTodayPlan = loadTodayPlan; // 다른 스크립트에서 재사용

  // ─────────────────────────────────────────────────────────────
  // B2: 제목 동적화
  // ─────────────────────────────────────────────────────────────
  function setPlanTitleFrom(plan) {
    const nodes = document.querySelectorAll("[data-plan-title]");
    if (!nodes.length) return;
    const iso = plan?.date || dateUtils.todayISO?.() || new Date().toISOString().slice(0, 10);
    const title = (plan?.name && String(plan.name).trim())
      ? String(plan.name).trim()
      : (plan?.target ? `${iso} · ${plan.target}` : `${iso} · Workout`);
    nodes.forEach((el) => { el.textContent = title; });
  }

  async function injectTodayTitle() {
    try {
      const plan = await loadTodayPlan();
      if (plan) setPlanTitleFrom(plan);
    } catch {
      ui.toastError?.("제목을 불러오지 못했습니다.");
    }
  }

  // ─────────────────────────────────────────────────────────────
  // B3: 진행도·링·상태·체크리스트
  // ─────────────────────────────────────────────────────────────
  async function loadTasksForPlan(planId) {
    try {
      const resp = await api.get(`/api/taskitems/?workout_plan=${encodeURIComponent(planId)}`);
      return Array.isArray(resp) ? resp : (Array.isArray(resp?.results) ? resp.results : []);
    } catch (err) {
      if (!ui.handleAuthError?.(err)) ui.toastError?.("작업 목록을 불러오지 못했습니다.");
      return [];
    }
  }

  function readDailyTasksFromServer() {
    const list = document.getElementById("dailyTasks");
    if (!list) return null;
    const items = Array.from(list.querySelectorAll("li.task-card__item"));
    if (!items.length) return { done: 0, total: 0 };
    let done = 0;
    for (const li of items) {
      const attr = li.getAttribute("data-completed");
      const checkedByAttr = attr === "true";
      const cb = li.querySelector("[data-task-checkbox]");
      const checkedByInput = cb ? !!cb.checked : false;
      if (checkedByAttr || checkedByInput || li.classList.contains("is-complete")) done++;
    }
    return { done, total: items.length };
  }

  function updateProgressUsingDailyOrWorkout(workoutTasks) {
    const daily = readDailyTasksFromServer();
    let done = 0, total = 0;

    if (daily && daily.total > 0) {
      done = daily.done;
      total = daily.total;
    } else {
      const wt = Array.isArray(workoutTasks) ? workoutTasks : [];
      total = wt.length;
      done = wt.filter((t) => !!t.completed).length;
    }

    const pct = total ? Math.round((done / total) * 100) : 0;

    // 0/n, % 텍스트 & 중앙 텍스트
    document.querySelectorAll("[data-progress-count]").forEach((el) => { el.textContent = `${done}/${total}`; });
    document.querySelectorAll("[data-progress-percent]").forEach((el) => { el.textContent = `${pct}%`; });
    document.querySelectorAll(".progress-ring__value-text").forEach((el) => { el.textContent = `${done}/${total}`; });

    // 링
    const ring = document.querySelector(".progress-ring__value-circle");
    if (ring) {
      const R = Number(ring.getAttribute("r") || 54);
      const C = 2 * Math.PI * R;
      ring.style.strokeDasharray = `${C}`;
      ring.style.strokeDashoffset = String(C - (pct / 100) * C);
    }

    // 상태 배지 (C6 규칙: 100%만 Completed)
    document.querySelectorAll("[data-workout-status]").forEach((el) => {
      let txt = "Not Started";
      if (total > 0 && done === total) txt = "Completed";
      else if (done > 0) txt = "In Progress";
      el.textContent = txt;
      el.classList.remove("badge-started", "badge-completed");
      if (txt === "In Progress") el.classList.add("badge-started");
      if (txt === "Completed") el.classList.add("badge-completed");
    });

    // a11y 안내 (한 곳만)
    const region = document.querySelector("[data-progress-count]");
    if (region) {
      region.setAttribute("role", "status");
      region.setAttribute("aria-live", "polite");
      region.setAttribute("aria-label", `오늘 진행도 ${done}개 완료, 총 ${total}개, ${pct}%`);
    }

    // 게이지 바 (있을 때만)
    const fill = document.getElementById("progressGoalFill");
    if (fill) fill.style.width = `${pct}%`;
  }

  // ─────────────────────────────────────────────────────────────
  // 체크리스트 렌더 (+ 접기)
  // ─────────────────────────────────────────────────────────────
  function renderChecklist(tasks, planId) {
    const list = document.querySelector("[data-task-list]");
    if (!list) return;

    list.innerHTML = "";
    const frag = document.createDocumentFragment();

    // 정렬: order → id
    tasks.sort((a, b) => {
      const ao = (a?.order ?? 1e9), bo = (b?.order ?? 1e9);
      if (ao !== bo) return ao - bo;
      return (a?.id || 0) - (b?.id || 0);
    });

    for (const t of tasks) {
      const li = document.createElement("li");
      li.className = "task-row";
      li.setAttribute("data-task-item", "");

      const name = t?.exercise_detail?.name || t?.exercise_name || t?.exercise || "Task";
      const done = !!t?.completed;

      li.innerHTML = `
        <label class="row between task" data-id="${t.id}" style="gap:10px; padding:6px 0;">
          <span class="row" style="gap:8px; align-items:center;">
            <input type="checkbox" data-action="toggle" ${done ? "checked" : ""} aria-label="Complete Task">
            <b>${name}</b>
            <span class="muted">
              ${(t?.target_sets ?? "-")}x${(t?.target_reps ?? "-")} · ${t?.intensity ?? "-"} · ${t?.duration_min ?? 0}m
            </span>
          </span>
          <button class="btn btn--ghost" data-action="delete">Delete</button>
        </label>
      `;
      frag.appendChild(li);
    }
    list.appendChild(frag);

    // 진행도 업데이트
    updateProgressUsingDailyOrWorkout(tasks);

    // 이벤트 위임 (중복 바인딩 방지)
    if (!list.__boundHandlers) {
      list.addEventListener("change", async (e) => {
        const cb = e.target;
        if (!(cb instanceof HTMLInputElement)) return;
        if (cb.getAttribute("data-action") !== "toggle") return;
        const row = cb.closest(".task");
        const id = Number(row?.dataset?.id);
        const prev = !cb.checked;

        try {
          await api.patch(`/api/taskitems/${id}/`, { completed: cb.checked });
          // 재조회로 정확도 확보
          const plan = await loadTodayPlan();
          const fresh = plan ? await loadTasksForPlan(plan.id) : [];
          renderChecklist(fresh, plan?.id);
          renderTasksAccordion(fresh, plan?.id);
          dedupeTaskDomListByName("[data-task-list]");
        } catch (err) {
          cb.checked = prev;
          if (!ui.handleAuthError?.(err)) ui.toastError?.("저장에 실패했습니다. 다시 시도해 주세요.");
        }
      });

      list.addEventListener("click", async (e) => {
        const btn = e.target.closest("[data-action='delete']");
        if (!btn) return;
        const row = btn.closest(".task");
        const id = Number(row?.dataset?.id);
        if (!id) return;
        if (!confirm("삭제할까요?")) return;

        try {
          await api.del(`/api/taskitems/${id}/`);
          const plan = await loadTodayPlan();
          const fresh = plan ? await loadTasksForPlan(plan.id) : [];
          renderChecklist(fresh, plan?.id);
          renderTasksAccordion(fresh, plan?.id);
          dedupeTaskDomListByName("[data-task-list]");
        } catch (err) {
          if (!ui.handleAuthError?.(err)) ui.toastError?.("삭제 실패");
        }
      });

      list.__boundHandlers = true;
    }

    // 접기(3개 기준)
    applyCollapsible(list, 3);
    // 렌더 후 DOM 중복 제거
    dedupeTaskDomListByName("[data-task-list]");
  }

  // ─────────────────────────────────────────────────────────────
  // 접기/펼치기 유틸
  // ─────────────────────────────────────────────────────────────
  function applyCollapsible(listEl, maxVisible = 3) {
    if (!listEl) return;
    listEl.classList.add("task-list--collapsible");

    const items = Array.from(listEl.querySelectorAll("li, [data-task-item]"));
    const total = items.length;
    const btn = getOrCreateToggleButton(listEl);

    if (total <= maxVisible) {
      if (btn) btn.hidden = true;
      return;
    }

    items.forEach((el, i) => { if (i >= maxVisible) el.classList.add("is-hidden"); });

    btn.hidden = false;
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-controls", listEl.id || "");
    btn.textContent = `더 보기 (${total - maxVisible})`;

    btn.onclick = () => {
      const expanded = btn.getAttribute("aria-expanded") === "true";
      if (expanded) {
        items.forEach((el, i) => { if (i >= maxVisible) el.classList.add("is-hidden"); });
        btn.setAttribute("aria-expanded", "false");
        btn.textContent = `더 보기 (${total - maxVisible})`;
      } else {
        items.forEach((el) => el.classList.remove("is-hidden"));
        btn.setAttribute("aria-expanded", "true");
        btn.textContent = "접기";
      }
    };
  }

  function getOrCreateToggleButton(listEl) {
    let btn = listEl.parentElement?.querySelector("[data-task-toggle]");
    if (!btn) {
      btn = document.createElement("button");
      btn.type = "button";
      btn.className = "task-toggle";
      btn.setAttribute("data-task-toggle", "");
      btn.hidden = true;
      btn.setAttribute("aria-label", "목록 더 보기/접기");
      listEl.insertAdjacentElement("afterend", btn);
    }
    return btn;
  }

  // ─────────────────────────────────────────────────────────────
  // 유형별 아코디언
  // ─────────────────────────────────────────────────────────────
  function getTypeKey(t) {
    return (t?.muscle_group || t?.body_part || t?.type || t?.category || t?.exercise_group || "기타");
  }

  function groupByType(tasks) {
    const map = new Map();
    for (const t of tasks) {
      const key = getTypeKey(t);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(t);
    }
    return map;
  }

  function renderTasksAccordion(tasks, planId) {
    const root = document.querySelector("[data-task-accordion]");
    if (!root) return;

    root.innerHTML = "";
    root.classList.add("accordion");

    const groups = groupByType(tasks);
    const sectionNames = Array.from(groups.keys()).sort((a, b) => String(a).localeCompare(String(b)));

    for (const name of sectionNames) {
      const section = document.createElement("section");
      section.className = "accordion__section";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "accordion__header";
      btn.setAttribute("aria-expanded", "false");

      const title = document.createElement("span");
      title.className = "accordion__title";
      title.textContent = name;

      const count = document.createElement("span");
      const items = groups.get(name) || [];
      const done = items.filter((x) => !!x.completed).length;
      count.className = "accordion__count";
      count.textContent = `${done}/${items.length}`;

      btn.appendChild(title);
      btn.appendChild(count);

      const panel = document.createElement("div");
      panel.className = "accordion__panel";
      panel.hidden = true;

      const ul = document.createElement("ul");
      ul.className = "accordion__list";

      // 정렬
      items.sort((a, b) => {
        const ao = (a?.order ?? 1e9), bo = (b?.order ?? 1e9);
        if (ao !== bo) return ao - bo;
        return (a?.id || 0) - (b?.id || 0);
      });

      for (const t of items) {
        const li = document.createElement("li");
        li.className = "accordion__item";
        li.setAttribute("data-task-item", "");
        const nameText = t?.exercise_detail?.name || t?.exercise_name || t?.exercise || "Task";
        const doneTask = !!t?.completed;
        li.innerHTML = `
          <label style="display:flex;gap:8px;align-items:center;">
            <input type="checkbox" ${doneTask ? "checked" : ""} data-task-id="${t.id}" aria-label="Complete Task" />
            <span class="${doneTask ? "done" : ""}">${nameText}</span>
          </label>
        `;
        ul.appendChild(li);
      }

      panel.appendChild(ul);
      section.appendChild(btn);
      section.appendChild(panel);
      root.appendChild(section);

      // 펼치기/접기
      btn.addEventListener("click", () => {
        const expanded = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", expanded ? "false" : "true");
        panel.hidden = expanded;
      });

      // 섹션 내 토글 (위임)
      if (!ul.__boundToggle) {
        ul.addEventListener("change", async (e) => {
          const cb = e.target;
          if (!(cb instanceof HTMLInputElement)) return;
          const id = cb.dataset.taskId;
          if (!id) return;
          const text = cb.parentElement?.querySelector("span");
          const prev = !cb.checked;

          try {
            await api.patch(`/api/taskitems/${id}/`, { completed: cb.checked });
            if (text) text.classList.toggle("done", cb.checked);

            // 섹션 카운트 갱신
            const all = Array.from(ul.querySelectorAll('input[type="checkbox"]'));
            const doneNow = all.filter((x) => x.checked).length;
            count.textContent = `${doneNow}/${all.length}`;

            // 상단 진행도 동기화(DOM/데일리 우선 정책으로 즉시)
            updateProgressUsingDailyOrWorkout(null);
            dedupeTaskDomListByName("[data-task-list]");
          } catch (err) {
            cb.checked = prev;
            if (!ui.handleAuthError?.(err)) ui.toastError?.("저장에 실패했습니다.");
          }
        });
        ul.__boundToggle = true;
      }

      // 섹션 접기 기본(3개)
      applyCollapsible(ul, 3);
    }
  }

  // ─────────────────────────────────────────────────────────────
  // DOM 중복 제거 + 진행도 재계산
  // ─────────────────────────────────────────────────────────────
  function normalizeNameKey(raw) {
    return String(raw || "")
      .toLowerCase()
      .replace(/\(.*?\)/g, "")         // 괄호 설명 제거
      .replace(/[^a-z0-9가-힣\s]/g, " ")// 특수문자 슬림화
      .replace(/\s+/g, " ")            // 공백 정리
      .trim();
  }

  function dedupeTaskDomListByName(containerSelector = "[data-task-list]") {
    const list = document.querySelector(containerSelector);
    if (!list) return;

    const seen = new Set();
    const items = Array.from(list.querySelectorAll("li[data-task-item], li.task-row"));

    for (const li of items) {
      const nameEl = li.querySelector("label span");
      const key = normalizeNameKey(nameEl ? nameEl.textContent : "");
      if (seen.has(key)) li.remove();
      else seen.add(key);
    }

    // DOM 기반 진행도 재계산
    const remaining = Array.from(list.querySelectorAll("li[data-task-item], li.task-row"));
    const total = remaining.length;
    const done = remaining.filter((li) => {
      const cb = li.querySelector('input[type="checkbox"]');
      return cb && cb.checked;
    }).length;

    const pct = total ? Math.round((done / total) * 100) : 0;

    document.querySelectorAll("[data-progress-count]").forEach((el) => { el.textContent = `${done}/${total}`; });
    document.querySelectorAll(".progress-ring__value-text").forEach((el) => { el.textContent = `${done}/${total}`; });
    document.querySelectorAll("[data-progress-percent]").forEach((el) => { el.textContent = `${pct}%`; });

    const ring = document.querySelector(".progress-ring__value-circle");
    if (ring) {
      const R = Number(ring.getAttribute("r") || 54);
      const C = 2 * Math.PI * R;
      ring.style.strokeDasharray = `${C}`;
      ring.style.strokeDashoffset = String(C - (pct / 100) * C);
    }

    document.querySelectorAll("[data-workout-status]").forEach((el) => {
      let txt = "Not Started";
      if (total > 0 && done === total) txt = "Completed";
      else if (done > 0) txt = "In Progress";
      el.textContent = txt;
    });

    // 접기 버튼 텍스트 새로고침
    const btn = list.parentElement?.querySelector("[data-task-toggle]");
    if (btn) {
      const maxVisible = 3;
      const hiddenCount = Math.max(0, total - maxVisible);
      const expanded = btn.getAttribute("aria-expanded") === "true";
      btn.hidden = total <= maxVisible;
      if (!btn.hidden) btn.textContent = expanded ? "접기" : `더 보기 (${hiddenCount})`;
    }
  }

  // ─────────────────────────────────────────────────────────────
  // 파이프라인 (B1~B3 + 아코디언 + 중복 제거)
  // ─────────────────────────────────────────────────────────────
  async function loadTodayPlanAndTasks() {
    const plan = await loadTodayPlan();
    const list = document.querySelector("[data-task-list]");
    if (!plan) {
      if (list) list.innerHTML = "";
      updateProgressUsingDailyOrWorkout([]); // Daily 없으면 0/0 처리
      return;
    }
    setPlanTitleFrom(plan); // B2
    const tasks = await loadTasksForPlan(plan.id);
    renderChecklist(tasks, plan.id);
    renderTasksAccordion(tasks, plan.id);
    updateProgressUsingDailyOrWorkout(tasks);
  }
  window.loadTodayPlanAndTasks = loadTodayPlanAndTasks;

  // ─────────────────────────────────────────────────────────────
  // (선택) B7: 인라인 Task 추가 — 대시보드 카드에서 바로 POST
  // 템플릿에 data-inline-task-form 이 있으면 자동 활성화.
  // ─────────────────────────────────────────────────────────────
  function bindInlineAddForDashboard() {
    const $form = document.querySelector("[data-inline-task-form]");
    if (!$form) return;

    const $name = $form.querySelector("[data-new-name]");
    const $sets = $form.querySelector("[data-new-sets]");
    const $reps = $form.querySelector("[data-new-reps]");
    const $min  = $form.querySelector("[data-new-min]");

    $form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!$name.value.trim()) return $name.focus();

      let plan = await loadTodayPlan();
      if (!plan?.id) {
        (window.toastError ? toastError("오늘 플랜이 없어요. 먼저 생성/로드해주세요.") : alert("오늘 플랜이 없어요."));
        return;
      }

      const payload = {
        workout_plan: plan.id,
        exercise_name: $name.value.trim(),
        target_sets: $sets.value ? Number($sets.value) : null,
        target_reps: $reps.value ? Number($reps.value) : null,
        duration_min: $min.value  ? Number($min.value)  : null,
      };

      try {
        await api.post(`/api/taskitems/`, payload);
        $name.value = ""; $sets.value = ""; $reps.value = ""; $min.value = "";
        $name.focus();

        // 최신으로 렌더/진행도 갱신
        await loadTodayPlanAndTasks();
      } catch (err) {
        if (!ui.handleAuthError?.(err)) (window.toastError ? toastError("추가 실패") : alert("추가 실패"));
      }
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 초기화
  // ─────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    // B1(로그만), B2, B3 파이프라인
    loadTodayPlan();          // 로깅/확인용
    injectTodayTitle();       // 제목
    loadTodayPlanAndTasks();  // 리스트/아코디언/진행도

    // Daily 체크 변경 시에도 진행도 동기화
    const dailyList = document.getElementById("dailyTasks");
    if (dailyList && !dailyList.__boundChange) {
      dailyList.addEventListener("change", () => updateProgressUsingDailyOrWorkout(null));
      dailyList.__boundChange = true;
    }

    // (선택) 인라인 추가
    bindInlineAddForDashboard();
  });
})();

// Today Summary / Insights / Recommendations (추가 모듈)
// 의존: window.api(get/post/patch/del), window.dateUtils.todayISO?, B1~B3에서 쓰는 DOM/스타일
// 필요 DOM ids: #sum-total-min, #sum-total-tasks, #sum-completed-tasks, #sum-total-kcal,
//               #insight-bullets, #recommendations, (선택) #selected-date, #toast
// ─────────────────────────────────────────────────────────────
(function () {
  "use strict";

  const $  = (sel, p = document) => p.querySelector(sel);
  const $$ = (sel, p = document) => Array.from(p.querySelectorAll(sel));

  function todayISO() {
    return (window.dateUtils?.todayISO?.()) || new Date().toISOString().slice(0, 10);
  }
  function selectedDate() {
    const el = $("#selected-date");
    return (el && el.value) ? el.value : todayISO();
  }
  function setTextSafe(el, val, fallback = "0") {
    if (!el) return;
    const n = Number.isFinite(Number(val)) ? Number(val) : fallback;
    el.textContent = String(n);
  }
  function showToast(msg) {
    const t = $("#toast");
    if (!t) return;
    t.textContent = msg;
    t.classList.remove("hidden");
    setTimeout(() => t.classList.add("hidden"), 2200);
  }

  // ----- render helpers -----
  function renderBullets(container, items) {
    if (!container) return;
    container.innerHTML = "";
    const ul = document.createElement("ul");
    (items || []).forEach((txt) => {
      const li = document.createElement("li");
      li.textContent = String(txt);
      ul.appendChild(li);
    });
    container.appendChild(ul);
  }
  function renderRecommendations(container, recos) {
    if (!container) return;
    container.innerHTML = "";
    (recos || []).forEach((r) => {
      const row = document.createElement("div");
      row.className = "reco-item";
      const title = document.createElement("div");
      title.className = "reco-title";
      title.textContent = r.title || "";
      row.appendChild(title);
      if (r.action_text && r.action_url) {
        const a = document.createElement("a");
        a.href = r.action_url;
        a.className = "reco-action";
        a.textContent = r.action_text;
        row.appendChild(a);
      }
      container.appendChild(row);
    });
  }

  // ----- loaders -----
  async function loadSummary() {
    const d = selectedDate();
    const res = await (await authFetch(`/api/workoutplans/summary/?date=${encodeURIComponent(d)}`)).json();
    setTextSafe($("#sum-total-min"),        res?.total_min ?? 0);
    setTextSafe($("#sum-total-tasks"),      res?.tasks_count ?? 0);
    setTextSafe($("#sum-completed-tasks"),  res?.completed_count ?? 0);
    setTextSafe($("#sum-total-kcal"),       res?.calories ?? 0);
  }
  async function loadInsights() {
    const d = selectedDate();
    const res = await api.authFetch(`/api/workoutplans/summary/?date=${encodeURIComponent(d)}`);
    renderBullets($("#insight-bullets"), res?.bullets || []);
  }
  async function loadRecommendations() {
    const d = selectedDate();
    const res = await api.get(`/api/recommendations/?date=${encodeURIComponent(d)}`);
    renderRecommendations($("#recommendations"), res || []);
  }

  async function refreshAll() {
    try {
      await Promise.all([loadSummary(), loadInsights(), loadRecommendations()]);
    } catch (e) {
      console.error(e);
      showToast("요약/인사이트 로딩 실패");
      // 실패 시 숫자 0 리셋
      setTextSafe($("#sum-total-min"), 0);
      setTextSafe($("#sum-total-tasks"), 0);
      setTextSafe($("#sum-completed-tasks"), 0);
      setTextSafe($("#sum-total-kcal"), 0);
      renderBullets($("#insight-bullets"), []);
      renderRecommendations($("#recommendations"), []);
    }
  }

  // 이벤트 연결: 기존 B1~B3와 공존
  document.addEventListener("DOMContentLoaded", refreshAll);
  document.addEventListener("plan:updated", refreshAll);
  document.addEventListener("week:navigate", (ev) => {
    const d = ev?.detail?.date;
    if (typeof d === "string" && d.length === 10) {
      const el = $("#selected-date");
      if (el) el.value = d;
      refreshAll();
    }
  });
  const dateInput = $("#selected-date");
  if (dateInput) dateInput.addEventListener("change", refreshAll);

  // 외부에서 수동 갱신 가능
  window.DashboardSummary = { refreshAll };
})();
