/* UI state regressions run without a browser, network, or real Steam data. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { JSDOM } = require('jsdom');

const ui = path.join(__dirname, '..', 'steam_ui');
const html = fs.readFileSync(path.join(ui, 'index.html'), 'utf8');
const script = fs.readFileSync(path.join(ui, 'app.js'), 'utf8');
const groups = [
  { id: 'initial:A', mode: 'initial', name: '首字母 · A', count: 2, appids: [1, 2], sample: ['Alpha', 'Another Game'] },
  { id: 'initial:B', mode: 'initial', name: '首字母 · B', count: 1, appids: [3], sample: ['Beta'] },
  { id: 'genre:action', mode: 'genre', name: '类型 · 动作', count: 2, appids: [1, 3], sample: ['Alpha', 'Beta'] },
];
const serverState = () => ({
  steam_root: 'C:\\Example\\Steam', steamid64: '76561198000000001', steam_running: false,
  counts: { library: 3, games: 3, all: 4, installed: 2, unresolved: 0 },
  scopes: { library: 3, games: 3, all: 4 }, collections: [], csrf_token: 'test', appinfo_error: null,
});
const settle = () => new Promise(resolve => setImmediate(resolve));

async function setup(t, { getState, makePlan, apply, preferences, theme, appearance, motion, particlesPaused, personaPaused, canvas = false, systemReducedMotion = false, unavailableStorage } = {}) {
  const dom = new JSDOM(html, { url: 'https://organizer.test/', runScripts: 'outside-only', pretendToBeVisual: true });
  t.after(() => dom.window.close());
  const { window } = dom;
  let animation;
  if (canvas) {
    let time = 0, next = 0;
    const frames = new Map(), rects = [], arcs = [], fills = [], strokes = [], waterFrames = [], observed = new Set();
    window.CanvasRenderingContext2D = function () {};
    window.IntersectionObserver = class {
      constructor(callback) { this.callback=callback; }
      observe(element) { observed.add(element); }
      disconnect() { observed.clear(); }
    };
    window.HTMLCanvasElement.prototype.getContext = function () {
      if (this.classList.contains('persona-water')) return {
        createImageData: (w,h) => ({ data: new Uint8ClampedArray(w*h*4) }),
        putImageData(pixels) { let checksum=0; for(let i=0;i<pixels.data.length;i+=67) checksum+=pixels.data[i]; waterFrames.push(checksum); },
      };
      return ({ setTransform() {}, clearRect() { rects.length = 0; arcs.length = 0; fills.length = 0; strokes.length = 0; }, fillRect(...rect) { rects.push(rect); }, arc(...arc) { arcs.push(arc); }, beginPath() {}, stroke() { strokes.push({ width: this.lineWidth, color: this.strokeStyle }); }, fill() { fills.push(1); }, save() {}, restore() {}, translate() {}, rotate() {}, moveTo() {}, lineTo() {}, closePath() {} }); };
    window.document.getElementById('persona-art').getBoundingClientRect = () => ({ width: 420, height: 300, left: 0, top: 0 });
    window.document.querySelector('.persona-hero').getBoundingClientRect = () => ({ width: 900, height: 300, left: 0, top: 0, bottom: 300 });
    window.document.querySelector('.stage').getBoundingClientRect = () => ({ width: 900, height: 500, left: 0, top: 0, bottom: 500 });
    window.performance.now = () => time;
    window.requestAnimationFrame = callback => { frames.set(++next, callback); return next; };
    window.cancelAnimationFrame = id => frames.delete(id);
    animation = { rects, arcs, fills, strokes, waterFrames, observed, pending: () => frames.size, step(ms) { time = ms; const batch = [...frames.values()]; frames.clear(); batch.forEach(callback => callback(time)); } };
  }
  window.matchMedia = query => ({ matches: query.includes('prefers-reduced-motion') ? systemReducedMotion : query.includes('prefers-color-scheme: light') || query.includes('(hover: hover)'), addEventListener() {} });
  if (unavailableStorage) Object.defineProperty(window, 'localStorage', { get() { throw new Error('Storage unavailable'); } });
  else {
    if (preferences !== undefined) window.localStorage.setItem('steam-organizer-preferences-v1', preferences);
    if (theme) window.localStorage.setItem('steam-organizer-theme', theme);
    if (appearance) window.localStorage.setItem('steam-organizer-appearance', appearance);
    if (motion) window.localStorage.setItem('steam-organizer-motion', motion);
    if (particlesPaused) window.localStorage.setItem('steam-organizer-particles-paused', 'true');
    if (personaPaused) window.localStorage.setItem('steam-organizer-persona-paused', 'true');
  }
  window.pywebview = { api: {
    get_state: getState || (async () => serverState()),
    make_plan: makePlan || (async () => ({ plan_id: 'example-plan', groups, summary: {} })),
    apply: apply || (async () => { throw new Error('Test writes are disabled'); }),
  }};
  window.eval(fs.readFileSync(path.join(ui, 'theme-bootstrap.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ui, 'appearance.js'), 'utf8'));
  window.eval(script);
  window.eval(fs.readFileSync(path.join(ui, 'vault.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ui, 'persona-motion.js'), 'utf8'));
  window.eval('boot()');
  await settle();
  const $ = id => window.document.getElementById(id);
  const run = source => window.eval(source);
  const plan = async () => { await run('makePlan()'); await settle(); };
  return { window, $, run, plan, animation };
}

test('initial scan enables preview, masks the account, and keeps write hidden', async t => {
  const { $, window } = await setup(t);
  assert.equal($('plan-btn').disabled, false);
  assert.equal($('apply-btn').hidden, true);
  assert.equal($('stat-scope').textContent, '3');
  assert.ok(!$('account-line').textContent.includes('76561198000000001'));
  assert.equal(window.document.querySelector('[aria-current="step"]').dataset.step, '2');
});

test('presets update rules, invalidate the preview, and survive reload', async t => {
  const first = await setup(t);
  await first.plan();
  first.window.document.querySelector('[data-preset="habits"]').click();
  assert.equal(first.$('apply-btn').hidden, true);
  assert.equal(first.$('stale-banner').hidden, false);
  const preferences = first.window.localStorage.getItem('steam-organizer-preferences-v1');
  assert.deepEqual(JSON.parse(preferences).modes, ['recent', 'playtime']);
  const second = await setup(t, { preferences });
  assert.equal(second.window.document.querySelector('[data-preset="habits"]').getAttribute('aria-pressed'), 'true');
  assert.equal(second.window.document.querySelector('[data-mode="recent"]').getAttribute('aria-pressed'), 'true');
});

test('search shows an empty result and bulk selection preserves hidden rows', async t => {
  const { $, window, run, plan } = await setup(t);
  await plan();
  $('preview-search').value = 'Another Game';
  run('filterPreview()');
  assert.equal($('search-result-count').textContent, '1 / 3 个分类');
  assert.equal(window.document.querySelector('[data-id="initial:B"]').hidden, true);
  $('select-none').click();
  assert.equal($('preview-groups').textContent, '2');
  assert.equal(window.document.querySelector('[data-id="initial:B"] input').checked, true);
  $('preview-search').value = 'no-such-game';
  run('filterPreview()');
  assert.equal($('search-empty').hidden, false);
  assert.equal($('select-all').disabled, true);
  $('clear-search-btn').click();
  assert.equal($('search-empty').hidden, true);
  assert.equal($('preview-search').value, '');
  assert.equal(window.document.querySelector('[data-id="initial:B"]').hidden, false);
  assert.equal($('preview-groups').textContent, '2');
});

test('section selection affects only matching results and updates indeterminate state', async t => {
  const { $, window, run, plan } = await setup(t);
  await plan();
  $('preview-search').value = 'Another Game';
  run('filterPreview()');
  window.document.querySelector('.mode-checkbox').click();
  assert.equal($('preview-groups').textContent, '2');
  $('preview-search').value = '';
  run('filterPreview()');
  assert.equal(window.document.querySelector('.mode-checkbox').indeterminate, true);
});

test('a failed regeneration cannot reactivate the previous plan', async t => {
  let fail = false;
  const { $, run, plan } = await setup(t, { makePlan: async () => {
    if (fail) throw new Error('Metadata refresh failed');
    return { plan_id: 'old-plan', groups, summary: {} };
  }});
  await plan();
  assert.equal($('apply-btn').disabled, false);
  fail = true;
  await plan();
  assert.equal($('apply-btn').disabled, true);
  assert.equal($('stale-banner').hidden, false);
  run('syncPlanFreshness()');
  assert.equal($('apply-btn').disabled, true);
});

test('manual rescan invalidates a plan even when settings match', async t => {
  const { $, run, plan } = await setup(t);
  await plan();
  await run('refreshState()');
  assert.equal($('apply-btn').disabled, true);
  assert.equal($('stale-banner').hidden, false);
});

test('invalid scan data exposes recovery and blocks preview generation', async t => {
  const { $ } = await setup(t, { getState: async () => ({}) });
  assert.equal($('connection-error').hidden, false);
  assert.equal($('plan-btn').disabled, true);
  assert.equal($('connect-steam-btn').disabled, false);
  assert.match($('connection-error-copy').textContent, /有效的 Steam 数据/);
});

test('empty P5R plans show the recovery view without offering a write', async t => {
  const { $, plan } = await setup(t, { appearance: 'p5r', makePlan: async () => ({ plan_id: 'empty', groups: [], summary: {} }) });
  await plan();
  assert.equal($('preview-panel').classList.contains('has-preview'), true);
  assert.equal($('preview-empty').hidden, false);
  assert.equal($('apply-btn').hidden, true);
  assert.match($('empty-title').textContent, /没有可分类/);
  assert.match($('action-title').textContent, /没有可用分类/);
});

test('startup tolerates invalid preferences and unavailable storage', async t => {
  const malformed = await setup(t, { preferences: 'not-json' });
  assert.equal(malformed.$('plan-btn').disabled, false);
  const unavailable = await setup(t, { unavailableStorage: true });
  assert.equal(unavailable.$('plan-btn').disabled, false);
  await unavailable.plan();
  assert.equal(unavailable.$('apply-btn').disabled, false);
});

test('scan and configuration actions cannot overlap a write', async t => {
  let scans = 0;
  const { $, run, plan } = await setup(t, {
    getState: async () => { scans++; return serverState(); },
    apply: () => new Promise(() => {}),
  });
  await plan();
  const scansBefore = scans;
  $('apply-btn').click();
  $('sheet-confirm').click();
  await run('refreshState(true)');
  assert.equal(scans, scansBefore);
  assert.equal($('plan-btn').disabled, true);
  assert.equal($('connect-steam-btn').disabled, true);
  assert.equal($('select-none').disabled, true);
});

test('theme switches persist and Steam running state blocks writes', async t => {
  const { $, window, plan } = await setup(t, { theme: 'light', getState: async () => ({ ...serverState(), steam_running: true }) });
  $('quick-theme-btn').click();
  assert.equal(window.document.documentElement.dataset.theme, 'dark');
  assert.equal(window.localStorage.getItem('steam-organizer-theme'), 'dark');
  await plan();
  assert.equal($('apply-btn').disabled, true);
  assert.match($('apply-btn').textContent, /退出 Steam/);
});

test('review remains the active step until a write actually starts', async t => {
  const { $, window, plan } = await setup(t, { apply: () => new Promise(() => {}) });
  await plan();
  assert.equal(window.document.querySelector('[aria-current="step"]').dataset.step, '3');
  $('apply-btn').click();
  $('sheet-confirm').click();
  assert.equal(window.document.querySelector('[aria-current="step"]').dataset.step, '4');
});

test('the exported offline artifact boots with sample data and rejects writes', async t => {
  const project = path.resolve(__dirname, '..');
  const scratch = path.join(project, '.test-tmp');
  fs.mkdirSync(scratch, { recursive: true });
  const destination = path.join(scratch, 'ui-integration-preview.html');
  t.after(() => { if (fs.existsSync(destination)) fs.unlinkSync(destination); });
  const exported = spawnSync('python', ['scripts/preview_ui.py', '--export', destination, '--appearance', 'p5r'], { cwd: project, encoding: 'utf8', windowsHide: true });
  assert.equal(exported.status, 0, exported.stderr);
  const previewHtml = fs.readFileSync(destination, 'utf8');
  assert.ok(!/<script[^>]+src=/.test(previewHtml));
  assert.ok(!/<link[^>]+rel="stylesheet"/.test(previewHtml));
  assert.ok(Buffer.byteLength(previewHtml, 'utf8') < 2_000_000, 'Keep the inlined desktop page below the WebView2 NavigateToString limit');
  const dom = new JSDOM(previewHtml, {
    url: 'https://offline-preview.test/', runScripts: 'dangerously', pretendToBeVisual: true,
    beforeParse(window) {
      window.matchMedia = () => ({ matches: true, addEventListener() {} });
      window.structuredClone = structuredClone;
    },
  });
  t.after(() => dom.window.close());
  await settle();
  assert.equal(dom.window.document.documentElement.dataset.appearance, 'p5r');
  assert.equal(dom.window.document.getElementById('demo-badge').hidden, false);
  assert.ok(dom.window.document.querySelector('style[data-source="p3r.css"]'));
  assert.ok(dom.window.document.querySelector('style[data-source="p5r.css"]'));
  assert.ok(dom.window.document.querySelector('style[data-source="p5r.css"]').textContent.includes('data:font/ttf;base64,'));
  const reloadCss = dom.window.document.querySelector('style[data-source="p3r.css"]').textContent;
  assert.ok(reloadCss.includes('data:font/ttf;base64,'), 'The upright P3R font is embedded offline');
  assert.ok(reloadCss.includes('The Anton Project Authors'), 'Include the font license with the embedded copy');
  assert.ok(dom.window.document.querySelector('style[data-source="persona-motion.css"]'));
  assert.ok(dom.window.document.querySelector('script[data-source="persona-motion.js"]'));
  assert.equal((previewHtml.match(/data:image\/webp;base64,/g) || []).length, 2, 'Both character cutouts work offline');
  assert.ok(!previewHtml.includes("url('art/"));
  assert.equal(dom.window.document.querySelector('[data-appearance="traces"]'), null);
  assert.ok(dom.window.document.querySelector('style[data-source="vault.css"]'));
  assert.equal(dom.window.document.querySelector('.p3r-scene img'), null);
  assert.equal(dom.window.document.getElementById('stat-scope').textContent, '24');
  await dom.window.eval('makePlan()');
  assert.ok(dom.window.document.querySelectorAll('.group').length > 0);
  await assert.rejects(dom.window.pywebview.api.apply({}), /只读示例/);
});

test('Collection is the default and appearance switching preserves the live preview', async t => {
  const first = await setup(t);
  const { window, $, plan } = first;
  assert.equal(window.document.documentElement.dataset.appearance, 'vault');
  assert.equal(window.document.querySelector('.p3r-scene img'), null);
  await plan();
  window.document.querySelector('.group-checkbox').click();
  $('preview-search').value = 'Beta';
  first.run('filterPreview()');
  const selected = $('preview-groups').textContent;
  window.document.querySelector('button[data-appearance="calm"]').click();
  assert.equal(window.document.documentElement.dataset.appearance, 'calm');
  assert.equal($('preview-groups').textContent, selected);
  assert.equal($('preview-search').value, 'Beta');
  assert.equal($('apply-btn').disabled, false);
  assert.equal($('stale-banner').hidden, true);
  assert.equal(window.localStorage.getItem('steam-organizer-appearance'), 'calm');
  const second = await setup(t, { appearance: 'calm' });
  assert.equal(second.window.document.documentElement.dataset.appearance, 'calm');
  assert.equal(second.window.document.querySelector('button[data-appearance="calm"]').getAttribute('aria-pressed'), 'true');
});

test('manual reduced motion disables entrances and preview choreography', async t => {
  const { window, $, plan } = await setup(t, { motion: 'reduced' });
  const root = window.document.documentElement;
  assert.equal(root.dataset.motion, 'reduced');
  assert.equal(root.classList.contains('appearance-enter'), false);
  await plan();
  assert.equal(root.classList.contains('preview-reveal'), false);
  $('motion-btn').click();
  assert.equal(root.dataset.motion, 'full');
  assert.equal(window.localStorage.getItem('steam-organizer-motion'), 'full');
  $('motion-btn').click();
  assert.equal(root.dataset.motion, 'reduced');
  assert.equal($('motion-btn').getAttribute('aria-checked'), 'true');
});

test('P5R persists and switching all four styles keeps selections, search and plan freshness', async t => {
  const { window, $, run, plan } = await setup(t, { appearance: 'p5r', theme: 'dark' });
  const root = window.document.documentElement;
  assert.equal(root.dataset.appearance, 'p5r');
  assert.equal(window.document.querySelector('meta[name="theme-color"]').content, '#c90d25');
  assert.equal(window.document.querySelector('button[data-appearance="p5r"]').getAttribute('aria-pressed'), 'true');
  await plan();
  assert.equal(root.classList.contains('preview-reveal'), true);
  window.document.querySelector('.group-checkbox').click();
  $('preview-search').value = 'Beta';
  run('filterPreview()');
  const selection = () => Array.from(window.document.querySelectorAll('.group.is-on')).map(row => row.dataset.id);
  const selected = selection();
  for (const style of ['p3r', 'calm', 'vault', 'p5r']) {
    window.document.querySelector(`button[data-appearance="${style}"]`).click();
    assert.equal(root.dataset.appearance, style);
    assert.deepEqual(selection(), selected);
    assert.equal($('preview-search').value, 'Beta');
    assert.equal($('stale-banner').hidden, true);
    assert.equal($('apply-btn').disabled, false);
  }
  assert.equal(window.localStorage.getItem('steam-organizer-appearance'), 'p5r');
  $('quick-theme-btn').click();
  assert.equal(window.document.querySelector('meta[name="theme-color"]').content, '#e21d30');
  $('motion-btn').click();
  assert.equal(root.classList.contains('preview-reveal'), false);
  assert.equal(root.classList.contains('appearance-enter'), false);
  await plan();
  assert.equal(root.classList.contains('preview-reveal'), false);
});

test('retired TRACES preferences migrate to P5R without losing organizer settings', async t => {
  const { window, $ } = await setup(t, { appearance: 'traces', theme: 'dark', motion: 'reduced' });
  assert.equal(window.document.documentElement.dataset.appearance, 'p5r');
  assert.equal(window.localStorage.getItem('steam-organizer-appearance'), 'p5r');
  assert.equal(window.document.querySelector('button[data-appearance="p5r"]').getAttribute('aria-pressed'), 'true');
  assert.equal(window.document.querySelector('.traces-scene'), null);
  assert.equal(window.document.documentElement.classList.contains('appearance-enter'), false);
  assert.equal($('plan-btn').disabled, false);
});

test('system reduced motion takes precedence over a saved full motion preference', async t => {
  const { window, $, plan } = await setup(t, { systemReducedMotion: true, motion: 'full' });
  assert.equal(window.document.documentElement.dataset.motion, 'reduced');
  assert.equal($('motion-btn').disabled, true);
  await plan();
  assert.equal(window.document.documentElement.classList.contains('preview-reveal'), false);
});

test('full motion reveals a successful plan without changing workflow safety', async t => {
  const { window, $, plan } = await setup(t, { motion: 'full' });
  await plan();
  assert.equal(window.document.documentElement.classList.contains('preview-reveal'), true);
  assert.equal($('preview-groups').textContent, '3');
  assert.equal(window.document.querySelector('[aria-current="step"]').dataset.step, '3');
  $('motion-btn').click();
  assert.equal(window.document.documentElement.classList.contains('preview-reveal'), false);
  assert.equal($('apply-btn').disabled, false);
});

test('Collection gallery and review navigation preserve selection, search and stale-plan guards', async t => {
  const { window, $, run, plan } = await setup(t);
  const root = window.document.documentElement;
  assert.equal(root.dataset.vaultView, 'collection');
  assert.equal($('vault-review-btn').disabled, true);
  assert.ok($('vault-art-fallback').querySelectorAll('rect').length > 100);
  const original = $('vault-art-fallback').innerHTML;
  $('vault-shuffle').click();
  assert.notEqual($('vault-art-fallback').innerHTML, original);
  await plan();
  assert.equal(root.dataset.vaultView, 'review');
  assert.equal($('vault-plan-count').textContent, '3');
  window.document.querySelector('.group-checkbox').click();
  $('preview-search').value = 'Beta'; run('filterPreview()');
  const selected = $('preview-groups').textContent;
  $('vault-collection-btn').click();
  assert.equal(root.dataset.vaultView, 'collection');
  $('vault-review-btn').click();
  assert.equal(root.dataset.vaultView, 'review');
  assert.equal($('preview-search').value, 'Beta');
  assert.equal($('preview-groups').textContent, selected);
  window.document.querySelector('[data-preset="habits"]').click();
  assert.equal($('apply-btn').hidden, true);
  assert.equal($('stale-banner').hidden, false);
});

test('Collection light/dark mode and GPU-free fallback work without a rendering library', async t => {
  const { window, $ } = await setup(t, { theme: 'light', systemReducedMotion: true });
  assert.equal(window.document.querySelector('meta[name="theme-color"]').content, '#f5f3f8');
  assert.ok($('vault-art-fallback').querySelector('svg'));
  $('quick-theme-btn').click();
  assert.equal(window.document.querySelector('meta[name="theme-color"]').content, '#08080a');
  assert.equal(window.document.documentElement.dataset.motion, 'reduced');
  assert.equal($('vault-pause').disabled, true);
});

test('square particles respond to pointer and keyboard, then stop in review and on hidden pages', async t => {
  const { window, $, animation, plan } = await setup(t, { canvas: true, theme: 'dark' });
  animation.step(0);
  assert.equal($('vault-art').dataset.renderer, 'canvas');
  const resting = JSON.stringify(animation.rects);
  const stage = window.document.querySelector('.stage');
  stage.dispatchEvent(new window.MouseEvent('pointermove', { clientX: 450, clientY: 250, bubbles: true }));
  animation.step(40);
  assert.notEqual(JSON.stringify(animation.rects), resting);
  stage.dispatchEvent(new window.MouseEvent('pointerleave'));
  window.document.querySelector('.vault-exhibit').dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  animation.step(340);
  assert.ok(animation.rects.some(rect => rect[2] > 22), 'Keyboard activation produces the same square wave');
  Object.defineProperty(window.document, 'hidden', { configurable: true, value: true });
  window.document.dispatchEvent(new window.Event('visibilitychange'));
  assert.equal(animation.pending(), 0);
  Object.defineProperty(window.document, 'hidden', { configurable: true, value: false });
  window.document.dispatchEvent(new window.Event('visibilitychange'));
  assert.ok(animation.pending() > 0);
  await plan();
  assert.equal(animation.pending(), 0);
  $('vault-collection-btn').click();
  animation.step(5000);
  animation.step(7000);
  assert.equal(animation.pending(), 0, 'Idle particle field stops scheduling frames');
});

test('particle pause persists, reduced motion overrides it, and shuffle remains available', async t => {
  const { $, window, animation } = await setup(t, { canvas: true });
  $('vault-pause').click(); animation.step(10);
  assert.equal(animation.pending(), 0);
  assert.equal(window.localStorage.getItem('steam-organizer-particles-paused'), 'true');
  assert.equal($('vault-pause-label').textContent, '继续动态');
  const next = await setup(t, { canvas: true, particlesPaused: true });
  next.animation.step(0); assert.equal(next.animation.pending(), 0);
  next.$('vault-shuffle').click(); next.animation.step(40);
  assert.equal(next.animation.pending(), 0);
  next.$('motion-btn').click();
  assert.equal(next.$('vault-pause').disabled, true);
  assert.equal(next.$('vault-pause-label').textContent, '已减少动效');
});

test('P3R and P5R effects stay in the illustration and suspend when hidden or reviewing', async t => {
  for (const appearance of ['p3r', 'p5r']) {
    const { window, $, animation, plan } = await setup(t, { appearance, canvas: true });
    const root = window.document.documentElement, stage = window.document.querySelector('.stage'), art = $('persona-art');
    animation.step(0);
    assert.equal(root.dataset.personaRunning, 'true');
    assert.equal($('persona-canvas').parentElement, art);
    art.dispatchEvent(new window.MouseEvent('pointermove', { clientX: 350, clientY: 200, bubbles: true }));
    animation.step(40); animation.step(80);
    assert.ok(Number(stage.style.getPropertyValue('--persona-x')) > 0);
    if (appearance === 'p3r') assert.ok(new Set(animation.waterFrames).size > 1, 'Water refraction changes over time');
    stage.dispatchEvent(new window.MouseEvent('click', { clientX: 200, clientY: 150, bubbles: true }));
    animation.step(120);
    assert.equal(animation.strokes.length, 0, 'Clicks outside the illustration cannot paint over controls');
    art.dispatchEvent(new window.MouseEvent('click', { clientX: 200, clientY: 150, bubbles: true }));
    animation.step(160);
    if (appearance === 'p3r') {
      const hero=window.document.querySelector('.persona-hero');
      assert.equal(hero.style.clipPath, 'url(#reload-menu-reveal)');
      assert.ok(Number($('reload-reveal-a').getAttribute('r')) > 0, 'First circular window reveals the actual scene');
      assert.equal(Number($('reload-reveal-b').getAttribute('r')), 0, 'Second window starts later');
      animation.step(240);
      assert.ok(Number($('reload-reveal-b').getAttribute('r')) > 0);
      assert.ok(Number($('reload-reveal-a').getAttribute('r')) > Number($('reload-reveal-b').getAttribute('r')));
    } else assert.equal(animation.fills.length, 3, 'Black and white comic impact');
    Object.defineProperty(window.document, 'hidden', { configurable: true, value: true });
    window.document.dispatchEvent(new window.Event('visibilitychange'));
    assert.equal(animation.pending(), 0);
    assert.equal(window.document.querySelector('.persona-hero').style.clipPath, '', 'Hidden/review scenes release the reveal mask');
    assert.equal(root.dataset.personaRunning, 'false');
    Object.defineProperty(window.document, 'hidden', { configurable: true, value: false });
    window.document.dispatchEvent(new window.Event('visibilitychange'));
    animation.step(8000);
    assert.equal(animation.pending() > 0, appearance === 'p3r', 'Only water shimmer continues while the artwork is visible');
    $('persona-replay').click(); animation.step(8100);
    assert.equal(stage.classList.contains('persona-replay'), true);
    assert.ok(animation.pending() > 0);
    await plan();
    assert.equal(animation.pending(), 0);
    assert.equal(window.document.querySelector('.persona-hero').style.clipPath, '', 'Hidden/review scenes release the reveal mask');
    assert.equal(root.dataset.personaRunning, 'false');
    assert.equal($('apply-btn').disabled, false);
  }
});

test('Persona motion pause survives appearance changes and reduced motion keeps content still', async t => {
  const { window, $, animation } = await setup(t, { appearance: 'p5r', canvas: true });
  $('persona-replay').click(); $('persona-pause').click();
  const paintedWater = animation.waterFrames.length; animation.step(500);
  assert.equal(animation.waterFrames.length, paintedWater, 'Paused water stays still');
  assert.equal(animation.pending(), 0);
  assert.equal(window.document.querySelector('.stage').classList.contains('persona-replay'), false);
  assert.equal(window.localStorage.getItem('steam-organizer-persona-paused'), 'true');
  assert.equal($('persona-replay').disabled, true);
  window.document.querySelector('[data-appearance="p3r"]').click();
  assert.equal(window.document.documentElement.classList.contains('appearance-enter'), false);
  assert.equal($('persona-pause-label').textContent, '继续动效');
  const persisted = await setup(t, { appearance: 'p3r', personaPaused: true, canvas: true });
  assert.equal(persisted.window.document.documentElement.dataset.personaPaused, 'true');
  assert.equal(persisted.animation.pending(), 0);
  $('persona-pause').click(); $('motion-btn').click();
  assert.equal($('persona-pause-label').textContent, '已减少动效');
  assert.equal($('persona-pause').disabled, true);
  assert.equal(animation.pending(), 0);
});


test('P3R scene reveal finishes cleanly and respects pause/reduced motion', async t => {
  const { window, $, animation } = await setup(t, { appearance: 'p3r', canvas: true });
  const hero=window.document.querySelector('.persona-hero');
  assert.ok(animation.observed.has(window.document.querySelector('.stage')), 'Observe the unclipped stage: a zero-radius reveal must not mark its own scene as offscreen');
  assert.ok(!animation.observed.has($('persona-art')));
  animation.step(600);
  assert.equal(hero.style.clipPath, '');
  $('persona-replay').click(); animation.step(700);
  assert.equal(hero.dataset.revealing, 'true');
  $('persona-pause').click();
  assert.equal(hero.style.clipPath, '');
  assert.equal(hero.dataset.revealing, undefined);
  $('persona-pause').click(); $('motion-btn').click();
  $('persona-art').dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  assert.equal(hero.style.clipPath, '');
  assert.equal(animation.pending(), 0);
});
