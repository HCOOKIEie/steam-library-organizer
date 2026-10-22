/* Finite, decorative choreography. Never reads or writes Steam data. */
(() => {
  const root = document.documentElement;
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
  let initialized = false;

  function initBackground(panel) {
    const stage = document.querySelector('.stage');
    const canvas = document.getElementById('calm-field-canvas');
    const trigger = document.getElementById('calm-field-trigger');
    if (!stage || !canvas || !trigger) return;
    let ctx = null;
    try { if (window.CanvasRenderingContext2D) ctx = canvas.getContext('2d'); } catch (_) {}
    if (!ctx) {
      canvas.dataset.fieldState = 'unavailable';
      trigger.disabled = true;
      trigger.title = '当前环境使用静态背景';
      return;
    }
    const forcedColors = window.matchMedia('(forced-colors: active)');
    const controls = 'button,input,label,summary,a,select,textarea,[role="button"],.preview-panel,.quality-card';
    let frame = 0, width = 0, height = 0, visible = true, heat = 0, lastInput = -Infinity;
    let pointer = { x: 0, y: 0 }, ripples = [];
    let dark = root.dataset.theme === 'dark';
    const allowed = () => root.dataset.appearance === 'calm' && root.dataset.motion !== 'reduced' &&
      !forcedColors.matches && !document.hidden && visible && !document.body.classList.contains('modal-open') &&
      !panel.classList.contains('has-preview');

    function draw(time) {
      ctx.clearRect(0, 0, width, height);
      const step = 44;
      // A deterministic field avoids random flicker and allocates no particles per frame.
      for (let row = 0, cy = 22; cy < height; row++, cy += step) {
        for (let col = 0, cx = 22; cx < width; col++, cx += step) {
          const seed = ((col * 73 + row * 151 + col * row * 17) % 101) / 101;
          const right = cx / Math.max(width, 1);
          const density = .18 + right * .35;
          if (seed > density && !heat && !ripples.length) continue;
          const dx = cx - pointer.x, dy = cy - pointer.y;
          const distance = Math.hypot(dx, dy);
          const near = Math.max(0, 1 - distance / 185) ** 2 * heat;
          let wave = 0, shiftX = dx / Math.max(distance, 1) * near * 8;
          let shiftY = dy / Math.max(distance, 1) * near * 8;
          for (const ripple of ripples) {
            const progress = (time - ripple.at) / 1450;
            const rx = cx - ripple.x, ry = cy - ripple.y;
            // Chebyshev distance creates square wavefronts that echo the card geometry.
            const radius = Math.max(width, height) * .85 * progress;
            const edge = Math.max(0, 1 - Math.abs(Math.max(Math.abs(rx), Math.abs(ry)) - radius) / 62);
            const strength = edge * edge * (1 - progress);
            wave = Math.max(wave, strength);
            shiftX += Math.sign(rx) * strength * 9;
            shiftY += Math.sign(ry) * strength * 9;
          }
          const activity = Math.min(1, near + wave);
          if (seed > density && activity < .04) continue;
          // Keep the title side quiet; surfaces above the field remain opaque.
          const base = seed <= density ? (.025 + right * .045) : 0;
          const alpha = (base + activity * (dark ? .38 : .23)) * (.38 + right * .62);
          const size = 6 + seed * 11 + activity * 6;
          const px = cx + shiftX - size / 2, py = cy + shiftY - size / 2;
          ctx.fillStyle = dark ? `rgba(199,250,114,${alpha})` : `rgba(65,95,26,${alpha})`;
          if (seed < .12) ctx.fillRect(px, py, size, size);
          else {
            ctx.fillRect(px, py, size, 1);
            ctx.fillRect(px, py + size - 1, size, 1);
            ctx.fillRect(px, py, 1, size);
            ctx.fillRect(px + size - 1, py, 1, size);
          }
        }
      }
    }
    function stop() {
      cancelAnimationFrame(frame);
      frame = 0;
      heat = 0;
      lastInput = -Infinity;
      ripples = [];
      canvas.dataset.fieldState = 'paused';
      ctx.clearRect(0, 0, width, height);
    }
    function tick(time) {
      frame = 0;
      if (!allowed()) { stop(); return; }
      heat = Math.max(0, 1 - (time - lastInput) / 950);
      ripples = ripples.filter(ripple => time - ripple.at < 1450);
      draw(time);
      canvas.dataset.fieldState = heat || ripples.length ? 'active' : 'idle';
      if (heat || ripples.length) frame = requestAnimationFrame(tick);
    }
    function wake() {
      if (!frame && allowed()) frame = requestAnimationFrame(tick);
    }
    function resize() {
      if (root.dataset.appearance !== 'calm') return;
      const rect = stage.getBoundingClientRect();
      const w = Math.round(rect.width), h = Math.round(stage.clientHeight || rect.height);
      const scale = Math.min(window.devicePixelRatio || 1, 1.5, Math.sqrt(3_000_000 / Math.max(w * h, 1)));
      if (w !== width || h !== height || canvas.width !== Math.round(w * scale)) {
        width = w;
        height = h;
        canvas.width = Math.round(w * scale);
        canvas.height = Math.round(h * scale);
        ctx.setTransform(scale, 0, 0, scale, 0, 0);
      }
    }
    function sync() {
      dark = root.dataset.theme === 'dark';
      trigger.disabled = root.dataset.motion === 'reduced' || forcedColors.matches;
      trigger.title = trigger.disabled ? '已减少动态效果，保留静态背景' : '移动鼠标探索背景，点击空白处或此按钮释放波纹';
      if (!allowed()) { stop(); return; }
      resize();
      draw(performance.now());
      canvas.dataset.fieldState = frame ? 'active' : 'idle';
    }
    function coordinates(event) {
      const rect = canvas.getBoundingClientRect();
      return { x: Math.max(0, Math.min(width, event.clientX - rect.left)),
        y: Math.max(0, Math.min(height, event.clientY - rect.top)) };
    }
    function pulse(position) {
      if (!allowed()) return;
      ripples.push({ ...position, at: performance.now() });
      ripples = ripples.slice(-3);
      wake();
    }
    stage.addEventListener('pointermove', event => {
      if (!allowed() || !finePointer.matches || event.pointerType === 'touch' || event.target.closest(controls)) return;
      pointer = coordinates(event);
      lastInput = performance.now();
      wake();
    }, { passive: true });
    stage.addEventListener('pointerleave', () => { lastInput = -Infinity; });
    stage.addEventListener('click', event => {
      if (event.target.closest(`${controls},.calm-intro,.stats`) || window.getSelection()?.toString()) return;
      pulse(coordinates(event));
    });
    trigger.addEventListener('click', () => pulse({ x: width * .7, y: Math.min(height * .3, 180) }));
    window.addEventListener('organizer-appearance-change', sync);
    window.addEventListener('organizer-motion-change', sync);
    window.addEventListener('organizer-preview-ready', sync);
    window.addEventListener('organizer-state-change', () => queueMicrotask(sync));
    document.addEventListener('visibilitychange', sync);
    window.addEventListener('pagehide', stop);
    window.addEventListener('resize', sync);
    forcedColors.addEventListener?.('change', sync);
    if ('ResizeObserver' in window) new ResizeObserver(sync).observe(stage);
    if ('MutationObserver' in window) new MutationObserver(sync).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? false; sync(); }).observe(stage);
    }
    sync();
  }

  function init() {
    if (initialized) return;
    initialized = true;
    const art = document.getElementById('calm-arrange');
    const panel = document.getElementById('preview-panel');
    const help = document.getElementById('calm-art-help');
    if (!art || !panel) return;
    let frame = 0, arrangeTimer = 0, finishTimer = 0, visible = true;
    let x = 0, y = 0, targetX = 0, targetY = 0, previousTime = 0;
    let layoutBefore = null;
    const layoutAnimations = new Set();
    const reduced = () => root.dataset.motion === 'reduced';
    const active = () => root.dataset.appearance === 'calm' && !document.hidden && visible &&
      !panel.classList.contains('has-preview') && !reduced();

    function stop() {
      clearTimeout(arrangeTimer);
      clearTimeout(finishTimer);
      cancelAnimationFrame(frame);
      arrangeTimer = finishTimer = frame = 0;
      x = y = targetX = targetY = previousTime = 0;
      art.dataset.phase = 'settled';
      art.style.removeProperty('--calm-rx');
      art.style.removeProperty('--calm-ry');
    }

    function cancelLayout() {
      layoutBefore = null;
      layoutAnimations.forEach(animation => animation.cancel());
      layoutAnimations.clear();
    }

    function revealReview() {
      // Move the real elements from their previous positions. No bitmap layer
      // sits above search fields or blocks input during the transition.
      const before = layoutBefore;
      cancelLayout();
      if (!before || reduced() || root.dataset.appearance !== 'calm' || document.hidden) return;
      before.forEach(({ element, top }) => {
        if (!element.animate) return;
        const distance = top - element.getBoundingClientRect().top;
        if (Math.abs(distance) < 1) return;
        const animation = element.animate([
          { transform: `translateY(${distance}px)` }, { transform: 'translateY(0)' },
        ], { duration: 300, easing: 'cubic-bezier(.2,.75,.25,1)' });
        layoutAnimations.add(animation);
        animation.onfinish = () => layoutAnimations.delete(animation);
      });
    }

    function replay() {
      if (!active()) return;
      clearTimeout(arrangeTimer);
      clearTimeout(finishTimer);
      art.dataset.phase = 'scattered';
      arrangeTimer = window.setTimeout(() => {
        arrangeTimer = 0;
        if (!active()) { stop(); return; }
        art.dataset.phase = 'arranging';
      }, 260);
      finishTimer = window.setTimeout(() => {
        finishTimer = 0;
        art.dataset.phase = 'settled';
      }, 1050);
    }

    function tick(time) {
      frame = 0;
      if (!active()) { stop(); return; }
      const dt = previousTime ? Math.min(time - previousTime, 40) : 16.7;
      previousTime = time;
      const follow = 1 - Math.exp(-dt / 75);
      x += (targetX - x) * follow;
      y += (targetY - y) * follow;
      const settled = Math.abs(targetX - x) + Math.abs(targetY - y) < .025;
      if (settled) { x = targetX; y = targetY; previousTime = 0; }
      art.style.setProperty('--calm-rx', `${x.toFixed(2)}deg`);
      art.style.setProperty('--calm-ry', `${y.toFixed(2)}deg`);
      if (!settled) frame = requestAnimationFrame(tick);
    }
    function moveTo(nextX, nextY) {
      targetX = nextX;
      targetY = nextY;
      if (!frame) frame = requestAnimationFrame(tick);
    }
    function sync() {
      const count = document.querySelectorAll('#modes .mode[aria-pressed="true"]').length;
      document.getElementById('calm-rule-count').textContent = count ? `${count} 项分类规则已就绪` : '选择规则，开始整理';
      art.disabled = reduced();
      help.textContent = reduced() ? '分类演示 · 已减少动态效果' : '移动探索 · 点击重排 · 分类演示';
      if (!active()) stop();
      if (reduced() || root.dataset.appearance !== 'calm' || document.hidden) cancelLayout();
    }
    art.addEventListener('click', replay);
    art.addEventListener('pointermove', event => {
      if (!active() || !finePointer.matches || event.pointerType === 'touch') return;
      const rect = art.getBoundingClientRect();
      const clamp = value => Math.max(-.5, Math.min(.5, value));
      moveTo(-clamp((event.clientY - rect.top) / Math.max(rect.height, 1) - .5) * 10,
        clamp((event.clientX - rect.left) / Math.max(rect.width, 1) - .5) * 14);
    }, { passive: true });
    art.addEventListener('pointerleave', () => { if (active()) moveTo(0, 0); else stop(); });
    art.addEventListener('blur', () => { if (active()) moveTo(0, 0); });
    window.addEventListener('organizer-appearance-change', () => { sync(); replay(); });
    window.addEventListener('organizer-motion-change', sync);
    // The app emits state-change before updating its action DOM.
    window.addEventListener('organizer-state-change', () => queueMicrotask(sync));
    window.addEventListener('organizer-preview-will-render', () => {
      cancelLayout();
      if (active()) layoutBefore = [document.getElementById('stats'), panel].map(element => ({
        element, top: element.getBoundingClientRect().top,
      }));
    });
    window.addEventListener('organizer-preview-ready', () => { revealReview(); sync(); });
    document.addEventListener('visibilitychange', sync);
    window.addEventListener('pagehide', () => { stop(); cancelLayout(); });
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => {
        visible = entries[0]?.isIntersecting ?? false;
        if (!visible) stop();
      });
      observer.observe(art);
    }
    sync();
    replay();
    initBackground(panel);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
