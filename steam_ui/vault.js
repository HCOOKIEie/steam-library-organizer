/* Original library carousel. Native DOM, finite spring motion, no runtime dependency. */
(() => {
  const root = document.documentElement, $ = id => document.getElementById(id);
  const api = (...args) => window.organizerLocalBridge.request(...args);
  let games = [], filtered = [], index = 0, position = 0, target = 0, velocity = 0;
  let frame = 0, last = 0, loading = false, loaded = false, requestId = 0;
  let identity = {}, cards = [], drag = null, wheelSum = 0, lockedUntil = 0, lastWheel = 0, selectedId = null, suppressUntil = 0;
  const images = new Map(), coverUrls = new Map();
  const visible = () => root.dataset.appearance === 'vault' && root.dataset.vaultView !== 'review' && !document.hidden && !document.querySelector('dialog[open]');
  const quiet = () => root.dataset.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches;
  const wrap = (value, length) => length ? ((value % length) + length) % length : 0;
  const radiance = (() => {
    let context = null, raf = 0, phase = 0, previous = 0, painted = -Infinity, burst = 0;
    let width = 0, height = 0, px = 0, py = 0, tx = 0, ty = 0, paused = false;
    try { paused = localStorage.getItem('steam-organizer-radiance-paused') === 'true'; } catch (_) {}
    const hash = n => { const value = Math.sin(n * 127.1 + 91.3) * 43758.54; return value - Math.floor(value); };
    function cancel() { cancelAnimationFrame(raf); raf = 0; previous = 0; }
    function draw(now) {
      raf = 0;
      if (!context || !visible()) { previous = 0; return; }
      const still = quiet() || paused;
      if (!still && now - painted < 32) { raf = requestAnimationFrame(draw); return; }
      const dt = previous ? Math.min(50, Math.max(0, now - previous)) : 16;
      previous = now; painted = now;
      if (!still) { phase += dt * .001; burst *= Math.exp(-dt / 240); }
      else burst = 0;
      const canvas = $('orbit-radiance'), box = canvas.getBoundingClientRect();
      const w = box.width || 700, h = box.height || 450, dpr = Math.min(devicePixelRatio || 1, 1.5);
      if (w !== width || h !== height) { width = w; height = h; canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
      context.setTransform(dpr, 0, 0, dpr, 0, 0); context.clearRect(0, 0, w, h);
      const follow = still ? 1 : 1 - Math.exp(-dt / 100);
      px += (tx - px) * follow; py += (ty - py) * follow;
      const cx = w * .5 + px * 12, cy = h * .495 + py * 7;
      const radius = Math.min(w * .23, h * .34), light = root.dataset.theme === 'light';
      // Four independently phased bands: sparse long filaments, shorter bright
      // packets and a few off-axis streaks. No shared-source HALOFLUX geometry.
      for (let band = 0; band < 4; band++) {
        context.beginPath();
        for (let i = 0; i < 44; i++) {
          const id = band * 44 + i, seed = hash(id), cycle = (phase * (.15 + hash(id + 350) * .26) + seed) % 1;
          const angle = seed * Math.PI * 2 + Math.sin(phase * .11 + id) * .018 + position * .025;
          const reach = radius * (1.2 + hash(id + 900) * 1.5), travel = cycle * reach;
          const start = radius + travel, length = 8 + hash(id + 70) * (band === 0 ? 90 : 46) + burst * 55;
          const bend = Math.sin(angle * 3 + phase * .18) * 5 + px * travel * .045;
          const x = Math.cos(angle), y = Math.sin(angle) * .79;
          context.moveTo(cx + x * start, cy + y * start + bend);
          context.lineTo(cx + x * (start + length), cy + y * (start + length) + bend);
        }
        context.strokeStyle = light ? ['#6486a650','#476f9d75','#6c92bc48','#49688640'][band] : ['#b8d9ff70','#e8f4ffc0','#8cbded60','#d9eaff45'][band];
        context.lineWidth = (band === 1 ? 1.1 : .55) + burst * .35; context.stroke();
      }
      context.beginPath();
      context.arc(cx, cy, radius * (1.02 + burst * .12), 0, Math.PI * 2);
      context.strokeStyle = light ? '#557da650' : '#b8d9ff75'; context.lineWidth = 1 + burst; context.stroke();
      if (!still) raf = requestAnimationFrame(draw);
    }
    function sync() {
      cancel();
      const button = $('orbit-radiance-pause'); if (!button) return;
      button.disabled = quiet() || !context;
      button.setAttribute('aria-pressed', String(paused || quiet() || !context));
      button.textContent = quiet() ? '光束静态' : !context ? '静态光束' : paused ? '继续光束' : '暂停光束';
      if (visible() && context) { painted = -Infinity; raf = requestAnimationFrame(draw); }
    }
    return {
      init() {
        if (typeof CanvasRenderingContext2D !== 'undefined') {
          try { context = $('orbit-radiance').getContext('2d', { alpha: true }); } catch (_) {}
        }
        if (context) $('orbit-wheel').dataset.radiance = 'canvas';
        $('orbit-radiance-pause').addEventListener('click', () => {
          paused = !paused;
          try { localStorage.setItem('steam-organizer-radiance-paused', String(paused)); } catch (_) {}
          sync();
        });
        $('orbit-wheel').addEventListener('pointermove', event => {
          if (quiet() || paused) return;
          const rect = $('orbit-wheel').getBoundingClientRect();
          tx = Math.max(-1, Math.min(1, (event.clientX - rect.left) / Math.max(rect.width, 1) * 2 - 1));
          ty = Math.max(-1, Math.min(1, (event.clientY - rect.top) / Math.max(rect.height, 1) * 2 - 1));
        }, { passive: true });
        $('orbit-wheel').addEventListener('pointerleave', () => { tx = ty = 0; });
        sync();
      },
      sync, cancel,
      bump() { if (!quiet() && !paused) { burst = 1; if (!raf && visible()) raf = requestAnimationFrame(draw); } },
    };
  })();
  function stop() { cancelAnimationFrame(frame); frame = 0; last = 0; }
  function detail() {
    const game = filtered[wrap(index, filtered.length)];
    $('orbit-manage').disabled = !game;
    $('orbit-prev').disabled = $('orbit-next').disabled = $('vault-shuffle').disabled = filtered.length < 2;
    $('orbit-total').textContent = `${games.length} 个游戏`;
    $('orbit-count').textContent = `${filtered.length} 项`;
    $('orbit-index').textContent = game ? `${String(wrap(index, filtered.length) + 1).padStart(2, '0')} / ${filtered.length}` : '—';
    $('orbit-title').textContent = game?.name || (games.length ? '没有匹配的游戏' : '游戏库为空');
    $('orbit-meta').textContent = game ? `${game.source} · ${game.installed ? '已安装' : game.source === 'Steam' ? '未安装' : '本机游戏'}${game.steam_minutes != null ? ` · ${(game.steam_minutes / 60).toLocaleString('zh-CN', { maximumFractionDigits: 1 })} 小时` : ''}` : '调整筛选，或导入本机游戏。';
    $('orbit-tags').replaceChildren(...(game?.tags || []).slice(0, 4).map(tag => { const span = document.createElement('span'); span.textContent = tag; return span; }));
    selectedId = game?.id || null;
  }
  function makeCards() {
    cards = [];
    const container = $('orbit-cards'); container.replaceChildren();
    if (!filtered.length) return;
    const n = Math.min(filtered.length, 7), begin = -Math.floor(n / 2);
    for (let offset = begin; offset < begin + n; offset++) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'orbit-card';
      const art = document.createElement('span'); art.className = 'orbit-card-art';
      const number = document.createElement('span'); number.className = 'orbit-card-number';
      const monogram = document.createElement('span'); monogram.className = 'orbit-monogram';
      const name = document.createElement('span'); name.className = 'orbit-card-name';
      art.append(number, monogram); button.append(art, name);
      const item = { button, art, number, monogram, name, offset, id: null };
      button.addEventListener('click', () => { if (drag?.moved || performance.now() < suppressUntil) return; choose(Math.round(position) + item.offset); $('orbit-wheel').focus({ preventScroll: true }); });
      container.append(button); cards.push(item);
    }
  }
  function cardData(item, game) {
    if (item.id === game.id) return;
    item.id = game.id; item.button.setAttribute('aria-label', `选择 ${game.name}`);
    item.name.textContent = game.name; item.monogram.textContent = [...game.name].filter(c => /[\p{L}\p{N}]/u.test(c)).slice(0, 2).join('').toUpperCase() || 'GAME';
    item.number.textContent = `LIBRARY / ${String(filtered.indexOf(game) + 1).padStart(3, '0')}`;
    item.art.querySelector('img')?.remove();
    item.button.classList.remove('has-cover');
    // Only public Steam cover URLs derived from real catalog app IDs. Failures
    // leave a deliberate typographic cover; no unrelated or generated artwork.
    if ($('demo-badge').hidden && game.source === 'Steam' && Number.isInteger(game.appid) && game.appid > 0 && images.get(game.id) !== false) {
      const image = document.createElement('img'); image.alt = ''; image.draggable = false;
      image.decoding = 'async'; image.referrerPolicy = 'no-referrer';
      image.onload = () => { images.set(game.id, true); if (item.id === game.id) item.button.classList.add('has-cover'); };
      image.onerror = async () => {
        image.onerror = () => { images.set(game.id, false); image.remove(); };
        try {
          let resolved = coverUrls.get(game.id);
          if (!resolved || resolved === true) {
            resolved = api('/api/library/cover', { ...identity, id: game.id }); coverUrls.set(game.id, resolved);
          }
          const result = await resolved; coverUrls.set(game.id, result);
          if (result?.url && /^https:\/\/shared\.(akamai|fastly)\.steamstatic\.com\//.test(result.url)) image.src = result.url;
          else { images.set(game.id, false); image.remove(); }
        } catch (_) { images.set(game.id, false); image.remove(); }
      };
      image.src = coverUrls.get(game.id)?.url || `https://shared.akamai.steamstatic.com/steam/apps/${game.appid}/library_600x900.jpg`;
      item.art.append(image);
    }
  }
  function paint() {
    const width = $('orbit-wheel').clientWidth || 600;
    const radius = Math.min(320, width * .49), step = .48, base = Math.round(position);
    for (const card of cards) {
      const itemIndex = wrap(base + card.offset, filtered.length), game = filtered[itemIndex];
      if (!game) continue;
      cardData(card, game);
      const distance = base + card.offset - position, angle = distance * step;
      const x = Math.sin(angle) * radius, depth = Math.cos(angle), scale = .64 + .36 * depth;
      card.button.style.transform = `translate(-50%, -50%) translate3d(${x.toFixed(2)}px, ${(25 * (1 - depth)).toFixed(2)}px, ${(depth * 85).toFixed(2)}px) rotateY(${(-angle * 25).toFixed(2)}deg) scale(${scale.toFixed(3)})`;
      card.button.style.opacity = String(Math.max(.22, 1 - Math.abs(distance) * .21));
      card.button.style.zIndex = String(20 - Math.round(Math.abs(distance) * 3));
      const active = game.id === selectedId;
      card.button.classList.toggle('is-active', active); card.button.setAttribute('aria-pressed', String(active));
      card.button.tabIndex = active ? 0 : -1;
    }
    $('orbit-wheel').style.setProperty('--orbit-turn', `${(position * 7).toFixed(2)}deg`);
  }
  function tick(now) {
    frame = 0;
    if (!visible()) { position = target; velocity = 0; last = 0; paint(); return; }
    const dt = Math.min(.032, Math.max(.001, last ? (now - last) / 1000 : .016)); last = now;
    velocity += ((target - position) * 155 - velocity * 22) * dt;
    position += velocity * dt;
    if (Math.abs(target - position) < .0008 && Math.abs(velocity) < .004) { position = target; velocity = 0; last = 0; }
    paint();
    if (velocity || position !== target) frame = requestAnimationFrame(tick);
  }
  function choose(next, jump = false) {
    if (!filtered.length) return;
    index = next; target = next;
    radiance.bump();
    if (jump || Math.abs(target - position) > 4) { position = target - Math.sign(target - position) * 1.1; velocity = 0; }
    detail();
    if (quiet() || !visible()) { stop(); position = target; velocity = 0; paint(); }
    else if (!frame) frame = requestAnimationFrame(tick);
  }
  function filter() {
    stop(); const query = $('orbit-search').value.trim().toLocaleLowerCase();
    filtered = games.filter(game => (!query || game.name.toLocaleLowerCase().includes(query)) && (!$('orbit-installed').checked || game.installed));
    index = position = target = 0; velocity = 0; makeCards(); detail(); paint();
  }
  async function load(force = false) {
    if (loading || (loaded && !force) || !visible() || $('stat-scope').textContent === '—') return;
    const id = ++requestId; loading = true;
    $('orbit-status').textContent = '正在读取本机游戏库…'; $('orbit-retry').hidden = true;
    try {
      const data = await api('/api/library/load', {}); if (id !== requestId) return;
      identity = { account: data.account, revision: data.revision };
      games = (data.games || []).filter(game => !game.form || game.form === 'game').sort((a, b) => Number(!!b.installed) - Number(!!a.installed) || (b.steam_minutes || 0) - (a.steam_minutes || 0));
      loaded = true; filter(); $('orbit-status').textContent = '';
    } catch (error) { $('orbit-title').textContent = '未读取到游戏库'; $('orbit-status').textContent = error.message; $('orbit-retry').hidden = false; }
    finally { loading = false; }
  }
  function sync() {
    const generated = $('preview-badge').textContent !== '尚未生成';
    $('vault-review-btn').disabled = !generated;
    const count = document.querySelectorAll('#groups .group').length; $('vault-plan-count').textContent = count ? String(count) : '';
    if (!generated && root.dataset.vaultView === 'review') view('collection');
  }
  function view(next, focus = false) {
    const review = next === 'review' && !$('vault-review-btn').disabled;
    root.dataset.vaultView = review ? 'review' : 'collection';
    $('vault-collection-btn').setAttribute('aria-pressed', String(!review)); $('vault-review-btn').setAttribute('aria-pressed', String(review));
    $('vault-view-title').textContent = review ? '分类预览' : '游戏库';
    if (review) { stop(); if (focus) $('preview-search').focus({ preventScroll: true }); } else load();
    radiance.sync();
  }
  function init() {
    $('orbit-prev').addEventListener('click', () => choose(index - 1));
    $('orbit-next').addEventListener('click', () => choose(index + 1));
    $('vault-shuffle').addEventListener('click', () => choose(index + 1 + Math.floor(Math.random() * Math.max(1, filtered.length - 1)), true));
    $('orbit-search').addEventListener('input', filter); $('orbit-installed').addEventListener('change', filter);
    $('orbit-retry').addEventListener('click', () => load(true));
    $('orbit-manage').addEventListener('click', () => { const game = filtered[wrap(index, filtered.length)]; if (game) window.organizerLibrary?.open({ query: game.name }); });
    const wheel = $('orbit-wheel');
    wheel.addEventListener('keydown', event => {
      if (event.target !== wheel && !event.target.classList.contains('orbit-card')) return;
      if (['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Enter'].includes(event.key)) {
        event.preventDefault();
        if (event.key === 'Enter') $('orbit-manage').click();
        else choose(event.key === 'Home' ? 0 : event.key === 'End' ? filtered.length - 1 : index + (event.key === 'ArrowLeft' ? -1 : 1));
      }
    });
    wheel.addEventListener('wheel', event => {
      if (!visible() || filtered.length < 2) return;
      event.preventDefault(); const now = performance.now(), delta = (Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY) * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 400 : 1);
      if (now < lockedUntil) return;
      if (now - lastWheel > 200 || Math.sign(delta) !== Math.sign(wheelSum)) wheelSum = 0;
      lastWheel = now; wheelSum += delta;
      if (Math.abs(wheelSum) >= 60) { choose(index + Math.sign(wheelSum)); wheelSum = 0; lockedUntil = now + 440; }
    }, { passive: false });
    wheel.addEventListener('pointerdown', event => { if (event.button !== 0) return; drag = { x: event.clientX, y: event.clientY, base: target, moved: false }; });
    wheel.addEventListener('pointermove', event => {
      if (!drag || !filtered.length) return;
      const dx = event.clientX - drag.x;
      if (Math.abs(dx) > 14 && Math.abs(dx) > Math.abs(event.clientY - drag.y)) {
        if (!drag.moved) { drag.moved = true; wheel.setPointerCapture?.(event.pointerId); }
        stop(); velocity = 0; position = drag.base - dx / 120;
        index = Math.round(position); detail(); paint(); wheel.classList.add('is-dragging');
      }
    });
    const release = event => {
      if (!drag) return;
      if (drag.moved) { suppressUntil = performance.now() + 250; choose(event.type === 'pointercancel' ? drag.base : Math.round(position)); }
      wheel.classList.remove('is-dragging'); if (wheel.hasPointerCapture?.(event.pointerId)) wheel.releasePointerCapture(event.pointerId);
      const finished = drag; setTimeout(() => { if (drag === finished) drag = null; }, 0);
    };
    wheel.addEventListener('pointerup', release); wheel.addEventListener('pointercancel', release); wheel.addEventListener('lostpointercapture', () => wheel.classList.remove('is-dragging'));
    $('vault-collection-btn').addEventListener('click', () => view('collection')); $('vault-review-btn').addEventListener('click', () => view('review', true));
    window.addEventListener('organizer-preview-ready', () => { sync(); view('review'); });
    window.addEventListener('organizer-state-change', () => { sync(); if (!visible()) stop(); else load(); radiance.sync(); });
    window.addEventListener('organizer-appearance-change', () => { if (!visible()) stop(); else { paint(); load(); } radiance.sync(); });
    window.addEventListener('organizer-motion-change', () => { stop(); position = target; velocity = 0; paint(); radiance.sync(); });
    document.addEventListener('visibilitychange', () => { stop(); position = target; velocity = 0; paint(); radiance.sync(); });
    window.addEventListener('resize', () => { if (visible()) paint(); radiance.sync(); }, { passive: true });
    window.addEventListener('pagehide', () => { stop(); radiance.cancel(); });
    document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('close', () => radiance.sync()));
    for (const id of ['quick-theme-btn', 'theme-btn']) $(id).addEventListener('click', () => queueMicrotask(() => radiance.sync()));
    $('refresh-btn').addEventListener('click', () => { loaded = false; setTimeout(() => load(true), 300); });
    radiance.init(); sync(); view('collection');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
})();
