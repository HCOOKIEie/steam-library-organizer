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

async function setup(t, { getState, makePlan, apply, preferences, theme, appearance, motion, systemReducedMotion = false, unavailableStorage } = {}) {
  const dom = new JSDOM(html, { url: 'https://organizer.test/', runScripts: 'outside-only', pretendToBeVisual: true });
  t.after(() => dom.window.close());
  const { window } = dom;
  window.matchMedia = query => ({ matches: query.includes('prefers-reduced-motion') ? systemReducedMotion : query.includes('prefers-color-scheme: light'), addEventListener() {} });
  if (unavailableStorage) Object.defineProperty(window, 'localStorage', { get() { throw new Error('Storage unavailable'); } });
  else {
    if (preferences !== undefined) window.localStorage.setItem('steam-organizer-preferences-v1', preferences);
    if (theme) window.localStorage.setItem('steam-organizer-theme', theme);
    if (appearance) window.localStorage.setItem('steam-organizer-appearance', appearance);
    if (motion) window.localStorage.setItem('steam-organizer-motion', motion);
  }
  window.pywebview = { api: {
    get_state: getState || (async () => serverState()),
    make_plan: makePlan || (async () => ({ plan_id: 'example-plan', groups, summary: {} })),
    apply: apply || (async () => { throw new Error('Test writes are disabled'); }),
  }};
  window.eval(fs.readFileSync(path.join(ui, 'theme-bootstrap.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ui, 'appearance.js'), 'utf8'));
  window.eval(script);
  window.eval('boot()');
  await settle();
  const $ = id => window.document.getElementById(id);
  const run = source => window.eval(source);
  const plan = async () => { await run('makePlan()'); await settle(); };
  return { window, $, run, plan };
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

test('empty plans explain the next action without offering a write', async t => {
  const { $, plan } = await setup(t, { makePlan: async () => ({ plan_id: 'empty', groups: [], summary: {} }) });
  await plan();
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
  const exported = spawnSync('python', ['scripts/preview_ui.py', '--export', destination], { cwd: project, encoding: 'utf8', windowsHide: true });
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
  assert.equal(dom.window.document.getElementById('demo-badge').hidden, false);
  assert.ok(dom.window.document.querySelector('style[data-source="p3r.css"]'));
  assert.ok(dom.window.document.querySelector('style[data-source="traces.css"]'));
  assert.equal(dom.window.document.querySelector('.p3r-scene img'), null);
  assert.equal(dom.window.document.getElementById('stat-scope').textContent, '24');
  await dom.window.eval('makePlan()');
  assert.ok(dom.window.document.querySelectorAll('.group').length > 0);
  await assert.rejects(dom.window.pywebview.api.apply({}), /只读示例/);
});

test('RELOAD is the default and appearance switching preserves the live preview', async t => {
  const first = await setup(t);
  const { window, $, plan } = first;
  assert.equal(window.document.documentElement.dataset.appearance, 'p3r');
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

test('TRACES persists and switching all three styles keeps selections, search and plan freshness', async t => {
  const { window, $, run, plan } = await setup(t, { appearance: 'traces', theme: 'dark' });
  const root = window.document.documentElement;
  assert.equal(root.dataset.appearance, 'traces');
  assert.equal(window.document.querySelector('meta[name="theme-color"]').content, '#101f27');
  assert.equal(window.document.querySelector('.traces-scene img'), null);
  assert.equal(window.document.querySelector('button[data-appearance="traces"]').getAttribute('aria-pressed'), 'true');
  await plan();
  assert.equal(root.classList.contains('preview-reveal'), true);
  window.document.querySelector('.group-checkbox').click();
  $('preview-search').value = 'Beta';
  run('filterPreview()');
  const selection = () => Array.from(window.document.querySelectorAll('.group.is-on')).map(row => row.dataset.id);
  const selected = selection();
  for (const style of ['p3r', 'calm', 'traces']) {
    window.document.querySelector(`button[data-appearance="${style}"]`).click();
    assert.equal(root.dataset.appearance, style);
    assert.deepEqual(selection(), selected);
    assert.equal($('preview-search').value, 'Beta');
    assert.equal($('stale-banner').hidden, true);
    assert.equal($('apply-btn').disabled, false);
  }
  assert.equal(window.localStorage.getItem('steam-organizer-appearance'), 'traces');
  $('quick-theme-btn').click();
  assert.equal(window.document.querySelector('meta[name="theme-color"]').content, '#eaf1ef');
  $('motion-btn').click();
  assert.equal(root.classList.contains('preview-reveal'), false);
  assert.equal(root.classList.contains('appearance-enter'), false);
  await plan();
  assert.equal(root.classList.contains('preview-reveal'), false);
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
