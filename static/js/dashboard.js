// static/js/dashboard.js
(function () {
  // ========= 공통 유틸 =========
  const API = window.API || "/api";
  const getAuthHeaders = () =>
    typeof window.authHeaders === "function"
      ? window.authHeaders()
      : { "Content-Type": "application/json" };

  const toISODate = (d) => {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  };

  const TODAY_ISO = toISODate(new Date());

  // ========= 진행원형 링 초기화/업데이트 =========
  function initProgressRings(context = document) {
    const ringElements = context.querySelectorAll(".progress-ring");
    ringElements.forEach((ring) => applyRingFromDataset(ring));
  }

  function applyRingFromDataset(ring) {
    const progress = Number(ring.dataset.progress || "0");
    setRingProgress(ring, progress);

    const colorMap = {
      primary: "#08d1ff",
      secondary: "#8ede3c",
      coral: "#ff7c7c",
      purple: "#a855f7",
    };
    const color =
      (ring.dataset.color && colorMap[ring.dataset.color]) || colorMap.primary;
    const circle = ring.querySelector(".progress-ring__value-circle");
    if (circle) {
      circle.style.setProperty("stroke", color);
    }
    ring.style.setProperty("--ring-color", color);
  }

  function setRingProgress(ring, percent) {
    const circle = ring.querySelector(".progress-ring__value-circle");
    if (!circle) return;
    const circumference = 2 * Math.PI * 54; // r=54 기반(템플릿과 동일)
    circle.style.strokeDasharray = `${circumference}`;
    const offset =
      circumference - (Math.min(percent, 100) / 100) * circumference;
    circle.style.strokeDashoffset = offset;
    ring.dataset.progress = String(Math.max(0, Math.min(100, percent)));
  }

  function updateMainProgress(percent) {
    // 진행률 숫자/바/링 모두 갱신
    const percentLabel = document.getElementById("progressPercent");
    const goalFill = document.getElementById("progressGoalFill");
    if (percentLabel) percentLabel.textContent = `${percent}%`;
    if (goalFill) goalFill.style.width = `${percent}%`;

    // 카드 내부 링(있다면) 업데이트
    const progressCard = document.getElementById("progress");
    if (!progressCard) return;
    const ring = progressCard.querySelector(".progress-ring");
    if (ring) setRingProgress(ring, percent);
  }

  // ========= Daily Tasks DOM 참조 =========
  const taskList = document.getElementById("dailyTasks");
  const taskAddButton = document.querySelector("[data-task-add]");
  const taskCountLabel = document.querySelector("[data-task-count]");
  const progressCard = document.getElementById("progress");
  const goalCount = document.getElementById("progressGoalCount");
  const goalTotal = document.getElementById("progressGoalTotal");

  // ========= Daily Tasks 렌더/진행률 갱신 =========
  function createTaskElement(text, completed = false, type = "workout") {
    const li = document.createElement("li");
    li.className = `task-card__item${completed ? " is-complete" : ""}`;
    li.dataset.taskType = type;
    li.dataset.completed = completed ? "true" : "false";

    li.innerHTML = `
      <label class="task-card__toggle">
        <input type="checkbox" class="task-card__input" data-task-checkbox ${
          completed ? "checked" : ""
        }>
        <span class="task-card__checkbox" data-state="${
          completed ? "checked" : "unchecked"
        }" aria-hidden="true">
          <svg viewBox="0 0 24 24" focusable="false">
            <path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="3"></path>
          </svg>
        </span>
        <span class="task-card__text${completed ? " is-complete" : ""}">${text}</span>
        <span class="task-card__dot task-card__dot--${type}" aria-hidden="true"></span>
      </label>
    `;
    return li;
  }

  function updateDailyGoalProgress() {
    if (!taskList) return;
    const items = taskList.querySelectorAll(
      ".task-card__item:not(.task-card__item--editing)"
    );
    const total = items.length;
    const completed = Array.from(items).filter((item) =>
      item.classList.contains("is-complete")
    ).length;
    const percent = total ? Math.round((completed / total) * 100) : 0;

    if (goalCount) goalCount.textContent = String(completed);
    if (goalTotal) goalTotal.textContent = String(total);
    if (taskCountLabel) taskCountLabel.textContent = `오늘 목표 ${total}개`;

    // 카드 데이터 속성도 갱신(필요 시 파생위젯 참고)
    if (progressCard) {
      progressCard.dataset.progressTotal = String(total);
      progressCard.dataset.progressComplete = String(completed);
    }

    updateMainProgress(percent);
  }

  function handleTaskToggle(event) {
    const checkbox =
      event.target.closest && event.target.closest("[data-task-checkbox]");
    if (!checkbox) return;
    const item = checkbox.closest(".task-card__item");
    if (!item) return;
    const text = item.querySelector(".task-card__text");
    const indicator = item.querySelector(".task-card__checkbox");
    const isComplete = checkbox.checked;
    item.classList.toggle("is-complete", isComplete);
    item.dataset.completed = isComplete ? "true" : "false";
    if (text) text.classList.toggle("is-complete", isComplete);
    if (indicator) indicator.dataset.state = isComplete ? "checked" : "unchecked";
    updateDailyGoalProgress();
  }

  // ========= 서버에서 오늘 플랜 → Tasks 로드 후 렌더 =========
  async function fetchTodayPlanDetail() {
    try {
      // 1) 오늘 날짜 기준 첫 플랜 찾기
      const r = await fetch(
        `${API}/workoutplans/by-date/?date=${encodeURIComponent(TODAY_ISO)}`,
        { headers: getAuthHeaders() }
      );
      const data = await r.json().catch(() => []);
      const plans = Array.isArray(data)
        ? data
        : Array.isArray(data?.results)
        ? data.results
        : [];
      if (!r.ok || !plans.length) return null;

      // 2) 상세(Tasks 포함) 가져오기
      const plan = plans[0];
      const r2 = await fetch(`${API}/workoutplans/${plan.id}/`, {
        headers: getAuthHeaders(),
      });
      if (!r2.ok) return null;
      const detail = await r2.json();
      return detail;
    } catch (e) {
      console.warn("fetchTodayPlanDetail failed", e);
      return null;
    }
  }

  function renderDailyTasksFromPlan(planDetail) {
    if (!taskList) return;
    const tasks = Array.isArray(planDetail?.tasks) ? planDetail.tasks : [];

    // 리스트 재구성
    taskList.innerHTML = tasks
      .map((t) => {
        const label = [
          t.exercise_detail?.name || t.exercise_name || "(exercise)",
          t.target_sets && t.target_reps ? `${t.target_sets}x${t.target_reps}` : "",
          t.duration_min ? `${t.duration_min}m` : "",
        ]
          .filter(Boolean)
          .join(" · ");

        // 항목 DOM
        const li = document.createElement("li");
        li.className = "task-card__item";
        li.dataset.taskType = "workout";
        li.dataset.completed = "false";
        li.innerHTML = `
          <label class="task-card__toggle">
            <input type="checkbox" class="task-card__input" data-task-checkbox>
            <span class="task-card__checkbox" data-state="unchecked" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="3"></path>
              </svg>
            </span>
            <span class="task-card__text">${label}</span>
            <span class="task-card__dot task-card__dot--workout" aria-hidden="true"></span>
          </label>
        `;
        return li.outerHTML;
      })
      .join("");

    updateDailyGoalProgress();
  }

  async function refreshDashboardFromServer({ silent = true } = {}) {
    const detail = await fetchTodayPlanDetail();
    if (!detail) {
      if (!silent && taskList) {
        taskList.innerHTML = `<li class="muted">오늘 생성된 플랜이 없습니다.</li>`;
      }
      updateDailyGoalProgress(); // 0개 기준
      return;
    }
    renderDailyTasksFromPlan(detail);
  }

  // 외부(예: workouts 페이지)에서 호출 가능하도록 노출
  window.refreshDashboardFromServer = refreshDashboardFromServer;

  // ========= “Task 추가” 인라인 에디터(기존 기능 유지) =========
  function insertTaskEditor() {
    if (!taskList) return;
    const existingEditor = taskList.querySelector(".task-card__item--editing");
    if (existingEditor) {
      const existingInput = existingEditor.querySelector(".task-card__input-field");
      if (existingInput) existingInput.focus();
      return;
    }

    const li = document.createElement("li");
    li.className = "task-card__item task-card__item--editing";
    li.innerHTML = `
      <div class="task-card__editor">
        <input type="text" class="task-card__input-field" placeholder="할 일을 입력하세요" maxlength="120" />
        <button type="button" class="task-card__confirm">추가</button>
        <button type="button" class="task-card__cancel" aria-label="취소">취소</button>
      </div>
    `;
    taskList.appendChild(li);

    const input = li.querySelector(".task-card__input-field");
    const confirmBtn = li.querySelector(".task-card__confirm");
    const cancelBtn = li.querySelector(".task-card__cancel");
    if (input) input.focus();

    const removeEditor = () => {
      if (li.isConnected) li.remove();
      updateDailyGoalProgress();
    };

    const commitEditor = () => {
      if (!input) return;
      const value = input.value.trim();
      if (!value) return removeEditor();
      const newTask = createTaskElement(value, false, "custom");
      li.replaceWith(newTask);
      updateDailyGoalProgress();
    };

    input?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        commitEditor();
      } else if (event.key === "Escape") {
        event.preventDefault();
        removeEditor();
      }
    });

    input?.addEventListener("blur", () => {
      window.setTimeout(() => {
        if (!document.contains(li)) return;
        const active = document.activeElement;
        if (active === confirmBtn || active === cancelBtn || active === input) return;
        if (!input.value.trim()) removeEditor();
      }, 120);
    });

    confirmBtn?.addEventListener("click", (e) => {
      e.preventDefault();
      commitEditor();
    });
    cancelBtn?.addEventListener("click", (e) => {
      e.preventDefault();
      removeEditor();
    });
  }

  // ========= 이벤트 바인딩/초기화 =========
  if (taskList) {
    // 토글 이벤트 위임
    taskList.addEventListener("change", handleTaskToggle);

    // DOM 변동 시(수동 추가 등) 진행률 재계산
    const observer = new MutationObserver(() => updateDailyGoalProgress());
    observer.observe(taskList, { childList: true });
  }

  if (taskAddButton && taskList) {
    taskAddButton.addEventListener("click", () => insertTaskEditor());
  }

  // 페이지 최초 로드 시 서버 데이터 반영
  initProgressRings(document);
  refreshDashboardFromServer({ silent: true });

  // ========= 교차-페이지 동기화(선택) =========
  // workouts 페이지에서 완료 후:
  //  - window.dispatchEvent(new CustomEvent('plan:updated'))
  //  - 또는 localStorage.setItem('planUpdatedAt', Date.now())
  //  - 또는 BroadcastChannel('plan_updates').postMessage('updated')
  window.addEventListener("plan:updated", () =>
    refreshDashboardFromServer({ silent: false })
  );

  try {
    const bc = "BroadcastChannel" in window ? new BroadcastChannel("plan_updates") : null;
    bc?.addEventListener("message", (msg) => {
      if (msg?.data === "updated") refreshDashboardFromServer({ silent: false });
    });
  } catch {}

  window.addEventListener("storage", (e) => {
    if (e.key === "planUpdatedAt") {
      refreshDashboardFromServer({ silent: false });
    }
  });

  // ========= (옵션) 식단 업로더 위젯: 기존 기능 유지 =========
  // 아래는 기존 UI 보존용. 위젯이 없으면 그냥 무시됨.
  (function initMealAnalyzer() {
    const MEAL_FEEDBACK_ICONS = {
      good: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4 10-10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>',
      warning:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a1 1 0 0 0 .86 1.5h18.64a1 1 0 0 0 .86-1.5L13.71 3.86a1 1 0 0 0-1.72 0Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>',
      poor:
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a1 1 0 0 0 .86 1.5h18.64a1 1 0 0 0 .86-1.5L13.71 3.86a1 1 0 0 0-1.72 0Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>',
    };

    function createMockFeedback() {
      const insightPool = [
        "Great choice of lean protein and vegetables",
        "Good balance of macronutrients",
        "Rich in vitamins and minerals",
        "Nicely portioned for your current goals",
        "Plenty of fibre to support digestion",
        "Consider adding a complex carb for long-lasting energy",
        "Watch sodium content for tomorrow's plan",
      ];
      const score =
        Math.random() > 0.3 ? "good" : Math.random() > 0.5 ? "warning" : "poor";
      const calories = Math.floor(Math.random() * 400) + 200;
      const protein = Math.floor(Math.random() * 30) + 10;
      const carbs = Math.floor(Math.random() * 50) + 20;
      const fat = Math.floor(Math.random() * 20) + 5;
      const shuffled = insightPool.slice().sort(() => 0.5 - Math.random());
      return {
        score,
        calories,
        protein,
        carbs,
        fat,
        insights: shuffled.slice(0, 3),
      };
    }

    document.querySelectorAll("[data-meal-analyzer]").forEach((widget) => {
      const dropzone = widget.querySelector("[data-meal-dropzone]");
      const input = widget.querySelector("[data-meal-input]");
      const previewImage = widget.querySelector("[data-meal-preview]");
      const resetBtn = widget.querySelector("[data-meal-reset]");
      const overlay = widget.querySelector("[data-meal-overlay]");
      const feedback = widget.querySelector("[data-meal-feedback]");
      const feedbackIcon = widget.querySelector("[data-meal-feedback-icon]");
      const insightList = widget.querySelector("[data-meal-insights]");
      const caloriesEl = widget.querySelector("[data-meal-calories]");
      const proteinEl = widget.querySelector("[data-meal-protein]");
      const carbsEl = widget.querySelector("[data-meal-carbs]");
      const fatEl = widget.querySelector("[data-meal-fat]");
      if (!dropzone || !input || !previewImage || !resetBtn || !overlay || !feedback) return;

      let analyzeTimeout = 0;

      function setStage(stage) {
        widget.dataset.mealStage = stage;
      }
      function setDragState(isActive) {
        dropzone.classList.toggle("dragover", Boolean(isActive));
      }
      function clearFeedback() {
        feedback.hidden = true;
        feedback.classList.remove(
          "meal-analyzer__feedback--good",
          "meal-analyzer__feedback--warning",
          "meal-analyzer__feedback--poor",
          "is-visible"
        );
        insightList && (insightList.innerHTML = "");
      }
      function showOverlay(isVisible) {
        overlay.hidden = !isVisible;
      }
      function renderFeedback(data) {
        if (caloriesEl) caloriesEl.textContent = String(data.calories);
        if (proteinEl) proteinEl.textContent = `${data.protein}g`;
        if (carbsEl) carbsEl.textContent = `${data.carbs}g`;
        if (fatEl) fatEl.textContent = `${data.fat}g`;
        if (insightList) {
          insightList.innerHTML = "";
          data.insights.forEach((insight) => {
            const li = document.createElement("li");
            li.textContent = insight;
            insightList.appendChild(li);
          });
        }
        const scoreClass = `meal-analyzer__feedback--${data.score}`;
        feedback.classList.add(scoreClass);
        if (feedbackIcon) {
          feedbackIcon.innerHTML =
            MEAL_FEEDBACK_ICONS[data.score] || MEAL_FEEDBACK_ICONS.good;
        }
        feedback.hidden = false;
        requestAnimationFrame(() => feedback.classList.add("is-visible"));
      }
      function resetWidget() {
        window.clearTimeout(analyzeTimeout);
        analyzeTimeout = 0;
        input.value = "";
        previewImage.src = "";
        setStage("upload");
        showOverlay(false);
        clearFeedback();
      }
      function processFile(file) {
        if (!file || !file.type.startsWith("image/")) return;
        const reader = new FileReader();
        reader.onload = () => {
          previewImage.src = typeof reader.result === "string" ? reader.result : "";
          setStage("analysis");
          clearFeedback();
          showOverlay(true);
          analyzeTimeout = window.setTimeout(() => {
            const data = createMockFeedback();
            showOverlay(false);
            renderFeedback(data);
          }, 2500);
        };
        reader.readAsDataURL(file);
      }

      dropzone.addEventListener("click", () => input.click());
      dropzone.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          input.click();
        }
      });
      dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        setDragState(true);
      });
      dropzone.addEventListener("dragleave", (e) => {
        e.preventDefault();
        setDragState(false);
      });
      dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        setDragState(false);
        if (!e.dataTransfer) return;
        const [file] = e.dataTransfer.files;
        processFile(file);
      });
      input.addEventListener("change", (e) => {
        const target = e.target;
        if (!(target instanceof HTMLInputElement) || !target.files || !target.files[0]) return;
        processFile(target.files[0]);
      });
      resetBtn.addEventListener("click", (e) => {
        e.preventDefault();
        resetWidget();
      });
    });
  })();
})();
