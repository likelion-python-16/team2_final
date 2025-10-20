(function () {
  console.log('[meals.js v5.5] init');

  // ---------------------- DOM refs ----------------------
  const widget           = document.querySelector('[data-meal-photo-widget]');
  if (!widget) return;

  const input            = widget.querySelector('[data-photo-input]');
  const emptyState       = widget.querySelector('[data-photo-empty]');
  const previewState     = widget.querySelector('[data-photo-preview]');
  const previewImage     = widget.querySelector('[data-photo-image]');
  const resetButton      = widget.querySelector('[data-photo-reset]');
  const loadingState     = widget.querySelector('[data-photo-loading]');

  const resultContainer  = widget.querySelector('[data-analysis-container]');
  const resultCard       = document.getElementById('mealAnalysisCard');
  const resultTitle      = document.getElementById('mealAnalysisTitle');
  const resultLabel      = document.getElementById('mealAnalysisLabel');
  const resultConfidence = document.getElementById('mealAnalysisConfidence');
  const resultServing    = document.getElementById('mealAnalysisServing');
  const resultMacros     = document.getElementById('mealAnalysisMacros');
  const resultNote       = document.getElementById('mealAnalysisNote');
  const resultAlt        = document.getElementById('mealAnalysisAlternatives');
  const errorBox         = document.getElementById('mealAnalysisError');

  let   commitButton     = widget.querySelector('[data-photo-commit]');
  const commitErrorBox   = document.getElementById('mealCommitError');

  const historyList      = document.getElementById('mealHistoryList');

  if (!input || !emptyState || !previewState || !previewImage) return;

  // ---------------------- state ----------------------
  let revokeUrl = null;
  let lastSavePayload = null;       // 서버에서 준 저장 payload
  window.__mealAnalyzeLast = null;  // 디버깅/후속 저장용

  // ---------------------- utils ----------------------
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

  const fmt1 = (n) => {
    const x = Number(n ?? 0);
    if (!Number.isFinite(x)) return 0;
    return Math.round(x * 10) / 10;
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

  function toggleState({ empty = false, preview = false, loading = false, analysis = false }) {
    emptyState.hidden   = !empty;
    previewState.hidden = !preview;
    if (loadingState) loadingState.hidden = !loading;
    if (resultContainer) resultContainer.hidden = !analysis;
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
      commitButton.textContent = '저장하기';
    }
    lastSavePayload = null;

    if (resultTitle)      resultTitle.textContent = '분석 결과';
    if (resultLabel)      resultLabel.textContent = '';
    if (resultConfidence) resultConfidence.textContent = '';
    if (resultServing)  { resultServing.textContent = ''; resultServing.hidden = true; }
    if (resultNote)     { resultNote.textContent = '';    resultNote.hidden = true; }
    if (resultAlt)      { resultAlt.innerHTML = '';       resultAlt.hidden = true; }
    if (resultMacros)   { resultMacros.innerHTML = '';    resultMacros.hidden = true; }
  }

  function resetWidget() {
    if (revokeUrl) { URL.revokeObjectURL(revokeUrl); revokeUrl = null; }
    previewImage.src = '';
    input.value = '';
    resetAnalysis();
    toggleState({ empty: true, preview: false, loading: false, analysis: false });
  }

  function showPreview(url) {
    toggleState({ empty: false, preview: true, loading: false, analysis: false });
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
          const list = document.getElementById('mealHistoryList');
          if (list && !list.querySelector('[data-history-item], .meal-history__item')) {
            list.innerHTML = '<p class="meal-history__empty" data-history-empty>오늘 기록된 식사가 아직 없습니다.</p>';
          }
          if (data.updated_consumed) updateSummaryGrid(data.updated_consumed);
        } catch (err) {
          console.error('Meal delete failed', err);
          alert(stringifyErr(err));
        }
      });
    });
  }

  // ---------------------- response normalize ----------------------
  // data → 항상 items[0]에 {name, macros(per100), macros_total(total), weight_g, source, confidence}
  function normalizeAnalyzeResponse(data) {
    if (!data || typeof data !== 'object') return { items: [], meal_type: '간식', can_save: false, save_payload: null };

    const hasSingle = (data.macros && data.macros_total) || (data.macros_per100g && data.macros_total);
    if (hasSingle) {
      const item = {
        name: data.label_ko || data.label || 'item',
        ai_label: data.label_ko || data.label || 'item',
        confidence: data.confidence ?? null,
        weight_g: data.weight_g ?? 100,
        source: data.source || 'csv',
        macros: data.macros_per100g || data.macros || { calories: 0, protein: 0, carb: 0, fat: 0 }, // 100g 기준(보조)
        macros_total: data.macros_total || { calories: 0, protein: 0, carb: 0, fat: 0 },             // 1회 제공량 총합(메인)
      };
      return { items: [item], meal_type: data.meal_type, can_save: !!data.can_save, save_payload: data.save_payload || null };
    }

    if (Array.isArray(data.items)) {
      return { items: data.items, meal_type: data.meal_type, can_save: !!data.can_save, save_payload: data.save_payload || null };
    }

    return { items: [], meal_type: data.meal_type, can_save: !!data.can_save, save_payload: data.save_payload || null };
  }

  function asPer100(macros) {
    if (macros?.kcal != null) {
      return { kcal: fmt1(macros.kcal), protein_g: fmt1(macros.protein_g), carb_g: fmt1(macros.carb_g), fat_g: fmt1(macros.fat_g) };
    }
    return { kcal: fmt1(macros?.calories), protein_g: fmt1(macros?.protein), carb_g: fmt1(macros?.carb), fat_g: fmt1(macros?.fat) };
  }

  function asTotal(macrosTotal) {
    if (macrosTotal?.kcal != null) {
      return { kcal: fmt1(macrosTotal.kcal), protein_g: fmt1(macrosTotal.protein_g), carb_g: fmt1(macrosTotal.carb_g), fat_g: fmt1(macrosTotal.fat_g) };
    }
    return { kcal: fmt1(macrosTotal?.calories), protein_g: fmt1(macrosTotal?.protein), carb_g: fmt1(macrosTotal?.carb), fat_g: fmt1(macrosTotal?.fat) };
  }

  // ---------------------- commit button helpers ----------------------
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

        const seg = [];
        const p = formatNumber(macros.protein); if (p !== '-') seg.push(`<span><strong>${p}g</strong> protein</span>`);
        const c = formatNumber(macros.carb);    if (c !== '-') seg.push(`<span><strong>${c}g</strong> carbs</span>`);
        const f = formatNumber(macros.fat);     if (f !== '-') seg.push(`<span><strong>${f}g</strong> fat</span>`);
        const macrosRow = seg.length ? `<div class="meal-history__macros">${seg.join('')}</div>` : '';

        const calText = formatNumber(macros.calories);
        const caloriesHtml = calText !== '-' ? `${calText} cal` : '-';

        const mealType = lastSavePayload.meal_type || '식사';
        card.innerHTML = `
          <div class="meal-history__thumb" aria-hidden="true">
            ${previewImage && previewImage.src ? `<img src="${previewImage.src}" alt="${lastSavePayload.label_ko || '식사 사진'}">` : '<span class="meal-history__emoji">🥗</span>'}
          </div>
          <div class="meal-history__info">
            <div class="meal-history__title-row">
              <strong>${lastSavePayload.label_ko || '분석 식사'}</strong>
              <span class="badge badge--subtle meal-type--${mealTypeClass(mealType)}">${mealType}</span>
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

      // 완료 처리
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

  // ---------------------- render ----------------------
  function renderAnalyzeResult(rawData) {
    const norm = normalizeAnalyzeResponse(rawData);
    const item = norm.items[0];

    // 초기화
    if (errorBox) { errorBox.hidden = true; errorBox.textContent = ''; }
    if (commitErrorBox) { commitErrorBox.hidden = true; commitErrorBox.textContent = ''; }

    if (!item) {
      if (resultTitle) resultTitle.textContent = '분석 결과';
      if (resultLabel) resultLabel.textContent = '항목을 찾지 못했습니다';
      if (resultConfidence) resultConfidence.textContent = '';
      if (resultServing) { resultServing.textContent = ''; resultServing.hidden = true; }
      if (resultMacros) { resultMacros.innerHTML = ''; resultMacros.hidden = true; }
      if (resultCard) resultCard.hidden = false;
      if (resultContainer) resultContainer.hidden = false;
      return;
    }

    // 🔴 메인: 총합(1회 제공량), 🔵 보조: 100g
    const per100 = asPer100(item.macros);         // 100g 기준(보조)
    const total  = asTotal(item.macros_total);    // 1회 제공량 기준(메인)

    if (resultTitle)      resultTitle.textContent = '분석 결과';
    if (resultLabel)      resultLabel.textContent = `${item.name || item.ai_label} (${item.source || 'csv'})`;
    if (resultConfidence) resultConfidence.textContent = (item.confidence != null) ? `${Math.round(item.confidence)}% 신뢰도` : '';

    if (resultServing) {
      const w = fmt1(item.weight_g ?? 100);
      resultServing.textContent = `중량: ${w} g 기준`;
      resultServing.hidden = false;
    }

    if (resultMacros) {
      resultMacros.innerHTML = `
        <div class="macro main">
          <strong>${total.kcal} kcal</strong>
          <span>탄 ${total.carb_g}g · 단 ${total.protein_g}g · 지 ${total.fat_g}g</span>
          <small class="muted">표시: 1회 제공량(총합) 기준</small>
        </div>
        <div class="macro sub">
          <span class="muted">100g 기준: ${per100.kcal} kcal · 탄 ${per100.carb_g}g · 단 ${per100.protein_g}g · 지 ${per100.fat_g}g</span>
        </div>
      `;
      resultMacros.hidden = false;
    }

    if (Array.isArray(rawData.alternatives) && rawData.alternatives.length) {
      const items = rawData.alternatives.slice(0, 3).map(a => `<li>${a.label} (${Math.round((a.score || 0) * 100)}%)</li>`).join('');
      resultAlt.innerHTML = `<h4>다른 후보</h4><ul>${items}</ul>`;
      resultAlt.hidden = false;
    } else {
      resultAlt.innerHTML = '';
      resultAlt.hidden = true;
    }

    // 안내 노트
    if (resultNote) {
      if (rawData.source === 'default')        { resultNote.textContent = '정확한 매칭을 찾지 못해 기본 열량 정보를 사용했습니다.'; resultNote.hidden = false; }
      else if (rawData.source === 'csv_estimate'){ resultNote.textContent = 'CSV 평균값(가늠)으로 추정했습니다.'; resultNote.hidden = false; }
      else if (rawData.source === 'fallback')  { resultNote.textContent = '대표 음식 영양 정보를 사용했습니다.'; resultNote.hidden = false; }
      else if (rawData.source === 'unmatched') { resultNote.textContent = '일치하는 음식 데이터를 찾지 못했어요.'; resultNote.hidden = false; }
      else { resultNote.textContent = ''; resultNote.hidden = true; }
    }

    if (resultContainer) resultContainer.hidden = false;
    if (resultCard) resultCard.hidden = false;

    // 저장 버튼/페이로드
    ensureCommitButton();
    window.__mealAnalyzeLast = rawData;
    if (commitButton) {
      if ((rawData.can_save || norm.can_save) && (rawData.save_payload || norm.save_payload)) {
        lastSavePayload = rawData.save_payload || norm.save_payload;
        commitButton.hidden = false;
        commitButton.disabled = false;
        commitButton.dataset.payload = JSON.stringify(lastSavePayload);
      } else {
        // 서버가 save_payload 안 줬다면, 클라에서 총합 기준으로 구성
        const mt = item.macros_total?.kcal != null
          ? { calories: item.macros_total.kcal, protein: item.macros_total.protein_g, carb: item.macros_total.carb_g, fat: item.macros_total.fat_g }
          : { calories: item.macros_total?.calories ?? 0, protein: item.macros_total?.protein ?? 0, carb: item.macros_total?.carb ?? 0, fat: item.macros_total?.fat ?? 0 };
        lastSavePayload = {
          label_ko: item.name || item.ai_label || 'item',
          macros: mt,                                       // ✅ 총합(1회 제공량) 저장
          meal_type: rawData.meal_type || '간식',
          source: item.source || 'csv',
          food_id: null,
        };
        commitButton.hidden = !(rawData.can_save || norm.can_save);
        commitButton.disabled = !(!commitButton.hidden);
      }
    }
  }

  // ---------------------- analyze ----------------------
  async function analyzeImage(file) {
    if (!file) return;
    resetAnalysis();
    toggleState({ empty: false, preview: true, loading: true, analysis: false });

    const formData = new FormData();
    formData.append('image', file, file.name);
    formData.append('commit', 'preview'); // 프리뷰 모드

    let res, data, raw;
    try {
      res = await fetch('/api/ai/meal-analyze/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
        credentials: 'same-origin',
      });

      raw = await res.text();
      try { data = JSON.parse(raw); } catch { data = { error: raw.slice(0, 500) }; }
    } catch (e) {
      if (errorBox) { errorBox.textContent = '네트워크 오류입니다.'; errorBox.hidden = false; }
      toggleState({ empty: false, preview: true, loading: false, analysis: false });
      return;
    }

    if (!res.ok || data.error) {
      if (errorBox) {
        errorBox.textContent = data.error || data.detail || `이미지를 분석하지 못했습니다. (HTTP ${res.status})`;
        errorBox.hidden = false;
      }
      toggleState({ empty: false, preview: true, loading: false, analysis: false });
      return;
    }

    console.log('[meals] analyze ok (full):', data);

    renderAnalyzeResult(data);
    toggleState({ empty: false, preview: true, loading: false, analysis: true });

    // 서버가 즉시 저장(safe/passed)한 경우 현황 갱신
    if (data.saved && data.updated_consumed) {
      updateSummaryGrid(data.updated_consumed);
    }
  }

  // ---------------------- file handlers ----------------------
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

  // ---------------------- commit binding & history delete ----------------------
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
