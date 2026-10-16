/* Appearance and choreography never change the organizer's data or plan. */
(() => {
  const root = document.documentElement;
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const pointerQuery = window.matchMedia('(hover: hover) and (pointer: fine)');
  let entranceTimer = 0;
  let previewTimer = 0;
  let pointerFrame = 0;
  let pointerX = 0;
  let pointerY = 0;
  let initialized = false;

  const read = (key) => { try { return window.localStorage.getItem(key); } catch (_) { return null; } };
  const write = (key, value) => { try { window.localStorage.setItem(key, value); } catch (_) {} };
  const reduced = () => root.dataset.motion === 'reduced';
  const animatedAppearance = () => ['p3r', 'traces'].includes(root.dataset.appearance);
  const currentScene = () => document.querySelector(root.dataset.appearance === 'traces' ? '.traces-scene' : '.p3r-scene');
  function resetScenes() {
    document.querySelectorAll('.p3r-scene, .traces-scene').forEach(scene => {
      scene.style.removeProperty('--pointer-x');
      scene.style.removeProperty('--pointer-y');
    });
  }

  function syncMotion() {
    const reduce = motionQuery.matches || read('steam-organizer-motion') === 'reduced';
    root.dataset.motion = reduce ? 'reduced' : 'full';
    const button = document.getElementById('motion-btn');
    if (button) {
      button.setAttribute('aria-checked', String(reduce));
      button.disabled = motionQuery.matches;
      button.title = motionQuery.matches ? '已跟随系统减少动态效果' : '保留完整界面，减少入场、视差与持续动画';
    }
    if (reduce) {
      clearTimeout(entranceTimer);
      clearTimeout(previewTimer);
      cancelAnimationFrame(pointerFrame);
      pointerFrame = 0;
      root.classList.remove('appearance-enter', 'preview-reveal');
      resetScenes();
    }
    window.dispatchEvent(new CustomEvent('organizer-motion-change', { detail: { reduced: reduce } }));
  }

  function enter() {
    clearTimeout(entranceTimer);
    root.classList.remove('appearance-enter');
    if (!animatedAppearance() || reduced()) return;
    // Restart a finite transition; the overlay never captures input or focus.
    void document.body.offsetWidth;
    root.classList.add('appearance-enter');
    entranceTimer = window.setTimeout(() => root.classList.remove('appearance-enter'), 840);
  }

  function setAppearance(value, persist = true) {
    if (!['p3r', 'calm', 'traces'].includes(value)) return;
    const changed = root.dataset.appearance !== value;
    root.dataset.appearance = value;
    if (changed) {
      cancelAnimationFrame(pointerFrame);
      pointerFrame = 0;
      resetScenes();
    }
    if (persist) write('steam-organizer-appearance', value);
    document.querySelectorAll('[data-appearance]').forEach((button) => {
      if (button.tagName === 'BUTTON') button.setAttribute('aria-pressed', String(button.dataset.appearance === value));
    });
    if (changed) enter();
    window.dispatchEvent(new CustomEvent('organizer-appearance-change', { detail: { appearance: value } }));
  }

  function revealPreview() {
    clearTimeout(previewTimer);
    root.classList.remove('preview-reveal');
    if (!animatedAppearance() || reduced()) return;
    void document.body.offsetWidth;
    root.classList.add('preview-reveal');
    previewTimer = window.setTimeout(() => root.classList.remove('preview-reveal'), 640);
  }

  function init() {
    if (initialized) return;
    initialized = true;
    syncMotion();
    setAppearance(root.dataset.appearance || 'p3r', false);
    document.querySelectorAll('.stats article').forEach((article, index) => article.style.setProperty('--item-index', String(index)));
    document.querySelectorAll('button[data-appearance]').forEach((button) => {
      button.addEventListener('click', () => setAppearance(button.dataset.appearance));
    });
    document.getElementById('motion-btn')?.addEventListener('click', () => {
      write('steam-organizer-motion', reduced() ? 'full' : 'reduced');
      syncMotion();
    });
    motionQuery.addEventListener?.('change', syncMotion);
    window.addEventListener('organizer-preview-ready', revealPreview);
    const stage = document.querySelector('.stage');
    stage?.addEventListener('pointermove', (event) => {
      if (!animatedAppearance() || reduced() || !pointerQuery.matches) return;
      const bounds = stage.getBoundingClientRect();
      pointerX = ((event.clientX - bounds.left) / Math.max(bounds.width, 1) - .5) * 9;
      pointerY = ((event.clientY - bounds.top) / Math.max(bounds.height, 1) - .5) * 7;
      if (pointerFrame) return;
      pointerFrame = requestAnimationFrame(() => {
        const scene = currentScene();
        scene?.style.setProperty('--pointer-x', `${pointerX.toFixed(1)}px`);
        scene?.style.setProperty('--pointer-y', `${pointerY.toFixed(1)}px`);
        pointerFrame = 0;
      });
    }, { passive: true });
    stage?.addEventListener('pointerleave', () => {
      cancelAnimationFrame(pointerFrame);
      pointerFrame = 0;
      resetScenes();
    });
    enter();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
