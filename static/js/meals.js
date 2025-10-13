(function () {
  const widget = document.querySelector('[data-meal-photo-widget]');
  if (!widget) return;

  const input = widget.querySelector('[data-photo-input]');
  const emptyState = widget.querySelector('[data-photo-empty]');
  const previewState = widget.querySelector('[data-photo-preview]');
  const previewImage = widget.querySelector('[data-photo-image]');

  if (!input || !emptyState || !previewState || !previewImage) return;

  let revokeUrl = null;
  let resetTimeout = 0;

  function resetWidget() {
    if (revokeUrl) {
      URL.revokeObjectURL(revokeUrl);
      revokeUrl = null;
    }
    window.clearTimeout(resetTimeout);
    previewImage.src = '';
    previewState.hidden = true;
    emptyState.hidden = false;
    input.value = '';
  }

  function showPreview(url) {
    if (!url) return;
    emptyState.hidden = true;
    previewState.hidden = false;
    previewImage.src = url;

    window.clearTimeout(resetTimeout);
    resetTimeout = window.setTimeout(() => {
      resetWidget();
    }, 3000);
  }

  input.addEventListener('change', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !target.files || !target.files[0]) return;
    const file = target.files[0];
    if (!file.type.startsWith('image/')) {
      resetWidget();
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    revokeUrl = objectUrl;
    showPreview(objectUrl);
  });

  widget.addEventListener('drop', (event) => {
    event.preventDefault();
    const { dataTransfer } = event;
    if (!dataTransfer || !dataTransfer.files || !dataTransfer.files[0]) return;
    const file = dataTransfer.files[0];
    if (!file.type.startsWith('image/')) return;
    const objectUrl = URL.createObjectURL(file);
    revokeUrl = objectUrl;
    showPreview(objectUrl);
  });

  widget.addEventListener('dragover', (event) => {
    event.preventDefault();
  });
})();
