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

async function setup(t, { getState, makePlan, apply, localGames, preferences, theme, appearance, motion, particlesPaused, personaPaused, spaceScene, gpu = false, canvas = false, selectionGeometry = false, systemReducedMotion = false, unavailableStorage } = {}) {
  const dom = new JSDOM(html, { url: 'https://organizer.test/', runScripts: 'outside-only', pretendToBeVisual: true });
  t.after(() => dom.window.close());
  const { window } = dom;
  if (selectionGeometry) {
    // jsdom has no layout. Use distinct positions and widths so selection motion
    // must follow the actual chosen control rather than a fixed distance.
    window.document.querySelectorAll('.presets, .segmented').forEach(track => {
      Object.defineProperty(track, 'offsetWidth', { configurable: true, value: 360 });
      Object.defineProperty(track, 'offsetHeight', { configurable: true, value: 40 });
      track.querySelectorAll('button').forEach((button, index) => {
        Object.defineProperty(button, 'offsetLeft', { configurable: true, value: 3 + index * 120 });
        Object.defineProperty(button, 'offsetWidth', { configurable: true, value: 104 + index * 8 });
        Object.defineProperty(button, 'offsetTop', { configurable: true, value: 3 });
        Object.defineProperty(button, 'offsetHeight', { configurable: true, value: 34 });
      });
    });
  }
  let animation;
  if (canvas || gpu) {
    let time = 0, next = 0;
    const frames = new Map(), rects = [], arcs = [], fills = [], strokes = [], draws = [], waterFrames = [], observed = new Set();
    let currentPath = [];
    window.CanvasRenderingContext2D = function () {};
    window.IntersectionObserver = class {
      constructor(callback) { this.callback=callback; }
      observe(element) { observed.add(element); }
      disconnect() { observed.clear(); }
    };
    const fakeGPU={
      VERTEX_SHADER:1,FRAGMENT_SHADER:2,COMPILE_STATUS:3,LINK_STATUS:4,ARRAY_BUFFER:5,STATIC_DRAW:6,FLOAT:7,
      TRIANGLES:8,POINTS:9,LINES:10,DEPTH_TEST:11,BLEND:12,SRC_ALPHA:13,ONE_MINUS_SRC_ALPHA:14,COLOR_BUFFER_BIT:16,DEPTH_BUFFER_BIT:32,
      createShader:()=>({}),createProgram:()=>({}),createBuffer:()=>({}),createVertexArray:()=>({}),
      getShaderParameter:()=>true,getProgramParameter:()=>true,getShaderInfoLog:()=>'',getProgramInfoLog:()=>'',
      getAttribLocation:(_,name)=>['aPosition','aCenter','aNormal','aBary','aTag'].indexOf(name),getUniformLocation:(_,name)=>name,
      drawArrays(mode,_,count){draws.push({mode,count});},
    };
    for(const name of ['shaderSource','compileShader','attachShader','linkProgram','useProgram','bindVertexArray','bindBuffer','bufferData',
      'enableVertexAttribArray','vertexAttribPointer','enable','blendFunc','clearColor','viewport','clear','uniformMatrix4fv','uniform1f',
      'uniform2f','uniform3fv','uniform4fv','deleteBuffer','deleteVertexArray','deleteShader','deleteProgram'])fakeGPU[name]=()=>{};
    if(gpu)window.WebGL2RenderingContext=function(){};
    window.HTMLCanvasElement.prototype.getContext = function (type) {
      if(type==='webgl2')return gpu?fakeGPU:null;
      if (this.classList.contains('persona-water')) return {
        createImageData: (w,h) => ({ data: new Uint8ClampedArray(w*h*4) }),
        putImageData(pixels) { let checksum=0; for(let i=0;i<pixels.data.length;i+=67) checksum+=pixels.data[i]; waterFrames.push(checksum); },
      };
      return ({ setTransform() {}, clearRect() { rects.length = 0; arcs.length = 0; fills.length = 0; strokes.length = 0; }, fillRect(...rect) { rects.push(rect); }, arc(...arc) { arcs.push(arc); }, beginPath() { currentPath = []; }, stroke() { strokes.push({ width: this.lineWidth, color: this.strokeStyle, points: [...currentPath] }); }, fill() { fills.push(1); }, save() {}, restore() {}, translate() {}, rotate() {}, moveTo(x,y) { currentPath.push([x,y]); }, lineTo(x,y) { currentPath.push([x,y]); }, closePath() {} }); };
    window.document.getElementById('persona-art').getBoundingClientRect = () => ({ width: 420, height: 300, left: 0, top: 0 });
    window.document.querySelector('.persona-hero').getBoundingClientRect = () => ({ width: 900, height: 300, left: 0, top: 0, bottom: 300 });
    window.document.querySelector('.stage').getBoundingClientRect = () => ({ width: 900, height: 500, left: 0, top: 0, bottom: 500 });
    window.performance.now = () => time;
    window.requestAnimationFrame = callback => { frames.set(++next, callback); return next; };
    window.cancelAnimationFrame = id => frames.delete(id);
    animation = { rects, arcs, fills, strokes, draws, waterFrames, observed, pending: () => frames.size, step(ms) { time = ms; const batch = [...frames.values()]; frames.clear(); batch.forEach(callback => callback(time)); } };
  }
  window.matchMedia = query => ({ matches: query.includes('prefers-reduced-motion') ? systemReducedMotion : query.includes('prefers-color-scheme: light') || query.includes('(hover: hover)'), addEventListener() {} });
  if (unavailableStorage) Object.defineProperty(window, 'localStorage', { get() { throw new Error('Storage unavailable'); } });
  else {
    if (preferences !== undefined) window.localStorage.setItem('steam-organizer-preferences-v1', preferences);
    if (theme) window.localStorage.setItem('steam-organizer-theme', theme);
    if (appearance) window.localStorage.setItem('steam-organizer-appearance', appearance);
    if (motion) window.localStorage.setItem('steam-organizer-motion', motion);
    if (particlesPaused) window.localStorage.setItem('steam-organizer-particles-paused', 'true');
    if (spaceScene !== undefined) window.localStorage.setItem('steam-organizer-space-scene', spaceScene);
    if (personaPaused) window.localStorage.setItem('steam-organizer-persona-paused', 'true');
  }
  window.pywebview = { api: {
    get_state: getState || (async () => serverState()),
    make_plan: makePlan || (async () => ({ plan_id: 'example-plan', groups, summary: {} })),
    apply: apply || (async () => { throw new Error('Test writes are disabled'); }),
    ...localGames,
  }};
  window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  window.HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new window.Event('close')); };
  window.eval(fs.readFileSync(path.join(ui, 'theme-bootstrap.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ui, 'appearance.js'), 'utf8'));
  window.eval(script);
  window.eval(fs.readFileSync(path.join(ui, 'local-games.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ui, 'library-manager.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ui, 'artwork.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ui, 'vault.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ui, 'persona-motion.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ui, 'calm.js'), 'utf8'));
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

function localGameScan() {
  return { plan_id: 'local-plan', candidates: [
    { id: 'known', name: '原神', exe: 'D:\\Games\\YuanShen.exe', start_dir: 'D:\\Games', args: '', confidence: 'recognized', existing: false, source: '目录', reason: '已识别游戏' },
    { id: 'review', name: '<img src=x onerror=alert(1)>', exe: 'D:\\Games\\Other.exe', start_dir: 'D:\\Games', args: '--channel CN', confidence: 'review', existing: false, source: '目录', reason: '请确认' },
    { id: 'existing', name: '已添加', exe: 'D:\\Games\\Existing.exe', start_dir: 'D:\\Games', args: '', confidence: 'recognized', existing: true, source: '目录', reason: '已识别游戏' },
  ], warnings: [] };
}

test('local game discovery selects only recognized new games and treats names as text', async t => {
  const { $, window } = await setup(t, { localGames: { scan_local_games: async () => localGameScan() } });
  $('local-games-open').click(); $('local-games-scan').click(); await settle();
  assert.equal($('local-games-dialog').open, true);
  const checks = [...$('local-games-list').querySelectorAll('input[type=checkbox]')];
  assert.deepEqual(checks.map(x => x.checked), [true, false, false]);
  assert.equal(checks[2].disabled, true);
  assert.equal($('local-games-list').querySelector('img'), null);
  assert.equal($('local-games-import').disabled, false);
  $('local-games-search').value = 'Other.exe';
  $('local-games-search').dispatchEvent(new window.Event('input'));
  $('local-games-select').click();
  assert.equal($('local-games-selection').textContent, '已选 2 / 2');
  $('local-games-close').click();
  assert.equal(window.document.activeElement.id, 'local-games-open');
});

test('local import requires confirmation, passes selected IDs and rename, and supports undo', async t => {
  const calls = [];
  const { $, window } = await setup(t, { localGames: {
    scan_local_games: async () => localGameScan(),
    import_local_games: async payload => { calls.push(payload); return { added: 1, backup: 'backup.json' }; },
    undo_local_import: async () => ({ restored: 'backup.json' }),
  } });
  $('local-games-open').click(); $('local-games-scan').click(); await settle();
  const name = $('local-games-list').querySelector('.local-game-details input');
  name.value = '原神 · 国服'; name.dispatchEvent(new window.Event('input'));
  $('local-games-import').click();
  assert.equal(calls.length, 0);
  assert.equal($('local-games-confirm').hidden, false);
  $('local-games-confirm-action').click(); await settle();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].selected.join(','), 'known');
  assert.equal(calls[0].names.known, '原神 · 国服');
  assert.equal(calls[0].plan_id, 'local-plan');
  assert.equal($('local-games-import').disabled, true);
  assert.match($('local-games-status').textContent, /已导入 1/);
  $('local-games-undo').click(); $('local-games-confirm-action').click(); await settle();
  assert.match($('local-games-status').textContent, /已恢复/);
});

test('merged local games stay in one row and selecting a launch variant changes only its submitted ID', async t => {
  const scan = localGameScan(), calls = [];
  const primary = { ...scan.candidates[0] };
  const alternate = { ...primary, id: 'known-direct', exe: 'F:\\Game\\YuanShen.exe', args: '--channel CN', source: '安装目录' };
  scan.candidates[0].alternatives = [primary, alternate];
  scan.merged = 1; scan.locations = ['D:\\Games', 'F:\\Game']; scan.partial_roots = 1; scan.incomplete_locations = ['F:\\Game'];
  const { $, window } = await setup(t, { localGames: {
    scan_local_games: async () => scan,
    import_local_games: async payload => { calls.push(payload); return { added: 1, backup: 'backup.json' }; },
  } });
  $('local-games-open').click(); $('local-games-scan').click(); await settle();
  assert.equal($('local-games-list').querySelectorAll('article').length, 3);
  assert.match($('local-games-status').textContent, /合并 1 个重复入口/);
  assert.match($('local-games-coverage').textContent, /2 个位置.*部分目录未扫完/);
  assert.match($('local-games-coverage').querySelector('ul').textContent, /F:\\Game（未扫完/);
  let select = $('local-games-list').querySelector('select');
  select.value = alternate.id; select.dispatchEvent(new window.Event('change')); await settle();
  assert.match($('local-games-list').querySelector('.local-game-path').textContent, /F:\\Game/);
  assert.equal($('local-games-list').querySelector('details').open, true);
  assert.equal(window.document.activeElement.tagName, 'SELECT');
  assert.equal($('local-games-selection').textContent, '已选 1 / 2');
  $('local-games-import').click(); $('local-games-confirm-action').click(); await settle();
  assert.equal(calls[0].selected.join(','), 'known-direct');
});

test('already-added local games lock all alternative launch modes', async t => {
  const scan = localGameScan();
  scan.candidates = [{ ...scan.candidates[2], alternatives: [{ ...scan.candidates[2] }, { ...scan.candidates[2], id: 'other-existing' }] }];
  const { $ } = await setup(t, { localGames: { scan_local_games: async () => scan } });
  $('local-games-open').click(); $('local-games-scan').click(); await settle();
  assert.equal($('local-games-list').querySelector('select').disabled, true);
  $('local-games-select').click();
  assert.equal($('local-games-import').disabled, true);
});

test('local import errors retain confirmation and unlock controls for retry', async t => {
  const { $ } = await setup(t, { localGames: {
    scan_local_games: async () => localGameScan(),
    import_local_games: async () => { throw new Error('Steam 正在运行'); },
  } });
  $('local-games-open').click(); $('local-games-scan').click(); await settle();
  $('local-games-import').click(); $('local-games-confirm-action').click(); await settle();
  assert.match($('local-games-error').textContent, /Steam 正在运行/);
  assert.equal($('local-games-confirm').hidden, false);
  assert.equal($('local-games-confirm-action').disabled, false);
  $('local-games-back').click();
  assert.equal($('local-games-results').hidden, false);
});

test('local scanning can be cancelled and blocks global organizer shortcuts', async t => {
  let resolveScan, plans = 0, cancelled = 0;
  const { $, window } = await setup(t, { makePlan: async () => { plans++; return { groups: [] }; }, localGames: {
    scan_local_games: () => new Promise(resolve => { resolveScan = resolve; }),
    cancel_local_scan: async () => { cancelled++; resolveScan({ candidates: [], cancelled: true, plan_id: null }); return {}; },
  } });
  $('local-games-open').click();
  window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }));
  assert.equal(plans, 0);
  $('local-games-scan').click(); await settle();
  assert.equal($('local-games-close').disabled, true);
  assert.equal($('local-games-cancel').hidden, false);
  $('local-games-cancel').click(); await settle();
  assert.equal(cancelled, 1);
  assert.equal($('local-games-import').disabled, true);
  assert.equal($('local-games-close').disabled, false);
});

function selectionBox(track) {
  const slider = track.querySelector('.calm-selection');
  assert.ok(slider, 'The functional selection indicator is present');
  const x = Number(slider.style.transform.match(/translate\(\s*([-\d.]+)px/)?.[1]);
  const scale = Number(slider.style.transform.match(/scaleX\(\s*([-\d.]+)/)?.[1]);
  assert.ok(Number.isFinite(x) && Number.isFinite(scale), 'Selection geometry is finite');
  return { x, width: parseFloat(slider.style.width) * scale };
}

function artworkFixture() {
  return { account: 'art-account', revision: 'art-revision', games: [
    { id: 'new-game', name: '<img src=x onerror=alert(1)>', present: { cover: true, hero: false, logo: false, wide: false } },
    { id: 'older-game', name: 'Older Game', present: { cover: false, hero: false, logo: false, wide: false } },
  ] };
}

test('artwork uses reviewed server image plans, escapes titles and preserves existing art by default', async t => {
  const calls = [];
  const { $, window } = await setup(t, { localGames: { manage_artwork: async (action, payload) => {
    calls.push({ action, payload });
    if (action === 'load') return artworkFixture();
    if (action === 'current') return { images: {} };
    if (action === 'search') return { matches: [{ id: 'match', name: '<script>bad</script>', provider: 'steam', exact: true }] };
    if (action === 'preview') return { plan_id: 'art-plan', name: 'Matched Game', provider: 'steam', images: Object.fromEntries(['cover','hero','logo','wide'].map(kind => [kind, { preview: 'data:image/png;base64,YQ==', width: 600, height: 900 }])) };
    if (action === 'apply') return { saved: ['hero','logo','wide'], skipped: [], backup: 'backup.json' };
    throw new Error('Unexpected action');
  } } });
  $('artwork-open').click(); await settle(); await settle();
  assert.equal($('artwork-dialog').open, true);
  assert.equal($('artwork-games').querySelector('img'), null);
  assert.equal(calls.filter(x => ['apply','auto','undo'].includes(x.action)).length, 0);
  $('artwork-search-form').dispatchEvent(new window.Event('submit', { cancelable: true })); await settle();
  assert.equal($('artwork-matches').querySelector('script'), null);
  $('artwork-matches').querySelector('button').click(); await settle();
  assert.equal($('artwork-images').querySelectorAll('img').length, 4);
  assert.deepEqual([...$('artwork-images').querySelectorAll('input')].map(x => x.checked), [false,true,true,true]);
  $('artwork-apply').click(); await settle();
  const applied = calls.find(x => x.action === 'apply').payload;
  assert.equal(applied.account, 'art-account'); assert.equal(applied.revision, 'art-revision');
  assert.equal(applied.game_id, 'new-game'); assert.equal(applied.plan_id, 'art-plan'); assert.equal(applied.replace, false);
  assert.equal(applied.selected.join(','), 'hero,logo,wide');
  assert.match($('artwork-status').textContent, /保存 3 张/);
  $('artwork-key').value = 'not-persisted-api-key';
  $('artwork-close').click();
  assert.equal($('artwork-key').value, '');
  assert.ok(!Object.values(window.localStorage).some(x => String(x).includes('not-persisted-api-key')));
});

test('import automatically fills only newly imported game artwork after closing the import dialog', async t => {
  const autos = [];
  const { $ } = await setup(t, { localGames: {
    scan_local_games: async () => localGameScan(),
    import_local_games: async () => ({ added: 1, backup: 'backup.json', appids: ['new-game'] }),
    manage_artwork: async (action, payload) => {
      if (action === 'load') return artworkFixture();
      if (action === 'current') return { images: {} };
      if (action === 'auto') { autos.push(payload.game_id); return { status: 'matched', saved: ['cover','hero','logo','wide'] }; }
      throw new Error('Unexpected action');
    },
  } });
  $('local-games-open').click(); $('local-games-scan').click(); await settle();
  $('local-games-import').click();
  assert.equal($('local-games-artwork').checked, true);
  $('local-games-confirm-action').click(); await settle(); await settle(); await settle();
  assert.equal($('local-games-dialog').open, false);
  assert.equal($('artwork-dialog').open, true);
  assert.deepEqual(autos, ['new-game']);
  assert.match($('artwork-status').textContent, /补齐 4 张图片/);
});

test('artwork write errors retain the image plan for retry and restore dialog controls', async t => {
  const { $, window } = await setup(t, { localGames: { manage_artwork: async action => {
    if (action === 'load') return artworkFixture();
    if (action === 'current') return { images: {} };
    if (action === 'search') return { matches: [{ id: 'match', name: 'Game', provider: 'steam', exact: true }] };
    if (action === 'preview') return { plan_id: 'plan', name: 'Game', provider: 'steam', images: { hero: { preview: 'data:image/png;base64,YQ==', width: 100, height: 100 } } };
    if (action === 'apply') throw new Error('Steam 正在运行，请完全退出');
    throw new Error('Unexpected action');
  } } });
  $('artwork-open').click(); await settle(); await settle();
  $('artwork-search-form').dispatchEvent(new window.Event('submit', { cancelable: true })); await settle();
  $('artwork-matches').querySelector('button').click(); await settle();
  $('artwork-apply').click(); await settle();
  assert.match($('artwork-error').textContent, /Steam 正在运行/);
  assert.equal($('artwork-apply').disabled, false);
  assert.equal($('artwork-close').disabled, false);
  assert.equal($('artwork-images').querySelectorAll('img').length, 1);
  window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }));
  assert.equal($('sheet').hidden, true);
});

test('local artwork supports folder search and reviewed per-role image choices', async t => {
  const calls = [];
  const { $, window } = await setup(t, { localGames: { manage_artwork: async (action, payload) => {
    calls.push({ action, payload });
    if (action === 'load') return artworkFixture();
    if (action === 'current') return { images: {} };
    if (action === 'search') return { matches: [{ id: 'local-match', name: '本地图片', provider: 'local' }] };
    if (action === 'preview') return { plan_id: 'local-plan', name: 'Game', provider: 'local',
      images: { cover: { preview: 'data:image/png;base64,YQ==', width: 600, height: 900 } },
      local_choices: { cover: [{ name: 'poster-a.png', width: 600, height: 900 }, { name: 'poster-b.png', width: 300, height: 450 }] } };
    throw new Error('Unexpected action');
  } } });
  $('artwork-open').click(); await settle(); await settle();
  $('artwork-provider').value = 'local'; $('artwork-provider').dispatchEvent(new window.Event('change'));
  assert.equal($('artwork-local-folder').hidden, false);
  $('artwork-folder').value = 'D:\\Game\\LauncherArt';
  $('artwork-search-form').dispatchEvent(new window.Event('submit', { cancelable: true })); await settle();
  assert.equal(calls.at(-1).payload.folder, 'D:\\Game\\LauncherArt');
  $('artwork-matches').querySelector('button').click(); await settle();
  const picker = $('artwork-images').querySelector('select');
  assert.equal(picker.options.length, 2);
  picker.value = '1'; picker.dispatchEvent(new window.Event('change')); await settle();
  assert.equal(calls.at(-1).payload.local_selection.cover, 1);
  assert.equal(calls.some(x => x.action === 'apply'), false);
  $('artwork-games').lastElementChild.click(); await settle();
  assert.equal($('artwork-folder').value, '', 'A chosen folder must not carry over to another game');
});

function assertSelectionAt(track, button) {
  const box = selectionBox(track);
  assert.ok(Math.abs(box.x - button.offsetLeft) < .1, 'Indicator reaches the selected control');
  assert.ok(Math.abs(box.width - button.offsetWidth) < .1, 'Indicator fits the selected control width');
  assert.equal(button.getAttribute('aria-pressed'), 'true');
}

async function pointerChoose(window, button) {
  button.dispatchEvent(new window.MouseEvent('pointerdown', { bubbles: true }));
  button.click();
  await settle();
}

test('calm selection can redirect mid-flight and stops scheduling frames after settling', async t => {
  const { window, animation } = await setup(t, { appearance: 'calm', canvas: true, selectionGeometry: true });
  const track = window.document.querySelector('.presets');
  const [recommended, simple, habits] = track.querySelectorAll('button');
  assert.ok(track.classList.contains('calm-track-ready'));
  assertSelectionAt(track, recommended);
  assert.equal(animation.pending(), 0);
  await pointerChoose(window, habits);
  assert.equal(habits.getAttribute('aria-pressed'), 'true', 'The control state changes without waiting for animation');
  animation.step(17);
  animation.step(34);
  const during = selectionBox(track);
  assert.ok(during.x > recommended.offsetLeft && during.x < habits.offsetLeft);
  await pointerChoose(window, simple);
  assert.deepEqual(selectionBox(track), during, 'Retargeting preserves the current visual position');
  for (let ms = 51; ms <= 1500; ms += 17) animation.step(ms);
  assertSelectionAt(track, simple);
  assert.equal(animation.pending(), 0, 'A settled selector leaves no background frame loop');

  const language = window.document.querySelector('.segmented');
  const english = language.querySelector('[data-lang="english"]');
  await pointerChoose(window, english);
  for (let ms = 1517; ms <= 3000; ms += 17) animation.step(ms);
  assertSelectionAt(language, english);
  assert.equal(animation.pending(), 0);

  await pointerChoose(window, window.document.querySelector('[data-mode="initial"]'));
  assert.equal(track.querySelector('.calm-selection').hidden, true, 'A custom rule combination must not highlight an unrelated preset');
  assert.equal(track.classList.contains('calm-track-ready'), false);
  assert.equal(animation.pending(), 0);
  await pointerChoose(window, recommended);
  assertSelectionAt(track, recommended);
});

test('calm keyboard and reduced-motion selection snap immediately without disabling controls', async t => {
  const { window, $, animation } = await setup(t, { appearance: 'calm', canvas: true, selectionGeometry: true });
  const track = window.document.querySelector('.presets');
  const [recommended, simple, habits] = track.querySelectorAll('button');
  await pointerChoose(window, habits);
  animation.step(17);
  simple.focus();
  simple.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  simple.click(); // jsdom does not synthesize a button click from Enter.
  await settle();
  assert.equal(window.document.documentElement.dataset.input, 'keyboard');
  assertSelectionAt(track, simple);
  assert.equal(animation.pending(), 0);
  assert.equal(window.document.activeElement, simple);

  await pointerChoose(window, habits);
  animation.step(34);
  assert.ok(animation.pending() > 0);
  $('motion-btn').click();
  assertSelectionAt(track, habits);
  assert.equal(animation.pending(), 0);
  await pointerChoose(window, recommended);
  assertSelectionAt(track, recommended);
  assert.equal(animation.pending(), 0);
  assert.equal(recommended.disabled, false);
  assert.equal($('plan-btn').disabled, false);
});

test('calm selection cancels while hidden and does not resume stale motion on return', async t => {
  const { window, animation } = await setup(t, { appearance: 'calm', canvas: true, selectionGeometry: true });
  const track = window.document.querySelector('.presets');
  const habits = track.querySelector('[data-preset="habits"]');
  await pointerChoose(window, habits);
  animation.step(17);
  assert.ok(animation.pending() > 0);
  Object.defineProperty(window.document, 'hidden', { configurable: true, value: true });
  window.document.dispatchEvent(new window.Event('visibilitychange'));
  assert.equal(animation.pending(), 0);
  assertSelectionAt(track, habits);
  Object.defineProperty(window.document, 'hidden', { configurable: true, value: false });
  window.document.dispatchEvent(new window.Event('visibilitychange'));
  animation.step(2000);
  assert.equal(animation.pending(), 0);
  assertSelectionAt(track, habits);
});

test('calm keeps functional controls and recovers from an empty preview without decorative controls', async t => {
  const { window, $, plan, animation } = await setup(t, {
    appearance: 'calm', canvas: true, selectionGeometry: true, systemReducedMotion: true,
    makePlan: async () => ({ plan_id: 'empty', groups: [], summary: {} }),
  });
  assert.equal(window.document.querySelector('#calm-arrange, #calm-art-help, #calm-rule-count, #calm-field-canvas, #calm-field-trigger'), null);
  await pointerChoose(window, window.document.querySelector('[data-preset="simple"]'));
  await plan();
  assert.equal($('preview-panel').classList.contains('has-preview'), true);
  assert.equal($('preview-empty').hidden, false);
  assert.equal($('apply-btn').hidden, true);
  assert.match($('empty-title').textContent, /没有可分类/);
  await pointerChoose(window, window.document.querySelector('[data-preset="recommended"]'));
  assert.equal($('plan-btn').disabled, false, 'An empty result does not prevent changing rules and retrying');
  assert.equal(animation.pending(), 0);
});

test('calm review transition stays interactive and is cancelled on reduced motion', async t => {
  const { window, $, plan, animation } = await setup(t, { appearance: 'calm', canvas: true, selectionGeometry: true });
  const motions = [];
  for (const id of ['stats', 'preview-panel', 'groups']) {
    const element = $(id);
    element.getBoundingClientRect = () => ({ top: $('preview-panel').classList.contains('has-preview') ? 100 : 280 });
    element.animate = frames => {
      const motion = { frames, cancelled: false, cancel() { this.cancelled = true; } };
      motions.push(motion);
      return motion;
    };
  }
  await plan();
  assert.equal(motions.length, 3);
  assert.equal(motions[0].frames[0].transform, 'translate(0px, 180px)');
  assert.equal(motions[2].frames.at(-1).opacity, 1);
  assert.equal(animation.pending(), 0);
  assert.equal($('apply-btn').disabled, false);
  assert.equal(window.document.activeElement, $('preview-search'));
  window.document.querySelector('.group-checkbox').click();
  assert.equal($('preview-groups').textContent, '2');
  $('motion-btn').click();
  assert.ok(motions.every(motion => motion.cancelled));
  assert.equal($('preview-groups').textContent, '2');
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

test('series rule participates in reviewed plans and persists on reload', async t => {
  const requests = [];
  const first = await setup(t, { makePlan: async payload => {
    requests.push(payload);
    return { plan_id: 'series-plan', groups: [{ id: 'series:女神异闻录', mode: 'series', name: '系列 · 女神异闻录', count: 2, appids: [1, 2], sample: ['Persona 3 Reload', 'Persona 5 Royal'] }], summary: {} };
  } });
  const rule = first.window.document.querySelector('[data-mode="series"]');
  assert.ok(rule); assert.equal(rule.getAttribute('aria-pressed'), 'false');
  rule.click(); await first.plan();
  assert.ok(requests[0].modes.includes('series'));
  assert.match(first.$('groups').textContent, /系列 · 女神异闻录/);
  const preferences = first.window.localStorage.getItem('steam-organizer-preferences-v1');
  const second = await setup(t, { preferences });
  assert.equal(second.window.document.querySelector('[data-mode="series"]').getAttribute('aria-pressed'), 'true');
  rule.click();
  assert.equal(first.$('apply-btn').hidden, true, 'Changing series selection invalidates the old plan');
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
  assert.ok(Buffer.byteLength(previewHtml, 'utf16le') < 2_097_152, 'WebView2 also bounds the UTF-16 document size');
  assert.ok(!previewHtml.includes('"art/app-icon.png"'), 'The logo and favicon are embedded offline');
  const dom = new JSDOM(previewHtml, {
    url: 'https://offline-preview.test/', runScripts: 'dangerously', pretendToBeVisual: true,
    beforeParse(window) {
      window.matchMedia = () => ({ matches: true, addEventListener() {} });
      window.structuredClone = structuredClone;
    },
  });
  t.after(() => dom.window.close());
  assert.match(dom.window.document.querySelector('.brand-mark img').src, /^data:image\/png;base64,/);
  assert.match(dom.window.document.querySelector('link[rel="icon"]').href, /^data:image\/png;base64,/);
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
  assert.ok(dom.window.document.querySelector('style[data-source="calm.css"]'));
  assert.ok(dom.window.document.querySelector('script[data-source="calm.js"]'));
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

test('Lightfield is the default and appearance switching preserves the live preview', async t => {
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

test('Lightfield home and review navigation preserve selection, search and stale-plan guards', async t => {
  const { window, $, run, plan } = await setup(t);
  const root = window.document.documentElement;
  assert.equal(root.dataset.vaultView, 'collection');
  assert.equal($('vault-review-btn').disabled, true);
  assert.ok($('orbit-wheel'));
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

test('wheel loads real library rows, filters, and opens the selected game without writes', async t => {
  const calls = [];
  const { $, window } = await setup(t, { systemReducedMotion: true, localGames: { manage_library: async (action, payload) => { calls.push({ action, payload }); return managedLibrary(); } } });
  await settle();
  assert.equal($('orbit-total').textContent, '3 个游戏');
  $('orbit-next').click();
  assert.equal($('orbit-title').textContent, '<img src=x onerror=alert(1)>');
  assert.equal($('orbit-title').querySelector('img'), null);
  $('orbit-manage').click(); await settle();
  assert.equal($('library-manager-dialog').open, true);
  assert.equal($('library-manager-search').value, '<img src=x onerror=alert(1)>');
  assert.ok(calls.every(x => x.action === 'load'));
  $('library-manager-close').click();
  $('orbit-installed').checked = true; $('orbit-installed').dispatchEvent(new window.Event('change'));
  assert.equal($('orbit-count').textContent, '1 项');
  assert.equal($('orbit-next').disabled, true);
  $('orbit-search').value = 'not present'; $('orbit-search').dispatchEvent(new window.Event('input'));
  assert.equal($('orbit-manage').disabled, true);
  assert.equal($('orbit-cards').children.length, 0);
});

test('wheel keyboard wraps, pointer drag advances, and trackpad momentum advances once', async t => {
  const { $, window } = await setup(t, { systemReducedMotion: true, localGames: { manage_library: async () => managedLibrary() } });
  await settle();
  const wheel = $('orbit-wheel');
  wheel.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true, cancelable: true }));
  assert.equal($('orbit-index').textContent, '03 / 3');
  wheel.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Home', bubbles: true, cancelable: true }));
  wheel.dispatchEvent(new window.WheelEvent('wheel', { deltaY: 120, cancelable: true }));
  wheel.dispatchEvent(new window.WheelEvent('wheel', { deltaY: 120, cancelable: true }));
  assert.equal($('orbit-index').textContent, '02 / 3');
  wheel.setPointerCapture = () => {}; wheel.hasPointerCapture = () => false;
  wheel.dispatchEvent(new window.MouseEvent('pointerdown', { button: 0, clientX: 200, clientY: 100 }));
  wheel.dispatchEvent(new window.MouseEvent('pointermove', { clientX: 140, clientY: 100 }));
  wheel.dispatchEvent(new window.MouseEvent('pointerup', { clientX: 140, clientY: 100 }));
  assert.equal($('orbit-index').textContent, '03 / 3');
});

test('wheel settles at rest and stops its frames on review, hidden pages and reduced motion', async t => {
  const { $, window, animation, plan } = await setup(t, { canvas: true, localGames: { manage_library: async () => managedLibrary() } });
  await settle();
  $('orbit-radiance-pause').click();
  $('orbit-next').click(); assert.ok(animation.pending() > 0);
  for (let time = 16; time < 2400; time += 16) animation.step(time);
  assert.equal(animation.pending(), 0);
  $('orbit-next').click(); await plan(); assert.equal(animation.pending(), 0);
  $('vault-collection-btn').click(); $('orbit-next').click();
  Object.defineProperty(window.document, 'hidden', { configurable: true, value: true });
  window.document.dispatchEvent(new window.Event('visibilitychange')); assert.equal(animation.pending(), 0);
});

test('radial beams flow behind the wheel, respond to selection, and pause in review', async t => {
  const { $, animation, plan } = await setup(t, { canvas: true, localGames: { manage_library: async () => managedLibrary() } });
  await settle(); animation.step(0);
  assert.equal($('orbit-radiance').getAttribute('aria-hidden'), 'true');
  assert.ok(animation.strokes.some(stroke => stroke.points.length >= 80), 'Multiple radial trails are actually painted');
  const before = JSON.stringify(animation.strokes[0].points);
  animation.step(80);
  assert.notEqual(JSON.stringify(animation.strokes[0].points), before);
  $('orbit-next').click(); animation.step(120);
  assert.ok(animation.strokes.some(stroke => stroke.width > 1.2), 'Selection intensifies the outward burst');
  $('orbit-radiance-pause').click(); animation.step(150);
  for (let time = 166; time < 2200; time += 16) animation.step(time);
  assert.equal(animation.pending(), 0);
  assert.equal($('orbit-radiance-pause').getAttribute('aria-pressed'), 'true');
  $('orbit-radiance-pause').click(); animation.step(2400);
  assert.ok(animation.pending() > 0);
  $('library-manager-open').click(); await settle(); animation.step(2450);
  assert.equal(animation.pending(), 0, 'Dialog suspends background drawing');
  $('library-manager-close').click(); animation.step(2500);
  assert.ok(animation.pending() > 0, 'Closing dialog resumes ambient beams');
  await plan(); assert.equal(animation.pending(), 0);
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

function managedLibrary() {
  return { account: 'account', revision: 'rev1', can_undo: false, folders: [{ id: 'fav', name: '常玩' }], games: [
    { id: 'steam:1', appid: 1, name: 'Alpha', source: 'Steam', installed: true, steam_minutes: 120, minutes: null, folder: '', tags: [] },
    { id: 'steam:2', appid: 2, name: '<img src=x onerror=alert(1)>', source: 'Steam', installed: false, steam_minutes: null, minutes: null, folder: 'fav', tags: ['待玩'] },
    { id: 'local:3', appid: 3, name: 'Local game', source: '非 Steam', steam_minutes: null, minutes: 60, folder: '', tags: [] },
  ] };
}

test('game management opens without writing and renders unsafe names as text', async t => {
  const calls = [];
  const { $, window } = await setup(t, { localGames: { manage_library: async (action, payload) => { calls.push({action, payload}); return managedLibrary(); } } });
  $('library-manager-open').click(); await settle();
  assert.equal($('library-manager-dialog').open, true);
  assert.ok(calls.length >= 1 && calls.every(c => c.action === 'load'));
  assert.equal($('library-manager-list').children.length, 3);
  assert.equal($('library-manager-list').querySelector('img'), null);
  assert.equal($('library-manager-move').disabled, true);
  assert.match($('library-manager-list').textContent, /Steam 记录/);
  assert.match($('library-manager-list').textContent, /自定义/);
  window.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }));
  assert.equal($('sheet').hidden, true);
});

test('folder creation and batch actions send account-bound IDs; filtering clears hidden selections', async t => {
  const calls = [];
  const data = managedLibrary();
  const { $, window } = await setup(t, { localGames: { manage_library: async (action, payload) => {
    calls.push({action, payload: JSON.parse(JSON.stringify(payload))});
    if (payload.action === 'create_folder') data.folders.push({id:'new', name:payload.name});
    return structuredClone(data);
  } } });
  $('library-manager-open').click(); await settle();
  $('library-manager-new-folder').click(); $('library-manager-field').value = '周末';
  $('library-manager-editor-save').click(); await settle();
  assert.equal(calls.at(-1).payload.name, '周末');
  assert.equal($('library-manager-editor').hidden, true);
  $('library-manager-select').click(); $('library-manager-target').value = 'new'; $('library-manager-move').click(); await settle();
  assert.deepEqual(calls.at(-1).payload.ids, ['steam:1', 'steam:2', 'local:3']);
  assert.equal(calls.at(-1).payload.folder, 'new');
  assert.equal(calls.at(-1).payload.account, 'account');
  $('library-manager-select').click();
  $('library-manager-search').value = 'Alpha'; $('library-manager-search').dispatchEvent(new window.Event('input'));
  assert.equal($('library-manager-list').children.length, 1);
  assert.equal($('library-manager-move').disabled, true);
  $('library-manager-select').click(); $('library-manager-add-tag').click(); $('library-manager-field').value = '喜欢';
  $('library-manager-editor-save').click(); await settle();
  assert.deepEqual(calls.at(-1).payload.ids, ['steam:1']);
  assert.equal(calls.at(-1).payload.tag, '喜欢');
});

test('personal playtime editor rejects blank and accepts zero or clear without replacing Steam record', async t => {
  const calls = [];
  const { $ } = await setup(t, { localGames: { manage_library: async (action, payload) => { calls.push({action, payload}); return managedLibrary(); } } });
  $('library-manager-open').click(); await settle();
  $('library-manager-list').querySelector('.manager-hours').click();
  assert.match($('library-manager-editor-note').textContent, /不修改 Steam 时长/);
  $('library-manager-field').value = ''; $('library-manager-editor-save').click(); await settle();
  assert.equal(calls.filter(x => x.action !== 'load').length, 0);
  $('library-manager-field').value = '0'; $('library-manager-editor-save').click(); await settle();
  assert.equal(calls.at(-1).payload.hours, 0);
  $('library-manager-list').querySelector('.manager-hours').click();
  $('library-manager-reset-time').click(); await settle();
  assert.equal(calls.at(-1).payload.hours, null);
});

test('Steam sync requires preview confirmation and keeps review on failure', async t => {
  const calls = [];
  const { $ } = await setup(t, { localGames: { manage_library: async (action, payload) => {
    calls.push({action, payload});
    if (action === 'preview') return { plan_id:'reviewed', replaced:2, groups:[{name:'常玩', appids:[1]}] };
    if (action === 'publish') throw new Error('Steam 仍在运行');
    return managedLibrary();
  } } });
  $('library-manager-open').click(); await settle();
  $('library-manager-sync').click(); await settle();
  assert.deepEqual(calls.filter(c => c.action !== 'load').map(c => c.action), ['preview']);
  assert.match($('library-manager-sync-list').textContent, /常玩/);
  $('library-manager-editor-save').click(); await settle();
  assert.equal(calls.at(-1).payload.plan_id, 'reviewed');
  assert.equal($('library-manager-editor').hidden, false);
  assert.match($('library-manager-error').textContent, /仍在运行/);
  assert.equal($('library-manager-close').disabled, false);
});

test('reorder controls persist order and switch off in alphabetical view', async t => {
  const calls = [];
  const { $, window } = await setup(t, { localGames: { manage_library: async (action, payload) => { calls.push({action,payload}); return managedLibrary(); } } });
  $('library-manager-open').click(); await settle();
  $('library-manager-list').querySelector('.manager-order button:last-child').click(); await settle();
  assert.equal(calls.at(-1).payload.action, 'reorder');
  assert.equal(calls.at(-1).payload.before, 'local:3');
  $('library-manager-select').click(); $('library-manager-bottom').click(); await settle();
  assert.equal(calls.at(-1).payload.before, null);
  $('library-manager-sort').value = 'name'; $('library-manager-sort').dispatchEvent(new window.Event('change'));
  assert.equal($('library-manager-list').querySelector('.manager-order button').disabled, true);
  $('library-manager-select').click();
  assert.equal($('library-manager-bottom').disabled, false);
  $('library-manager-bottom').click(); await settle();
  assert.equal(calls.at(-1).payload.before, null);
  assert.equal($('library-manager-sort').value, 'manual');
});

 test('pointer drag supports reordering and folder moves without native HTML drag', async t => {
  const calls = [];
  const { $, window } = await setup(t, { localGames: { manage_library: async (action, payload) => { calls.push({action,payload}); return managedLibrary(); } } });
  $('library-manager-open').click(); await settle();
  const drag = async (target, cancel = false) => {
    const handle = $('library-manager-list').querySelector('.manager-grip');
    handle.setPointerCapture = () => {};
    handle.hasPointerCapture = () => false;
    window.document.elementFromPoint = () => target;
    handle.dispatchEvent(new window.MouseEvent('pointerdown', {button:0,clientX:10,clientY:10}));
    handle.dispatchEvent(new window.MouseEvent('pointermove', {button:0,clientX:20,clientY:20}));
    handle.dispatchEvent(new window.MouseEvent(cancel ? 'pointercancel' : 'pointerup', {button:0,clientX:20,clientY:20}));
    await settle();
  };
  await drag($('library-manager-list').children[1]);
  assert.equal(calls.at(-1).payload.action, 'reorder');
  assert.equal(calls.at(-1).payload.before, 'steam:2');
  await drag($('library-manager-folders').querySelector('[data-folder="fav"]'));
  assert.equal(calls.at(-1).payload.action, 'move');
  assert.equal(calls.at(-1).payload.folder, 'fav');
  const previous = calls.length;
  await drag($('library-manager-list').children[1], true);
  assert.equal(calls.length, previous);
  assert.equal($('library-manager-dialog').classList.contains('is-dragging'), false);
});
