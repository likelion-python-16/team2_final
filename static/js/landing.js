(function () {
  const wordTarget = document.querySelector('.hero-title__word');
  if (!wordTarget) return;

  const words = JSON.parse(wordTarget.dataset.words || '[]');
  if (!words.length) return;

  let index = 0;
  setInterval(() => {
    index = (index + 1) % words.length;
    wordTarget.classList.add('is-switching');
    setTimeout(() => {
      wordTarget.textContent = words[index];
      wordTarget.classList.remove('is-switching');
    }, 220);
  }, 2200);
})();
