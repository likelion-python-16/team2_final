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
  const progressCard = document.getElementById('progress');
  const percentLabel = document.getElementById('progressPercent');
  const goalFill = document.getElementById('progressGoalFill');
  const goalCount = document.getElementById('progressGoalCount');

  function updateDailyGoalProgress() {
    if (!taskList) return;
    const items = taskList.querySelectorAll('.task-list__item');
    const total = items.length;
    const completed = Array.from(items).filter((item) => item.classList.contains('is-complete')).length;
    const percent = total ? Math.round((completed / total) * 100) : 0;

    if (percentLabel) percentLabel.textContent = `${percent}%`;
    if (goalFill) goalFill.style.width = `${percent}%`;
    if (goalCount) goalCount.textContent = completed;
    if (progressCard) {
      progressCard.dataset.progressTotal = String(total);
      progressCard.dataset.progressComplete = String(completed);
    }
  }

  if (taskList) {
    taskList.addEventListener('change', (event) => {
      const checkbox = event.target.closest('[data-task-checkbox]');
      if (!checkbox) return;
      const item = checkbox.closest('.task-list__item');
      if (!item) return;
      const text = item.querySelector('.task-list__text');
      const indicator = item.querySelector('.task-checkbox');
      const isComplete = checkbox.checked;
      item.classList.toggle('is-complete', isComplete);
      item.dataset.completed = isComplete ? 'true' : 'false';
      if (text) text.classList.toggle('is-complete', isComplete);
      if (indicator) indicator.dataset.state = isComplete ? 'checked' : 'unchecked';
      updateDailyGoalProgress();
    });

    updateDailyGoalProgress();
  }
})();
