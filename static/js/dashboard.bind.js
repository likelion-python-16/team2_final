// static/js/dashboard.bind.js
// Requires: A1(api.js), A2(ui.js), A3(date.js)
// Scope: Dashboard B1~B3 + 접기/펼치기 + 유형별 아코디언 + (추가) DOM 중복 제거
// 원칙: 템플릿/스타일 삭제 없이 "추가만"으로 동작

(function () {
  "use strict";

  // ─────────────────────────────────────────────────────────────
  // A1 Fallback 래퍼 (api.get/patch 미정의 시 대비)
  // ─────────────────────────────────────────────────────────────
  const api = (function ensureApi() {
    if (window.api && typeof window.api.get === "function" && typeof window.api.patch === "function") {
      return window.api;
    }
    const headers = () => (window.authHeaders ? window.authHeaders() : { "Content-Type": "application/json" });
    const fetchJson = async (url, opts = {}) => {
      const res = await fetch(url, { credentials: "same-origin", headers: headers(), ...opts });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const err = new Error(data?.detail || `HTTP ${res.status}`);
        err.status = res.status;
        err.data = data;
        throw err;
      }
      return data;
    };
    return {
      get: (url) => fetchJson(url),
      patch: (url, body) => fetchJson(url, { method: "PATCH", body: JSON.stringify(body || {}) }),
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
      if (!plans || !plans.length) {
        console.info("[B1] 오늘 플랜 없음:", today);
        return null;
      }
      const planId = plans[0].id;
      const plan = await api.get(`/api/workoutplans/${planId}/`);
      console.info("[B1] 오늘 플랜:", plan);
      return plan;
    } catch (err) {
      if (!ui.handleAuthError?.(err)) {
        ui.toastError?.("오늘 플랜을 불러오지 못했습니다.");
        console.error("[B1] loadTodayPlan error:", err);
      }
      return null;
    }
  }
  window.loadTodayPlan = loadTodayPlan;

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
      if (!plan) return; // 플랜 없으면 기존 문구 유지
      setPlanTitleFrom(plan);
    } catch {
      ui.toastError?.("제목을 불러오지 못했습니다.");
    }
  }

  // ─────────────────────────────────────────────────────────────
  // B3: 진행도/링/체크리스트
  // ─────────────────────────────────────────────────────────────
  async function loadTasksForPlan(planId) {
    try {
      const qs = `/api/taskitems/?workout_plan=${encodeURIComponent(planId)}`;
      const resp = await api.get(qs);
      return Array.isArray(resp) ? resp : (Array.isArray(resp?.results) ? resp.results : []);
    } catch (err) {
      if (!ui.handleAuthError?.(err)) ui.toastError?.("작업 목록을 불러오지 못했습니다.");
      return [];
    }
  }

  // 서버 렌더된 Daily Tasks 읽기(있으면 우선 사용)
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

  // 진행도/링 갱신 (Daily 우선 → 없으면 Workout)
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

    // 0/n 카운트
    document.querySelectorAll("[data-progress-count]").forEach((el) => {
      el.textContent = `${done}/${total}`;
    });
    // 원 중앙 텍스트 덮어쓰기
    document.querySelectorAll(".progress-ring__value-text").forEach((el) => {
      el.textContent = `${done}/${total}`;
    });
    // % 텍스트
    const pct = total ? Math.round((done / total) * 100) : 0;
    document.querySelectorAll("[data-progress-percent]").forEach((el) => {
      el.textContent = `${pct}%`;
    });
    // A11y: 진행도 상태를 보조기기에 알려주기 (첫 번째 진행도 영역 기준)
    const region = document.querySelector("[data-progress-count]");
    if (region) {
      region.setAttribute("role", "status");
      region.setAttribute("aria-live", "polite");
      region.setAttribute("aria-label", `오늘 진행도 ${done}개 완료, 총 ${total}개, ${pct}%`);
}
    // 링 스트로크
    const ring = document.querySelector(".progress-ring__value-circle");
    if (ring) {
      const R = Number(ring.getAttribute("r") || 54);
      const C = 2 * Math.PI * R;
      ring.style.strokeDasharray = `${C}`;
      ring.style.strokeDashoffset = String(C - (pct / 100) * C);
    }
    // 상태 배지
    document.querySelectorAll("[data-workout-status]").forEach((el) => {
      let txt = "Not Started";
      if (total > 0 && done === total) txt = "Completed";
      else if (done > 0) txt = "In Progress";
      el.textContent = txt;
      // (선택) 클래스 토글은 CSS 유틸이 있을 때:
      el.classList.remove("badge-started", "badge-completed");
      if (txt === "In Progress") el.classList.add("badge-started");
      if (txt === "Completed") el.classList.add("badge-completed");
    });
    // 게이지 바
    const fill = document.getElementById("progressGoalFill");
    if (fill) fill.style.width = `${pct}%`;
  }

  // 체크리스트 렌더(+ 접기)
  function renderTasks(tasks, planId) {
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
      const name = t?.exercise_name || t?.exercise || "Task";
      const done = !!t?.completed;
      li.innerHTML = `
        <label class="task-check" style="display:flex;gap:8px;align-items:center;">
          <input type="checkbox" ${done ? "checked" : ""} data-task-id="${t.id}" aria-label="Complete Task"/>
          <span>${name}</span>
        </label>
      `;
      frag.appendChild(li);
    }
    list.appendChild(frag);

    // 저장 이벤트(위임) — once 제거 (여러 번 토글 가능)
    if (!list.__boundToggle) {
      list.addEventListener("change", async (e) => {
        const cb = e.target;
        if (!(cb instanceof HTMLInputElement)) return;
        const taskId = cb.dataset.taskId;
        if (!taskId) return;

        const prev = !cb.checked;
        try {
          await api.patch(`/api/taskitems/${taskId}/`, { completed: cb.checked });

          // 최신 항목 다시 가져와서 진행도 갱신 + DOM 중복 제거
          const fresh = await loadTasksForPlan(planId);
          updateProgressUsingDailyOrWorkout(fresh);
          dedupeTaskDomListByName("[data-task-list]");
        } catch (err) {
          cb.checked = prev; // 롤백
          if (!ui.handleAuthError?.(err)) ui.toastError?.("저장에 실패했습니다. 다시 시도해 주세요.");
        }
      });
      list.__boundToggle = true; // 중복 바인딩 방지 플래그
    }

    // 초기 진행도 반영 + 접기(3개 기준) + DOM 중복 제거
    updateProgressUsingDailyOrWorkout(tasks);
    applyCollapsible(list, 3);
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

    // 초기: 접힘
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
  // Workout Tasks 아코디언
  // ─────────────────────────────────────────────────────────────
  function getTypeKey(t) {
    return (
      t?.muscle_group ||
      t?.body_part ||
      t?.type ||
      t?.category ||
      t?.exercise_group ||
      "기타"
    );
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

      // 정렬: order → id
      items.sort((a, b) => {
        const ao = (a?.order ?? 1e9), bo = (b?.order ?? 1e9);
        if (ao !== bo) return ao - bo;
        return (a?.id || 0) - (b?.id || 0);
      });

      for (const t of items) {
        const li = document.createElement("li");
        li.className = "accordion__item";
        li.setAttribute("data-task-item", "");
        const nameText = t?.exercise_name || t?.exercise || "Task";
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

      // 섹션 내 토글 저장(위임)
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

            // 상단 진행도도 동기화 (서버 기준 재조회 생략: DOM 기반 재계산)
            dedupeTaskDomListByName("[data-task-list]"); // 메인 리스트 있을 때 동기화
            updateProgressUsingDailyOrWorkout(null);
          } catch (err) {
            cb.checked = prev;
            if (!ui.handleAuthError?.(err)) ui.toastError?.("저장에 실패했습니다.");
          }
        });
        ul.__boundToggle = true;
      }

      // 섹션도 접기 기본 적용(3개만 보이게)
      applyCollapsible(ul, 3);
    }
  }

  // ─────────────────────────────────────────────────────────────
  // (추가) DOM 안에서 "이름 중복" 제거 + 진행도 재계산
  // ─────────────────────────────────────────────────────────────
  function normalizeNameKey(raw) {
    return String(raw || "")
      .toLowerCase()
      .replace(/\(.*?\)/g, "")        // 괄호 설명 제거
      .replace(/[^a-z0-9가-힣\s]/g, " ") // 특수문자 슬림화
      .replace(/\s+/g, " ")           // 공백 정리
      .trim();
  }

  function normalizeNameKey(raw) {
    return String(raw || "")
      .toLowerCase()
      .replace(/\(.*?\)/g, "")        // 괄호 설명 제거
      .replace(/[^a-z0-9가-힣\s]/g, " ") // 특수문자 슬림화
      .replace(/\s+/g, " ")           // 공백 정리
      .trim();
  }

  function dedupeTaskDomListByName(containerSelector = "[data-task-list]") {
    const list = document.querySelector(containerSelector);
    if (!list) return;

    const seen = new Set();

    // ✅ 오타 수정: 잘못된 ']' 제거 + 단일 쿼리
    const items = Array.from(list.querySelectorAll("li[data-task-item], li.task-row"));

    for (const li of items) {
      const nameEl = li.querySelector("label span");
      const key = normalizeNameKey(nameEl ? nameEl.textContent : "");
      if (seen.has(key)) {
        li.remove(); // 화면에서만 제거
      } else {
        seen.add(key);
      }
    }

    // DOM 기준 진행도 재계산
    const remaining = Array.from(list.querySelectorAll("li[data-task-item], li.task-row"));
    const total = remaining.length;
    const done = remaining.filter((li) => {
      const cb = li.querySelector('input[type="checkbox"]');
      return cb && cb.checked;
    }).length;

    // 0/n, 중앙 텍스트
    document.querySelectorAll("[data-progress-count]").forEach((el) => { el.textContent = `${done}/${total}`; });
    document.querySelectorAll(".progress-ring__value-text").forEach((el) => { el.textContent = `${done}/${total}`; });

    // % + 링
    const pct = total ? Math.round((done / total) * 100) : 0;
    document.querySelectorAll("[data-progress-percent]").forEach((el) => { el.textContent = `${pct}%`; });
    const ring = document.querySelector(".progress-ring__value-circle");
    if (ring) {
      const R = Number(ring.getAttribute("r") || 54);
      const C = 2 * Math.PI * R;
      ring.style.strokeDasharray = `${C}`;
      ring.style.strokeDashoffset = String(C - (pct / 100) * C);
    }

    // 상태 배지
    document.querySelectorAll("[data-workout-status]").forEach((el) => {
      let txt = "Not Started";
      if (total > 0 && done === total) txt = "Completed";
      else if (done > 0) txt = "In Progress";
      el.textContent = txt;
    });

    // 더 보기/접기 버튼 텍스트 재세팅
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
  // 파이프라인
  // ─────────────────────────────────────────────────────────────
  async function loadTodayPlanAndTasks() {
    const plan = await loadTodayPlan();
    const list = document.querySelector("[data-task-list]");
    if (!plan) {
      updateProgressUsingDailyOrWorkout([]); // Daily 없으면 0/0 처리
      if (list) list.innerHTML = "";
      return;
    }
    setPlanTitleFrom(plan); // B2: 제목
    const tasks = await loadTasksForPlan(plan.id);
    renderTasks(tasks, plan.id);                 // 기본 리스트
    renderTasksAccordion(tasks, plan.id);        // 유형별 아코디언 추가 렌더
    updateProgressUsingDailyOrWorkout(tasks);    // 진행도 갱신
  }
  window.loadTodayPlanAndTasks = loadTodayPlanAndTasks;

  // ─────────────────────────────────────────────────────────────
  // 초기 바인딩
  // ─────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    // B1 확인 호출(로그/배너용)
    loadTodayPlan();
    // B2 제목 주입
    injectTodayTitle();
    // B3 + 아코디언 파이프라인
    loadTodayPlanAndTasks();

    // Daily Tasks 체크 변경 시에도 진행도 갱신
    const dailyList = document.getElementById("dailyTasks");
    if (dailyList && !dailyList.__boundChange) {
      dailyList.addEventListener("change", () => {
        // Daily 우선 정책 유지: DOM 기준 즉시 재계산
        updateProgressUsingDailyOrWorkout(null);
      });
      dailyList.__boundChange = true;
    }
  });
})();
