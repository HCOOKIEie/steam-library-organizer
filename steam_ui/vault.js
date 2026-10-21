/* Original square-particle field. Offline Canvas2D, no runtime dependencies. */
(() => {
  const root = document.documentElement;
  const $ = id => document.getElementById(id);
  let renderer = null, loaded = false, syncQueued = false, seed = 17;
  let paused = false;
  try { paused = localStorage.getItem('steam-organizer-particles-paused') === 'true'; } catch (_) {}
  const reduced = () => root.dataset.motion === 'reduced';
  const visible = () => root.dataset.appearance === 'vault' && root.dataset.vaultView !== 'review' && !document.hidden;
  const quiet = () => paused || reduced();
  const setText = (id, text) => { if ($(id).textContent !== text) $(id).textContent = text; };
  const hash = (x, y) => {
    const value = Math.sin(x * 127.1 + y * 311.7 + seed * 74.7) * 43758.5453;
    return value - Math.floor(value);
  };

  function syncControls() {
    $('vault-pause').disabled = reduced();
    $('vault-pause').setAttribute('aria-pressed', String(quiet()));
    setText('vault-pause-label', reduced() ? '已减少动效' : paused ? '继续动态' : '暂停动态');
    setText('vault-particle-help', reduced() ? '已跟随减少动效设置 · 可重排方格' : paused ? '动态已暂停 · 可重排方格' : '移动鼠标唤醒方格 · 点击释放波纹');
  }

  function showView(next, focus = false) {
    const review = next === 'review' && !$('vault-review-btn').disabled;
    root.dataset.vaultView = review ? 'review' : 'collection';
    $('vault-collection-btn').setAttribute('aria-pressed', String(!review));
    $('vault-review-btn').setAttribute('aria-pressed', String(review));
    setText('vault-view-title', review ? '分类审阅' : '我的游戏库');
    setText('vault-view-copy', review ? '检查每一个分类，留下适合你的整理方案。' : '下一款想玩的游戏，就在你的收藏里。');
    renderer?.wake();
    if (focus && review) $('preview-search').focus({ preventScroll: true });
  }
  function sync() {
    syncQueued = false;
    const generated = $('preview-badge').textContent !== '尚未生成';
    $('vault-review-btn').disabled = !generated;
    const count = document.querySelectorAll('#groups .group').length;
    setText('vault-plan-count', count ? String(count) : '');
    if (!generated && root.dataset.vaultView === 'review') showView('collection');
  }
  function queueSync() { if (!syncQueued) { syncQueued = true; queueMicrotask(sync); } }

  // Sampling keeps the resting field identical between Canvas and SVG fallback.
  function cells(width, height) {
    const pitch = width < 500 ? 30 : 38;
    const result = [];
    for (let row = 0; row < Math.ceil(height / pitch); row++) {
      for (let col = 0; col < Math.ceil(width / pitch); col++) {
        const x = (col + .5) * pitch, y = (row + .5) * pitch;
        const density = .06 + .84 * Math.pow(x / width, 1.25);
        result.push({ x, y, size: pitch * .56, on: hash(col, row) < density,
          phase: hash(col + 31, row + 19) * Math.PI * 2,
          alpha: .22 + hash(col + 9, row + 7) * .35 });
      }
    }
    return result;
  }
  function fallback(width = 1000, height = 560) {
    const fill = root.dataset.theme === 'light' ? '#7c3bb5' : '#a02cda';
    const rects = cells(width, height).filter(cell => cell.on).map(cell =>
      `<rect x="${(cell.x-cell.size/2).toFixed(1)}" y="${(cell.y-cell.size/2).toFixed(1)}" width="${cell.size}" height="${cell.size}" opacity="${cell.alpha.toFixed(2)}"/>`).join('');
    $('vault-art-fallback').innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid slice"><g fill="${fill}">${rects}</g></svg>`;
  }

  function createField(canvas) {
    if (typeof CanvasRenderingContext2D === 'undefined') return null;
    const context = canvas.getContext('2d', { alpha: true });
    if (!context) return null;
    const stage = canvas.closest('.stage');
    const surface = document.querySelector('.vault-exhibit');
    let frame = 0, disposed = false, width = 0, height = 0, grid = [];
    let lastPaint = -Infinity, activeUntil = performance.now() + 4800;
    let pointer = null, trail = [], pulses = [];

    function resize() {
      const bounds = stage.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return false;
      if (width !== bounds.width || height !== bounds.height) {
        width = bounds.width; height = bounds.height;
        const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
        canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
        context.setTransform(dpr, 0, 0, dpr, 0, 0);
        grid = cells(width, height); fallback(width, height);
      }
      return true;
    }
    function draw(now) {
      const still = quiet();
      const light = root.dataset.theme === 'light';
      context.clearRect(0, 0, width, height);
      pulses = still ? [] : pulses.filter(p => now - p.time < 1900);
      trail = still ? [] : trail.filter(p => now - p.time < 650);
      for (const cell of grid) {
        let hover = 0, ring = 0, dx = 0, dy = 0;
        if (!still) {
          for (const point of trail) {
            const distance = Math.hypot(cell.x-point.x, cell.y-point.y);
            hover = Math.max(hover, Math.max(0, 1-distance/135) * (1-(now-point.time)/650));
          }
          if (pointer) hover = Math.max(hover, Math.max(0, 1-Math.hypot(cell.x-pointer.x,cell.y-pointer.y)/135));
          for (const pulse of pulses) {
            const age = (now-pulse.time)/1000;
            const distance = Math.hypot(cell.x-pulse.x,cell.y-pulse.y);
            const wave = Math.max(0,1-Math.abs(distance-age*280)/46) * Math.exp(-age*1.3);
            ring = Math.min(1,ring+wave);
            dx += (cell.x-pulse.x)/Math.max(1,distance) * wave * 14;
            dy += (cell.y-pulse.y)/Math.max(1,distance) * wave * 14;
          }
        }
        if (!cell.on && hover < .32 && ring < .12) continue;
        const twinkle = still ? .82 : .72 + Math.sin(now*.0011+cell.phase)*.22;
        // Keep the centered prompt legible without a panel over the reference field.
        const middle = Math.abs(cell.x/width-.5)<.29 && Math.abs(cell.y/height-.48)<.13;
        const alpha = Math.min(.95,cell.alpha*twinkle*(middle?.32:1)+hover*.52+ring*.6);
        const size = cell.size * (1+hover*.13+ring*.12);
        context.fillStyle = light ? `rgba(124,59,181,${alpha*.72})` : `rgba(${Math.round(145+ring*60)},${Math.round(39+hover*55)},${Math.round(204+ring*35)},${alpha})`;
        context.fillRect(cell.x-size/2+dx,cell.y-size/2+dy,size,size);
      }
      $('vault-art').dataset.renderer = 'canvas';
    }
    function render(now) {
      frame = 0;
      if (disposed || !visible() || !resize()) return;
      if (now-lastPaint >= 32 || quiet()) { draw(now); lastPaint=now; }
      if (!quiet() && (now<activeUntil || pulses.length || trail.length)) frame=requestAnimationFrame(render);
    }
    function wake() {
      if (disposed) return;
      if (!visible()) { cancelAnimationFrame(frame); frame=0; return; }
      lastPaint=-Infinity;
      if (!frame) frame=requestAnimationFrame(render);
    }
    function point(event) {
      const bounds=stage.getBoundingClientRect();
      return { x:event.clientX-bounds.left, y:event.clientY-bounds.top, time:performance.now() };
    }
    function move(event) {
      if (!visible() || quiet() || event.pointerType==='touch') return;
      const current=point(event);
      if (pointer) { trail.push({...pointer,time:current.time}); if(trail.length>10) trail.shift(); }
      pointer=current; activeUntil=current.time+2600; wake();
    }
    function leave() { pointer=null; wake(); }
    function pulse(event) {
      if (!visible() || quiet() || event.target.closest('button,input,a,summary')) return;
      const current=point(event); pulses.push(current);
      if (pulses.length>6) pulses.shift();
      activeUntil=current.time+2800; wake();
    }
    function keyboard(event) {
      if (!['Enter',' '].includes(event.key)) return;
      event.preventDefault();
      if (quiet() || !visible()) return;
      const time=performance.now();
      pulses.push({x:width*.5,y:height*.48,time});
      if (pulses.length>6) pulses.shift();
      activeUntil=time+2800; wake();
    }
    stage.addEventListener('pointermove',move,{passive:true});
    stage.addEventListener('pointerleave',leave);
    stage.addEventListener('click',pulse);
    surface.addEventListener('keydown',keyboard);
    const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(wake);
    observer?.observe(stage);
    window.addEventListener('resize',wake,{passive:true});
    return { wake, reset() { grid=cells(width||1000,height||560); activeUntil=performance.now()+2200; wake(); }, dispose() {
      disposed=true; cancelAnimationFrame(frame); observer?.disconnect();
      stage.removeEventListener('pointermove',move); stage.removeEventListener('pointerleave',leave); stage.removeEventListener('click',pulse);
      surface.removeEventListener('keydown',keyboard); window.removeEventListener('resize',wake);
    }};
  }
  function start() {
    if (!visible() || renderer) return;
    try { renderer=createField($('vault-canvas')); } catch (_) { $('vault-art').dataset.renderer='fallback'; }
    renderer?.wake();
  }
  function refresh() { fallback(); syncControls(); start(); renderer?.wake(); }
  function init() {
    if (loaded || !$('vault-canvas')) return;
    loaded=true;
    $('vault-collection-btn').addEventListener('click',()=>showView('collection'));
    $('vault-review-btn').addEventListener('click',()=>showView('review',true));
    $('vault-shuffle').addEventListener('click',()=>{ seed++; fallback(); renderer?.reset(); });
    $('vault-pause').addEventListener('click',()=>{
      if(reduced()) return;
      paused=!paused;
      try { localStorage.setItem('steam-organizer-particles-paused',String(paused)); } catch (_) {}
      syncControls(); renderer?.reset();
    });
    $('quick-theme-btn').addEventListener('click',()=>queueMicrotask(refresh));
    $('theme-btn').addEventListener('click',()=>queueMicrotask(refresh));
    window.matchMedia('(prefers-color-scheme: light)').addEventListener?.('change',()=>queueMicrotask(refresh));
    window.addEventListener('organizer-state-change',queueSync);
    window.addEventListener('organizer-preview-ready',()=>{ sync(); showView('review'); });
    window.addEventListener('organizer-appearance-change',()=>{ queueSync(); refresh(); });
    window.addEventListener('organizer-motion-change',refresh);
    document.addEventListener('visibilitychange',()=>renderer?.wake());
    window.addEventListener('pagehide',()=>{ renderer?.dispose(); renderer=null; });
    window.addEventListener('pageshow',start);
    sync(); showView('collection'); refresh();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init,{once:true}); else init();
})();
