/* Functional motion only: selection follows input, review follows layout. */
(() => {
  const root = document.documentElement;
  const reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const forcedColors = window.matchMedia('(forced-colors: active)');
  const omega = 24;
  let initialized = false;

  function init() {
    if (initialized) return;
    initialized = true;
    root.dataset.input ||= 'pointer';
    const tracks = [...document.querySelectorAll('.presets, .segmented')].map(element => {
      const selection = document.createElement('span');
      selection.className = 'calm-selection';
      selection.setAttribute('aria-hidden', 'true');
      selection.hidden = true;
      selection.style.width = '100px';
      selection.style.height = 'calc(100% - 6px)';
      selection.style.transformOrigin = '0 50%';
      element.appendChild(selection);
      return { element, selection, x: 0, width: 0, vx: 0, vw: 0,
        targetX: 0, targetWidth: 0, positioned: false, visible: false };
    });
    const panel = document.getElementById('preview-panel');
    const stats = document.getElementById('stats');
    const groups = document.getElementById('groups');
    let frame = 0, lastTime = null, queued = false, queueInstant = false;
    let layoutBefore = null, groupAnimation = null;
    const layoutAnimations = new Set();
    const isCalm = () => root.dataset.appearance === 'calm';
    const canAnimate = () => isCalm() && root.dataset.input === 'pointer' &&
      root.dataset.motion !== 'reduced' && !reducedQuery.matches &&
      !forcedColors.matches && !document.hidden;

    function paint(track) {
      track.selection.style.transform = `translate(${track.x.toFixed(3)}px, 3px) scaleX(${(track.width / 100).toFixed(5)})`;
    }
    function settled(track) {
      return Math.abs(track.x - track.targetX) < .05 && Math.abs(track.width - track.targetWidth) < .05 &&
        Math.abs(track.vx) < .1 && Math.abs(track.vw) < .1;
    }
    function snap(track) {
      track.x = track.targetX;
      track.width = track.targetWidth;
      track.vx = track.vw = 0;
      paint(track);
    }
    function stopFrame() {
      cancelAnimationFrame(frame);
      frame = 0;
      lastTime = null;
    }
    function advance(time) {
      if (lastTime === null) { lastTime = time; return; }
      const dt = Math.max(0, (time - lastTime) / 1000);
      lastTime = time;
      const decay = Math.exp(-omega * dt);
      for (const track of tracks) {
        if (!track.visible || settled(track)) continue;
        // Exact critically damped solution, preserving velocity when redirected.
        const dx = track.x - track.targetX, dw = track.width - track.targetWidth;
        const ax = track.vx + omega * dx, aw = track.vw + omega * dw;
        track.x = track.targetX + (dx + ax * dt) * decay;
        track.width = track.targetWidth + (dw + aw * dt) * decay;
        track.vx = (track.vx - omega * ax * dt) * decay;
        track.vw = (track.vw - omega * aw * dt) * decay;
        if (settled(track)) snap(track); else paint(track);
      }
    }
    function tick(time) {
      frame = 0;
      if (!canAnimate()) { sync(true); return; }
      advance(time);
      if (tracks.some(track => track.visible && !settled(track))) frame = requestAnimationFrame(tick);
      else lastTime = null;
    }
    function sync(instant = false) {
      // Read all targets before any style writes; hidden controls use native CSS.
      const measurements = tracks.map(track => {
        const selected = track.element.querySelector('button[aria-pressed="true"]');
        return { track, x: selected?.offsetLeft || 0, width: selected?.offsetWidth || 0,
          visible: isCalm() && !forcedColors.matches && Boolean(selected) &&
            track.element.offsetWidth > 0 && selected.offsetWidth > 0 };
      });
      if (frame) advance(performance.now());
      const immediate = instant || !canAnimate();
      for (const { track, x, width, visible } of measurements) {
        track.targetX = x;
        track.targetWidth = width;
        track.visible = visible;
        track.selection.hidden = !visible;
        track.element.classList.toggle('calm-track-ready', visible);
        if (immediate || !visible || !track.positioned || settled(track)) snap(track);
        track.positioned = visible;
      }
      if (immediate || !tracks.some(track => track.visible && !settled(track))) {
        stopFrame();
      } else if (!frame) {
        lastTime = performance.now();
        frame = requestAnimationFrame(tick);
      }
    }
    function queueSync(instant = false) {
      queueInstant ||= instant;
      if (queued) return;
      queued = true;
      queueMicrotask(() => {
        const immediate = queueInstant;
        queued = queueInstant = false;
        sync(immediate);
      });
    }

    function cancelLayout() {
      layoutBefore = null;
      for (const animation of layoutAnimations) animation.cancel();
      layoutAnimations.clear();
      groupAnimation = null;
    }
    function animate(element, keyframes, options) {
      if (typeof element?.animate !== 'function') return null;
      const animation = element.animate(keyframes, options);
      layoutAnimations.add(animation);
      animation.onfinish = () => {
        layoutAnimations.delete(animation);
        if (groupAnimation === animation) groupAnimation = null;
        animation.cancel();
      };
      return animation;
    }
    function captureLayout() {
      // Capture the current presentation before cancelling an interrupted FLIP.
      const before = canAnimate() ? {
        positions: [stats, panel].filter(Boolean).map(element => ({
          element, rect: element.getBoundingClientRect(),
        })),
        opacity: groupAnimation && groups ? Number.parseFloat(getComputedStyle(groups).opacity) : 0,
      } : null;
      cancelLayout();
      layoutBefore = before;
    }
    function revealReview() {
      const before = layoutBefore;
      cancelLayout();
      if (!before || !canAnimate()) return;
      const moves = before.positions.map(({ element, rect }) => {
        const after = element.getBoundingClientRect();
        return { element, x: (rect.left || 0) - (after.left || 0), y: rect.top - after.top };
      });
      for (const { element, x, y } of moves) {
        if (Math.abs(x) + Math.abs(y) < .5) continue;
        animate(element, [{ transform: `translate(${x}px, ${y}px)` }, { transform: 'translate(0, 0)' }],
          { duration: 240, easing: 'cubic-bezier(.2,.75,.25,1)' });
      }
      if (groups?.childElementCount) {
        groupAnimation = animate(groups, [{ opacity: Number.isFinite(before.opacity) ? before.opacity : 0 }, { opacity: 1 }],
          { duration: 220, easing: 'cubic-bezier(.2,.75,.25,1)' });
      }
    }
    function suspend() {
      cancelLayout();
      sync(true);
    }

    document.addEventListener('pointerdown', event => {
      root.dataset.input = event.pointerType === 'touch' || event.pointerType === 'pen' ? 'keyboard' : 'pointer';
      if (root.dataset.input === 'keyboard') suspend();
    }, { capture: true, passive: true });
    document.addEventListener('keydown', () => {
      root.dataset.input = 'keyboard';
      suspend();
    }, true);
    // The app emits this event before it finishes updating the selected buttons.
    window.addEventListener('organizer-state-change', () => queueSync());
    window.addEventListener('organizer-appearance-change', suspend);
    window.addEventListener('organizer-motion-change', suspend);
    window.addEventListener('organizer-preview-will-render', captureLayout);
    window.addEventListener('organizer-preview-ready', () => { revealReview(); queueSync(); });
    window.addEventListener('resize', suspend);
    document.addEventListener('toggle', () => queueSync(true), true);
    document.addEventListener('visibilitychange', suspend);
    window.addEventListener('pagehide', suspend);
    reducedQuery.addEventListener?.('change', suspend);
    forcedColors.addEventListener?.('change', suspend);
    if ('ResizeObserver' in window) {
      const observer = new ResizeObserver(() => queueSync(true));
      for (const track of tracks) {
        observer.observe(track.element);
        track.element.querySelectorAll('button').forEach(button => observer.observe(button));
      }
    }
    if ('MutationObserver' in window) {
      new MutationObserver(suspend).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
    }
    sync(true);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
