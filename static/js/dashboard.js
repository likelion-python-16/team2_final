(function () {
  const ringElements = document.querySelectorAll('.progress-ring');
  ringElements.forEach((ring) => {
    const progress = Number(ring.dataset.progress || '0');
    const circle = ring.querySelector('.progress-ring__value-circle');
    if (!circle) return;
    const circumference = 2 * Math.PI * 54;
    circle.style.strokeDasharray = `${circumference}`;
    const offset = circumference - (Math.min(progress, 100) / 100) * circumference;
    circle.style.strokeDashoffset = offset;
    const colorMap = {
      primary: '#08d1ff',
      secondary: '#8ede3c',
      coral: '#ff7c7c',
      purple: '#a855f7',
    };
    const color = ring.dataset.color && colorMap[ring.dataset.color] ? colorMap[ring.dataset.color] : colorMap.primary;
    circle.style.setProperty('stroke', color);
    ring.style.setProperty('--ring-color', color);
  });

  const MEAL_FEEDBACK_ICONS = {
    good: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4 10-10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>',
    warning: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a1 1 0 0 0 .86 1.5h18.64a1 1 0 0 0 .86-1.5L13.71 3.86a1 1 0 0 0-1.72 0Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>',
    poor: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a1 1 0 0 0 .86 1.5h18.64a1 1 0 0 0 .86-1.5L13.71 3.86a1 1 0 0 0-1.72 0Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>',
  };

  function createMockFeedback() {
    const insightPool = [
      'Great choice of lean protein and vegetables',
      'Good balance of macronutrients',
      'Rich in vitamins and minerals',
      'Nicely portioned for your current goals',
      'Plenty of fibre to support digestion',
      'Consider adding a complex carb for long-lasting energy',
      'Watch sodium content for tomorrow\'s plan',
    ];

    const score = Math.random() > 0.3 ? 'good' : Math.random() > 0.5 ? 'warning' : 'poor';
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

  document.querySelectorAll('[data-meal-analyzer]').forEach((widget) => {
    const dropzone = widget.querySelector('[data-meal-dropzone]');
    const input = widget.querySelector('[data-meal-input]');
    const previewImage = widget.querySelector('[data-meal-preview]');
    const resetBtn = widget.querySelector('[data-meal-reset]');
    const overlay = widget.querySelector('[data-meal-overlay]');
    const feedback = widget.querySelector('[data-meal-feedback]');
    const feedbackIcon = widget.querySelector('[data-meal-feedback-icon]');
    const insightList = widget.querySelector('[data-meal-insights]');
    const caloriesEl = widget.querySelector('[data-meal-calories]');
    const proteinEl = widget.querySelector('[data-meal-protein]');
    const carbsEl = widget.querySelector('[data-meal-carbs]');
    const fatEl = widget.querySelector('[data-meal-fat]');
    if (!dropzone || !input || !previewImage || !resetBtn || !overlay || !feedback) return;

    let analyzeTimeout = 0;

    function setStage(stage) {
      widget.dataset.mealStage = stage;
    }

    function setDragState(isActive) {
      dropzone.classList.toggle('dragover', Boolean(isActive));
    }

    function clearFeedback() {
      feedback.hidden = true;
      feedback.classList.remove('meal-analyzer__feedback--good', 'meal-analyzer__feedback--warning', 'meal-analyzer__feedback--poor', 'is-visible');
      insightList.innerHTML = '';
    }

    function showOverlay(isVisible) {
      overlay.hidden = !isVisible;
    }

    function renderFeedback(data) {
      caloriesEl.textContent = String(data.calories);
      proteinEl.textContent = `${data.protein}g`;
      carbsEl.textContent = `${data.carbs}g`;
      fatEl.textContent = `${data.fat}g`;
      insightList.innerHTML = '';
      data.insights.forEach((insight) => {
        const li = document.createElement('li');
        li.textContent = insight;
        insightList.appendChild(li);
      });

      const scoreClass = `meal-analyzer__feedback--${data.score}`;
      feedback.classList.add(scoreClass);
      if (feedbackIcon) {
        feedbackIcon.innerHTML = MEAL_FEEDBACK_ICONS[data.score] || MEAL_FEEDBACK_ICONS.good;
      }
      feedback.hidden = false;
      requestAnimationFrame(() => {
        feedback.classList.add('is-visible');
      });
    }

    function resetWidget() {
      window.clearTimeout(analyzeTimeout);
      analyzeTimeout = 0;
      input.value = '';
      previewImage.src = '';
      setStage('upload');
      showOverlay(false);
      clearFeedback();
    }

    function processFile(file) {
      if (!file || !file.type.startsWith('image/')) return;
      const reader = new FileReader();
      reader.onload = () => {
        previewImage.src = typeof reader.result === 'string' ? reader.result : '';
        setStage('analysis');
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

    dropzone.addEventListener('click', () => {
      input.click();
    });

    dropzone.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        input.click();
      }
    });

    dropzone.addEventListener('dragover', (event) => {
      event.preventDefault();
      setDragState(true);
    });

    dropzone.addEventListener('dragleave', (event) => {
      event.preventDefault();
      setDragState(false);
    });

    dropzone.addEventListener('drop', (event) => {
      event.preventDefault();
      setDragState(false);
      if (!event.dataTransfer) return;
      const [file] = event.dataTransfer.files;
      processFile(file);
    });

    input.addEventListener('change', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement) || !target.files || !target.files[0]) return;
      processFile(target.files[0]);
    });

    resetBtn.addEventListener('click', (event) => {
      event.preventDefault();
      resetWidget();
    });

  });

  const taskList = document.getElementById('dailyTasks');
  const taskAddButton = document.querySelector('[data-task-add]');
  const taskCountLabel = document.querySelector('[data-task-count]');
  const progressCard = document.getElementById('progress');
  const percentLabel = document.getElementById('progressPercent');
  const goalFill = document.getElementById('progressGoalFill');
  const goalLabel = document.getElementById('progressGoalLabel');
  const goalCount = document.getElementById('progressGoalCount');
  const goalTotal = document.getElementById('progressGoalTotal');

  function updateDailyGoalProgress() {
    if (!taskList) return;
    const items = taskList.querySelectorAll('.task-card__item:not(.task-card__item--editing)');
    const total = items.length;
    const completed = Array.from(items).filter((item) => item.classList.contains('is-complete')).length;
    const percent = total ? Math.round((completed / total) * 100) : 0;

    if (percentLabel) percentLabel.textContent = `${percent}%`;
    if (goalFill) goalFill.style.width = `${percent}%`;
    if (goalCount) goalCount.textContent = String(completed);
    if (goalTotal) goalTotal.textContent = String(total);
    if (goalLabel) {
      goalLabel.setAttribute('data-completed', String(completed));
      goalLabel.setAttribute('data-total', String(total));
    }
    if (progressCard) {
      progressCard.dataset.progressTotal = String(total);
      progressCard.dataset.progressComplete = String(completed);
    }
    if (taskCountLabel) taskCountLabel.textContent = `오늘 목표 ${total}개`;
  }

  function handleTaskToggle(event) {
    const checkbox = event.target.closest && event.target.closest('[data-task-checkbox]');
    if (!checkbox) return;
    const item = checkbox.closest('.task-card__item');
    if (!item) return;
    const text = item.querySelector('.task-card__text');
    const indicator = item.querySelector('.task-card__checkbox');
    const isComplete = checkbox.checked;
    item.classList.toggle('is-complete', isComplete);
    item.dataset.completed = isComplete ? 'true' : 'false';
    if (text) text.classList.toggle('is-complete', isComplete);
    if (indicator) indicator.dataset.state = isComplete ? 'checked' : 'unchecked';
    updateDailyGoalProgress();
  }

  if (taskList) {
    taskList.addEventListener('change', handleTaskToggle);
    const observer = new MutationObserver(() => {
      updateDailyGoalProgress();
    });
    observer.observe(taskList, { childList: true });
    updateDailyGoalProgress();
  }

  function createTaskElement(text) {
    const li = document.createElement('li');
    li.className = 'task-card__item';
    li.dataset.taskType = 'custom';
    li.dataset.completed = 'false';

    li.innerHTML = `
      <label class="task-card__toggle">
        <input type="checkbox" class="task-card__input" data-task-checkbox>
        <span class="task-card__checkbox" data-state="unchecked" aria-hidden="true">
          <svg viewBox="0 0 24 24" focusable="false">
            <path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="3"></path>
          </svg>
        </span>
        <span class="task-card__text">${text}</span>
        <span class="task-card__dot task-card__dot--custom" aria-hidden="true"></span>
      </label>
    `;

    return li;
  }

  function insertTaskEditor() {
    if (!taskList) return;
    const existingEditor = taskList.querySelector('.task-card__item--editing');
    if (existingEditor) {
      const existingInput = existingEditor.querySelector('.task-card__input-field');
      if (existingInput) existingInput.focus();
      return;
    }

    const li = document.createElement('li');
    li.className = 'task-card__item task-card__item--editing';
    li.innerHTML = `
      <div class="task-card__editor">
        <input type="text" class="task-card__input-field" placeholder="할 일을 입력하세요" maxlength="120" />
        <button type="button" class="task-card__confirm">추가</button>
        <button type="button" class="task-card__cancel" aria-label="취소">취소</button>
      </div>
    `;

    taskList.appendChild(li);

    const input = li.querySelector('.task-card__input-field');
    const confirmBtn = li.querySelector('.task-card__confirm');
    const cancelBtn = li.querySelector('.task-card__cancel');

    if (input) input.focus();

    const removeEditor = () => {
      if (li.isConnected) li.remove();
      updateDailyGoalProgress();
    };

    const commitEditor = () => {
      if (!input) return;
      const value = input.value.trim();
      if (!value) {
        removeEditor();
        return;
      }
      const newTask = createTaskElement(value);
      li.replaceWith(newTask);
      updateDailyGoalProgress();
    };

    if (input) {
      input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          commitEditor();
        } else if (event.key === 'Escape') {
          event.preventDefault();
          removeEditor();
        }
      });

      input.addEventListener('blur', () => {
        window.setTimeout(() => {
          if (!document.contains(li)) return;
          const active = document.activeElement;
          if (active === confirmBtn || active === cancelBtn || active === input) return;
          if (!input.value.trim()) {
            removeEditor();
          }
        }, 120);
      });
    }

    if (confirmBtn) {
      confirmBtn.addEventListener('click', (event) => {
        event.preventDefault();
        commitEditor();
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', (event) => {
        event.preventDefault();
        removeEditor();
      });
    }
  }

  if (taskAddButton && taskList) {
    taskAddButton.addEventListener('click', () => {
      insertTaskEditor();
    });
  }
})();
