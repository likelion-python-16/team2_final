(function () {
  const calendar = document.querySelector('[data-calendar]');
  if (!calendar) return;

  const monthLabel = calendar.querySelector('[data-calendar-month]');
  const grid = calendar.querySelector('[data-calendar-grid]');
  const prevBtn = calendar.querySelector('[data-calendar-prev]');
  const nextBtn = calendar.querySelector('[data-calendar-next]');
  const showOutsideDays = calendar.dataset.showOutsideDays === 'true';

  const monthFormatter = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long' });
  const dayFormatter = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'full' });

  const today = new Date();
  let viewDate = new Date(today.getFullYear(), today.getMonth(), 1);
  let selectedDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());

  function toISODate(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  function fromISODate(value) {
    const parts = value.split('-').map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
    return new Date(parts[0], parts[1] - 1, parts[2]);
  }

  function isSameDay(a, b) {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  }

  function renderDays() {
    if (!grid || !monthLabel) return;

    monthLabel.textContent = monthFormatter.format(viewDate);
    grid.innerHTML = '';

    const startOfMonth = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
    const firstDayIndex = startOfMonth.getDay();
    const startDate = showOutsideDays
      ? new Date(viewDate.getFullYear(), viewDate.getMonth(), 1 - firstDayIndex)
      : startOfMonth;
    const daysInMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0).getDate();

    const totalCells = showOutsideDays
      ? 42
      : Math.ceil((firstDayIndex + daysInMonth) / 7) * 7;

    let hasSelectedInView = false;

    for (let cellIndex = 0; cellIndex < totalCells; cellIndex += 1) {
      const date = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate() + cellIndex);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'calendar__day';
      button.textContent = String(date.getDate());
      button.dataset.date = toISODate(date);
      button.dataset.monthOffset = String((date.getFullYear() - viewDate.getFullYear()) * 12 + (date.getMonth() - viewDate.getMonth()));
      button.setAttribute('role', 'gridcell');
      button.setAttribute('aria-label', dayFormatter.format(date));

      const isOutside = button.dataset.monthOffset !== '0';
      if (isOutside) {
        button.classList.add('is-outside');
        if (!showOutsideDays) {
          button.disabled = true;
        }
      }

      if (isSameDay(date, today)) {
        button.classList.add('is-today');
      }

      if (selectedDate && isSameDay(date, selectedDate)) {
        button.setAttribute('aria-selected', 'true');
        button.tabIndex = 0;
        hasSelectedInView = true;
      } else {
        button.setAttribute('aria-selected', 'false');
        button.tabIndex = -1;
      }

      grid.appendChild(button);
    }

    if (!hasSelectedInView) {
      const firstDay = grid.querySelector('.calendar__day');
      if (firstDay) firstDay.tabIndex = 0;
    }

    calendar.dataset.selectedDate = selectedDate ? toISODate(selectedDate) : '';
  }

  function showPreviousMonth() {
    viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1);
    renderDays();
  }

  function showNextMonth() {
    viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1);
    renderDays();
  }

  function handleDaySelection(event) {
    const target = event.target.closest('.calendar__day');
    if (!target || !grid.contains(target)) return;
    const { date: isoDate, monthOffset } = target.dataset;
    if (!isoDate) return;
    const parsed = fromISODate(isoDate);
    if (!parsed) return;

    if (monthOffset && Number(monthOffset) !== 0) {
      viewDate = new Date(parsed.getFullYear(), parsed.getMonth(), 1);
    }

    selectedDate = parsed;
    renderDays();
  }

  if (prevBtn) prevBtn.addEventListener('click', showPreviousMonth);
  if (nextBtn) nextBtn.addEventListener('click', showNextMonth);
  if (grid) grid.addEventListener('click', handleDaySelection);

  renderDays();
})();
