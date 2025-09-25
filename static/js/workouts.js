(function () {
  const headers = document.querySelectorAll('.workout-card__header');
  if (!headers.length) return;

  const completedMarkup = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12 10 17 19 7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>Completed';

  const startMarkup = '<span>▶</span>Start Workout';

  function createCompletedLabel() {
    const span = document.createElement('span');
    span.className = 'workout-status workout-status--done';
    span.innerHTML = completedMarkup;
    return span;
  }

  function createStartButton() {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'workout-start';
    button.innerHTML = startMarkup;
    return button;
  }

  function switchToCompleted(startButton) {
    const header = startButton.closest('.workout-card__header');
    if (!header) return;
    const completedLabel = createCompletedLabel();
    startButton.replaceWith(completedLabel);
    bindCompleted(completedLabel);
  }

  function switchToStart(completedLabel) {
    const header = completedLabel.closest('.workout-card__header');
    if (!header) return;
    const startButton = createStartButton();
    completedLabel.replaceWith(startButton);
    bindStart(startButton);
  }

  function bindStart(button) {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      switchToCompleted(button);
    });
  }

  function bindCompleted(label) {
    label.addEventListener('click', () => {
      switchToStart(label);
    });
  }

  headers.forEach((header) => {
    const start = header.querySelector('.workout-start');
    const completed = header.querySelector('.workout-status--done');

    if (start) {
      const startButton = createStartButton();
      start.replaceWith(startButton);
      bindStart(startButton);
    } else if (completed) {
      const completedLabel = createCompletedLabel();
      completed.replaceWith(completedLabel);
      bindCompleted(completedLabel);
    }
  });
})();
