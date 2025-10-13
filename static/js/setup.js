(function () {
  function activateGroup(selector, activeClass) {
    document.querySelectorAll(selector).forEach((input) => {
      const label = input.closest('label');
      if (!label) return;
      label.classList.toggle(activeClass, input.checked);
      input.addEventListener('change', () => {
        const name = input.name;
        document.querySelectorAll(selector + `[name="${name}"]`).forEach((other) => {
          const otherLabel = other.closest('label');
          if (otherLabel) {
            otherLabel.classList.toggle(activeClass, other.checked);
          }
        });
      });
    });
  }

  activateGroup('input[name="goal"]', 'is-active');
  activateGroup('input[name="activity_level"]', 'is-active');
})();
