// static/js/meals.js
(function () {
  console.log('[meals.js] initialized'); // ✅ 버전 표기 제거

  const widget = document.querySelector('[data-meal-photo-widget]');
  if (!widget) return;

  const input            = widget.querySelector('[data-photo-input]');
  const emptyState       = widget.querySelector('[data-photo-empty]');
  const previewState     = widget.querySelector('[data-photo-preview]');
  const previewImage     = widget.querySelector('[data-photo-image]');
  const resetButton      = widget.querySelector('[data-photo-reset]');
  const loadingState     = widget.querySelector('[data-photo-loading]');

  const resultCard       = document.getElementById('mealAnalysisCard');
  const resultTitle      = document.getElementById('mealAnalysisTitle');
  const resultLabel      = document.getElementById('mealAnalysisLabel');
  const resultConfidence = document.getElementById('mealAnalysisConfidence');
  const macrosTotalEl    = document.getElementById('mealAnalysisMacrosTotal');
  const macrosPer100El   = document.getElementById('mealAnalysisMacrosPer100');
  const resultServing    = document.getElementById('mealAnalysisServing');
  const resultNote       = document.getElementById('mealAnalysisNote');
  const resultAlt        = document.getElementById('mealAnalysisAlternatives');
  const resultContainer  = widget.querySelector('[data-analysis-container]');
  const errorBox         = document.getElementById('mealAnalysisError');

  let commitButton       = widget.querySelector('[data-photo-commit]');
  const commitErrorBox   = document.getElementById('mealCommitError');

  const historyList      = document.getElementById('mealHistoryList');

  if (!input || !emptyState || !previewState || !previewImage) return;

  let revokeUrl = null;
  let lastSavePayload = null;
  let lastPreviewPhotoUrl = null;

  // ---------- utils ----------
  const mealTypeClass = (type) => {
    const map = {
      breakfast: 'breakfast', lunch: 'lunch', dinner: 'dinner', snack: 'snack',
      '아침': 'breakfast', '점심': 'lunch', '저녁': 'dinner', '간식': 'snack',
    };
    return map[type] || 'default';
  };

  const formatNumber = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return '-';
    return Number.isInteger(n) ? `${n}` : n.toFixed(1);
  };

  const getCSRFToken = () => {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  };

  function stringifyErr(e) {
    if (e == null) return '';
    if (typeof e === 'string') return e;
    if (e.message) return String(e.message);
    try { return JSON.stringify(e); } catch { return String(e); }
  }

  function toggleState({ empty = false, preview = false, loading = false }) {
    emptyState.hidden = !empty;
    previewState.hidden = !preview;
    if (loadingState) loadingState.hidden = !loading;
  }

  function resetAnalysis() {
    if (resultCard) resultCard.hidden = true;
    if (resultContainer) resultContainer.hidden = true;
    if (errorBox) { errorBox.hidden = true; errorBox.textContent = ''; }
    if (commitErrorBox) { commitErrorBox.hidden = true; commitErrorBox.textContent = ''; }

    if (commitButton) {
      commitButton.hidden = true;
      commitButton.disabled = false;
      commitButton.removeAttribute('data-payload');
    }
    lastSavePayload = null;
    lastPreviewPhotoUrl = null;

    if (macrosTotalEl)  macrosTotalEl.innerHTML  = '';
    if (macrosPer100El) macrosPer100El.innerHTML = '';
    if (resultServing)  { resultServing.textContent = ''; resultServing.hidden = true; }
    if (resultNote)     { resultNote.textContent = ''; resultNote.hidden = true; }
    if (resultAlt)      { resultAlt.innerHTML = ''; resultAlt.hidden = true; }
  }

  function resetWidget() {
    if (revokeUrl) { URL.revokeObjectURL(revokeUrl); revokeUrl = null; }
    previewImage.src = '';
    input.value = '';
    resetAnalysis();
    toggleState({ empty: true, preview: false, loading: false });
  }

  function showPreview(url) {
    toggleState({ empty: false, preview: true, loading: false });
    previewImage.src = url;
  }

  function updateSummaryGrid(consumed) {
    const summaryGrid = document.querySelector('.meal-summary-grid');
    if (!summaryGrid) return;
    const summaryItems = {
      calories: summaryGrid.children[0],
      protein:  summaryGrid.children[1],
      carbs:    summaryGrid.children[2],
      fat:      summaryGrid.children[3],
    };
    Object.entries(summaryItems).forEach(([key, item]) => {
      if (!item || consumed[key] == null) return;
      const valueEl = item.querySelector('.meal-summary__value span:first-child');
      const goal = Number(item.dataset.goal || '0');
      const progressFill = item.querySelector('.meal-progress__fill');
      if (valueEl) valueEl.textContent = consumed[key];
      if (progressFill && goal > 0) {
        progressFill.style.setProperty('--progress', `${Math.min((consumed[key] / goal) * 100, 100)}%`);
      }
    });
  }

  function attachDeleteHandlers(scope) {
    (scope || document).querySelectorAll('[data-history-delete]').forEach((btn) => {
      if (btn.dataset.bound === 'true') return;
      btn.dataset.bound = 'true';
      btn.addEventListener('click', async () => {
        const itemId = btn.getAttribute('data-item-id') || btn.closest('[data-item-id]')?.getAttribute('data-item-id');
        if (!itemId) return;
        if (!confirm('이 기록을 삭제할까요?')) return;
        try {
          const res = await fetch(`/api/ai/meal-entry/${itemId}/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': getCSRFToken(), 'Accept': 'application/json' },
            credentials: 'same-origin',
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            const detail = data.error || data.detail || `status ${res.status}`;
            throw new Error(detail);
          }
          const card = btn.closest('[data-history-item]') || btn.closest('.meal-history__item');
          if (card) card.remove();
          const historyList = document.getElementById('mealHistoryList');
          if (historyList && !historyList.querySelector('[data-history-item], .meal-history__item')) {
            historyList.innerHTML = '<p class="meal-history__empty" data-history-empty>오늘 기록된 식사가 아직 없습니다.</p>';
          }
          if (data.updated_consumed) updateSummaryGrid(data.updated_consumed);
        } catch (err) {
          console.error('Meal delete failed', err);
          alert(stringifyErr(err));
        }
      });
    });
  }

  // ---------- commit button binding ----------
  function ensureCommitButton() {
    if (!commitButton || !document.body.contains(commitButton)) {
      commitButton = widget.querySelector('[data-photo-commit]');
      if (commitButton) {
        console.log('[meals] commit button found/rebound');
        bindCommitClick();
      }
    }
    return commitButton;
  }

  function bindCommitClick() {
    if (!commitButton || commitButton.__bound) return;
    commitButton.__bound = true;
    commitButton.addEventListener('click', onCommitClick);
  }

  async function onCommitClick() {
    if (!lastSavePayload) return;
    if (commitErrorBox) { commitErrorBox.hidden = true; commitErrorBox.textContent = ''; }

    commitButton.disabled = true;
    const original = commitButton.textContent;
    commitButton.textContent = '저장 중...';

    try {
      const res = await fetch('/api/ai/meal-commit/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
        credentials: 'same-origin',
        body: JSON.stringify(lastSavePayload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        let msg = data.error || data.detail || `HTTP ${res.status}`;
        if (typeof msg === 'object') { try { msg = JSON.stringify(msg); } catch {} }
        throw new Error(msg);
      }

      if (data.updated_consumed) updateSummaryGrid(data.updated_consumed);

      if (historyList && data.saved && data.meal_item_id) {
        const emptyRow = historyList.querySelector('[data-history-empty]');
        if (emptyRow) emptyRow.remove();

        const macros = lastSavePayload.macros || {};
        const card = document.createElement('article');
        card.className = 'meal-history__item';
        card.dataset.historyItem = 'true';
        card.dataset.itemId = String(data.meal_item_id);

        const macroSegments = [];
        const p = formatNumber(macros.protein); if (p !== '-') macroSegments.push(`<span><strong>${p}g</strong> protein</span>`);
        const c = formatNumber(macros.carb);    if (c !== '-') macroSegments.push(`<span><strong>${c}g</strong> carbs</span>`);
        const f = formatNumber(macros.fat);     if (f !== '-') macroSegments.push(`<span><strong>${f}g</strong> fat</span>`);
        const macrosRow = macroSegments.length ? `<div class="meal-history__macros">${macroSegments.join('')}</div>` : '';

        const calText = formatNumber(macros.calories);
        const caloriesHtml = calText !== '-' ? `${caloriesHtmlSafe(calText)} cal` : '-';

        const serverPhotoUrl = data.photo_url || null;
        const thumbHtml = serverPhotoUrl
          ? `<img src="${serverPhotoUrl}" alt="${escapeHtml(lastSavePayload.label_ko || '식사 사진')}">`
          : (previewImage && previewImage.src
              ? `<img src="${previewImage.src}" alt="${escapeHtml(lastSavePayload.label_ko || '식사 사진')}">`
              : '<span class="meal-history__emoji">🥗</span>');

        const mealType = lastSavePayload.meal_type || '식사';
        card.innerHTML = `
          <div class="meal-history__thumb" aria-hidden="true">
            ${thumbHtml}
          </div>
          <div class="meal-history__info">
            <div class="meal-history__title-row">
              <strong>${escapeHtml(lastSavePayload.label_ko || '분석 식사')}</strong>
              <span class="badge badge--subtle meal-type--${mealTypeClass(mealType)}">${escapeHtml(mealType)}</span>
              <span class="badge badge--ai"><span aria-hidden="true">⚡</span>AI</span>
            </div>
            <span class="meal-history__calories">${caloriesHtml}</span>
          </div>
          ${macrosRow}
          <button type="button" class="meal-history__delete" data-history-delete data-item-id="${data.meal_item_id}" aria-label="식사 삭제">×</button>
        `;
        historyList.prepend(card);
        attachDeleteHandlers(card);
      }

      commitButton.hidden = true;
      lastSavePayload = null;
    } catch (err) {
      if (commitErrorBox) {
        commitErrorBox.textContent = stringifyErr(err) || '저장 중 오류가 발생했습니다.';
        commitErrorBox.hidden = false;
      }
    } finally {
      commitButton.disabled = false;
      commitButton.textContent = original || '저장하기';
    }
  }

  function caloriesHtmlSafe(v) { return String(v); }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c)=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c])); }

  function renderMacrosRow(macros) {
    const parts = [];
    const cal = formatNumber(macros.calories); if (cal !== '-') parts.push(`<span><strong>${cal}</strong> cal</span>`);
    const pro = formatNumber(macros.protein);  if (pro !== '-') parts.push(`<span><strong>${pro}g</strong> protein</span>`);
    const carb= formatNumber(macros.carb);     if (carb !== '-') parts.push(`<span><strong>${carb}g</strong> carbs</span>`);
    const fat = formatNumber(macros.fat);      if (fat !== '-') parts.push(`<span><strong>${fat}g</strong> fat</span>`);
    return parts.join('');
  }

  // ---------- 분석 호출 ----------
  async function analyzeImage(file) {
    if (!file) return;
    resetAnalysis();
    toggleState({ empty: false, preview: true, loading: true });

    const formData = new FormData();
    formData.append('image', file, file.name);
    formData.append('commit', 'preview');

    try {
      const res = await fetch('/api/ai/meal-analyze/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
        credentials: 'same-origin',
      });

      const raw = await res.text();
      let data;
      try { data = JSON.parse(raw); } catch { data = { error: raw.slice(0, 500) }; }

      if (!res.ok) {
        let msg = data.error || data.detail || `이미지를 분석하지 못했습니다. (HTTP ${res.status})`;
        if (typeof msg === 'object') { try { msg = JSON.stringify(msg); } catch {} }
        throw new Error(msg);
      }

      if (resultTitle) resultTitle.textContent = data.label_ko || data.label || '분석 결과';
      if (resultLabel) resultLabel.textContent = data.label ? `(${data.label})` : '';
      if (resultConfidence) resultConfidence.textContent = (data.confidence != null) ? `${data.confidence}% 신뢰도` : '';

      lastPreviewPhotoUrl = data.photo_url || null;
      if (lastPreviewPhotoUrl) {
        previewImage.src = lastPreviewPhotoUrl;
      }

      const per100 = data.macros_per100g || data.macros || {};
      const total  = data.macros_total   || {};
      if (resultServing) {
        const w = data.weight_g;
        if (w) { resultServing.textContent = `기준량: ${formatNumber(w)} g`; resultServing.hidden = false; }
        else   { resultServing.textContent = ''; resultServing.hidden = true; }
      }
      if (macrosTotalEl)  macrosTotalEl.innerHTML  = renderMacrosRow(total);
      if (macrosPer100El) macrosPer100El.innerHTML = renderMacrosRow(per100);

      if (resultNote) {
        if (data.source === 'default')       { resultNote.textContent = '정확한 매칭을 찾지 못해 기본 열량 정보를 사용했습니다.'; resultNote.hidden = false; }
        else if (data.source === 'csv_estimate') { resultNote.textContent = 'CSV 평균값(가늠)으로 추정했습니다.'; resultNote.hidden = false; }
        else if (data.source === 'fallback') { resultNote.textContent = '대표 음식 영양 정보를 사용했습니다.'; resultNote.hidden = false; }
        else if (data.source === 'unmatched'){ resultNote.textContent = '일치하는 음식 데이터를 찾지 못했어요.'; resultNote.hidden = true; }
        else { resultNote.textContent = ''; resultNote.hidden = true; }
      }

      if (resultAlt) {
        const alt = Array.isArray(data.alternatives) ? data.alternatives : [];
        if (alt.length) {
          const items = alt.slice(0, 3).map(it => `<li>${escapeHtml(it.label)} (${Math.round((it.score || 0) * 100)}%)</li>`).join('');
          resultAlt.innerHTML = `<h4>다른 후보</h4><ul>${items}</ul>`;
          resultAlt.hidden = false;
        } else {
          resultAlt.innerHTML = '';
          resultAlt.hidden = true;
        }
      }

      if (resultContainer) resultContainer.hidden = false;
      if (resultCard) resultCard.hidden = false;

      console.log('[meals] analyze ok:', {
        can_save: data.can_save, has_payload: !!data.save_payload, meal_type: data.meal_type
      });
      window.__mealAnalyzeLast = data;

      ensureCommitButton();
      if (commitButton) {
        if (data.can_save && data.save_payload) {
          lastSavePayload = data.save_payload;
          commitButton.hidden = false;
          commitButton.disabled = false;
          commitButton.dataset.payload = JSON.stringify(lastSavePayload);
        } else {
          lastSavePayload = null;
          commitButton.hidden = true;
        }
      }

      if (data.saved && data.updated_consumed) {
        updateSummaryGrid(data.updated_consumed);
      }
    } catch (error) {
      console.error('[meals] analyze error:', error);
      if (errorBox) {
        errorBox.textContent = stringifyErr(error) || '이미지를 분석하지 못했습니다.';
        errorBox.hidden = false;
      }
    } finally {
      toggleState({ empty: false, preview: true, loading: false });
    }
  }

  // ---------- 파일 선택 / 드롭 ----------
  input.addEventListener('change', (e) => {
    const target = e.target;
    if (!(target instanceof HTMLInputElement) || !target.files || !target.files[0]) return;
    const file = target.files[0];
    if (!file.type.startsWith('image/')) {
      resetWidget();
      if (errorBox) { errorBox.textContent = '이미지 파일을 선택해 주세요.'; errorBox.hidden = false; }
      return;
    }
    const url = URL.createObjectURL(file);
    revokeUrl = url;
    showPreview(url);
    analyzeImage(file);
  });

  widget.addEventListener('dragover', (e) => e.preventDefault());
  widget.addEventListener('drop', (e) => {
    e.preventDefault();
    const dt = e.dataTransfer;
    if (!dt || !dt.files || !dt.files[0]) return;
    const file = dt.files[0];
    if (!file.type.startsWith('image/')) return;
    const url = URL.createObjectURL(file);
    revokeUrl = url;
    showPreview(url);
    analyzeImage(file);
  });

  if (resetButton) resetButton.addEventListener('click', resetWidget);

  // ---------- 초기 바인딩 & 위임 ----------
  bindCommitClick();
  widget.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-photo-commit]');
    if (!btn) return;
    if (btn !== commitButton) {
      commitButton = btn;
      bindCommitClick();
    }
  });

  attachDeleteHandlers(historyList);
})();
