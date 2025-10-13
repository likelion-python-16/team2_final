(function () {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const animatedTargets = document.querySelectorAll('[data-animate]');
  const animatedChildren = document.querySelectorAll('[data-animate-child]');
  const progressBlocks = document.querySelectorAll('.landing-progress[data-progress]');
  const counters = document.querySelectorAll('strong[data-count]');
  const tiltCards = document.querySelectorAll('[data-tilt]');
  const phone = document.querySelector('[data-phone-tilt]');
  const heroBackground = document.querySelector('.landing-hero__background');
  const staggerGroups = document.querySelectorAll('[data-stagger]');
  const staggerItems = document.querySelectorAll('[data-stagger-item]');

  function setImmediateState() {
    animatedTargets.forEach((el) => el.classList.add('is-inview'));
    animatedChildren.forEach((el) => el.classList.add('is-inview'));
    progressBlocks.forEach((el) => {
      const fill = el.querySelector('.landing-progress__fill');
      const percentEl = el.querySelector('.landing-progress__percent');
      const target = Number(el.dataset.progress || 0);
      if (fill) fill.style.width = `${target}%`;
      if (percentEl) percentEl.textContent = `${Math.round(target)}%`;
    });
    counters.forEach((el) => {
      const value = el.dataset.count || el.textContent || '';
      const suffix = el.dataset.suffix || '';
      el.textContent = `${value}${suffix}`;
    });
    staggerItems.forEach((item) => item.classList.add('is-visible'));
  }

  if (prefersReducedMotion) {
    setImmediateState();
    return;
  }

  function animateProgress(el) {
    if (el.dataset.animated === 'true') return;
    const fill = el.querySelector('.landing-progress__fill');
    const percentEl = el.querySelector('.landing-progress__percent');
    const target = Number(el.dataset.progress || 0);
    if (!fill) return;
    el.dataset.animated = 'true';
    const duration = 1200;
    const start = performance.now();

    function step(now) {
      const progress = Math.min((now - start) / duration, 1);
      const current = target * progress;
      fill.style.width = `${current}%`;
      if (percentEl) percentEl.textContent = `${Math.round(current)}%`;
      if (progress < 1) requestAnimationFrame(step);
    }

    fill.style.width = '0%';
    requestAnimationFrame(step);
  }

  function animateCount(el) {
    if (el.dataset.animated === 'true') return;
    const target = Number(el.dataset.count || 0);
    const suffix = el.dataset.suffix || '';
    el.dataset.animated = 'true';
    const duration = 1400;
    const start = performance.now();

    function step(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = Math.round(target * eased);
      el.textContent = `${value}${suffix}`;
      if (progress < 1) requestAnimationFrame(step);
    }

    el.textContent = `0${suffix}`;
    requestAnimationFrame(step);
  }

  const observer = 'IntersectionObserver' in window
    ? new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const target = entry.target;
          target.classList.add('is-inview');
          if (target.matches('.landing-progress[data-progress]')) {
            animateProgress(target);
          }
          if (target.matches('strong[data-count]')) {
            animateCount(target);
          }
          if (target.matches('[data-stagger]')) {
            const items = target.querySelectorAll('[data-stagger-item]');
            items.forEach((item, index) => {
              window.setTimeout(() => {
                item.classList.add('is-visible');
              }, 120 * index);
            });
          }
          observer.unobserve(target);
        });
      }, {
        rootMargin: '0px 0px -10% 0px',
        threshold: 0.2,
      })
    : null;

  if (observer) {
    animatedTargets.forEach((el) => observer.observe(el));
    animatedChildren.forEach((el) => observer.observe(el));
    progressBlocks.forEach((el) => observer.observe(el));
    counters.forEach((el) => observer.observe(el));
    staggerGroups.forEach((el) => observer.observe(el));
  } else {
    setImmediateState();
  }

  function handleTilt(element, event) {
    const rect = element.getBoundingClientRect();
    const relX = (event.clientX - rect.left) / rect.width - 0.5;
    const relY = (event.clientY - rect.top) / rect.height - 0.5;
    const rotateX = relY * -12;
    const rotateY = relX * 16;
    element.style.transform = `perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    element.classList.add('is-tilting');
  }

  function resetTilt(element) {
    element.style.transform = 'perspective(900px) rotateX(0deg) rotateY(0deg)';
    element.classList.remove('is-tilting');
  }

  tiltCards.forEach((card) => {
    card.addEventListener('mousemove', (event) => handleTilt(card, event));
    card.addEventListener('mouseleave', () => resetTilt(card));
  });

  if (phone) {
    phone.addEventListener('mousemove', (event) => {
      const rect = phone.getBoundingClientRect();
      const relX = (event.clientX - rect.left) / rect.width - 0.5;
      const relY = (event.clientY - rect.top) / rect.height - 0.5;
      const rotateX = relY * -18;
      const rotateY = relX * 22;
      phone.style.transform = `perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
      phone.classList.add('is-tilting');
    });

    phone.addEventListener('mouseleave', () => {
      phone.style.transform = '';
      phone.classList.remove('is-tilting');
    });
  }

  let ticking = false;
  const parallaxStrength = 0.12;

  function handleScroll() {
    if (!heroBackground) return;
    const offset = window.scrollY * -parallaxStrength;
    heroBackground.style.transform = `translateY(${offset}px)`;
    ticking = false;
  }

  window.addEventListener('scroll', () => {
    if (!ticking) {
      window.requestAnimationFrame(handleScroll);
      ticking = true;
    }
  });

  handleScroll();
})();
