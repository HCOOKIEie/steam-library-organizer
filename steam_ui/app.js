/* Steam Library Organizer front end. Safety and clarity come before writes. */

const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
const mobileSheetQuery = window.matchMedia('(max-width: 720px)');
const systemThemeQuery = window.matchMedia('(prefers-color-scheme: light)');
const THEME_STORAGE_KEY = 'steam-organizer-theme';
let reducedMotion = reducedMotionQuery.matches || document.documentElement.dataset.motion === 'reduced';
reducedMotionQuery.addEventListener?.('change', (event) => { reducedMotion = event.matches || document.documentElement.dataset.motion === 'reduced'; });
window.addEventListener('organizer-motion-change', (event) => { reducedMotion = reducedMotionQuery.matches || Boolean(event.detail?.reduced); });
window.addEventListener('organizer-appearance-change', () => {
  applyTheme(document.documentElement.dataset.theme);
});

function readStoredTheme() {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return value === 'dark' || value === 'light' ? value : '';
  } catch (_) {
    return '';
  }
}

let hasStoredTheme = Boolean(readStoredTheme());

function syncThemeControl(theme) {
  const button = document.getElementById('theme-btn');
  if (!button) return;
  const isLight = theme === 'light';
  const currentLabel = isLight ? '亮色' : '深色';
  const targetLabel = isLight ? '深色' : '亮色';
  button.setAttribute('aria-checked', String(isLight));
  button.setAttribute('aria-label', `当前为${currentLabel}模式，切换到${targetLabel}模式`);
  $('theme-icon').textContent = isLight ? '☾' : '☀';
  $('theme-label').textContent = `切换到${targetLabel}模式`;
  $('theme-current').textContent = `当前：${currentLabel}`;
}

function applyTheme(theme, { persist = false, announce = false } = {}) {
  const nextTheme = theme === 'light' ? 'light' : 'dark';
  document.documentElement.dataset.theme = nextTheme;
  const isReload = document.documentElement.dataset.appearance === 'p3r';
  const isRoyal = document.documentElement.dataset.appearance === 'p5r';
  const isVault = document.documentElement.dataset.appearance === 'vault';
  document.documentElement.style.colorScheme = isReload ? 'light' : nextTheme;
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.content = isVault ? (nextTheme === 'light' ? '#eef0f3' : '#0c1015') : isReload ? (nextTheme === 'light' ? '#006fdb' : '#0059cf') : isRoyal ? (nextTheme === 'light' ? '#e21d30' : '#c90d25') : (nextTheme === 'light' ? '#f5f5f7' : '#161618');

  if (persist) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
      hasStoredTheme = true;
    } catch (_) {}
  }

  syncThemeControl(nextTheme);
  $('quick-theme-btn')?.setAttribute('aria-label', `切换到${nextTheme === 'light' ? '深色' : '亮色'}模式`);
  const nativeTheme = window.pywebview?.api?.set_theme;
  if (nativeTheme) Promise.resolve().then(() => nativeTheme(isReload ? 'dark' : nextTheme)).catch(() => {});
  if (announce && document.getElementById('toast')) {
    toast(`已切换到${nextTheme === 'light' ? '亮色' : '深色'}模式`);
  }
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
  applyTheme(current === 'light' ? 'dark' : 'light', { persist: true, announce: true });
  closeMoreMenu();
  $('more-btn').focus();
}

systemThemeQuery.addEventListener?.('change', (event) => {
  if (!hasStoredTheme) applyTheme(event.matches ? 'light' : 'dark');
});

function spring({ from = 0, to = 1, velocity = 0, damping = 1, response = 0.36, onUpdate, onDone }) {
  if (reducedMotion) {
    onUpdate(to, 0);
    onDone?.();
    return { stop() {} };
  }

  const w0 = (2 * Math.PI) / response;
  let value = from;
  let speed = velocity;
  let raf = 0;
  let last = performance.now();
  const tick = (now) => {
    const dt = Math.min((now - last) / 1000, 1 / 30);
    last = now;
    const acceleration = -w0 * w0 * (value - to) - 2 * damping * w0 * speed;
    speed += acceleration * dt;
    value += speed * dt;
    if (Math.abs(value - to) < 0.4 && Math.abs(speed) < 0.4) {
      onUpdate(to, 0);
      onDone?.();
      return;
    }
    onUpdate(value, speed);
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return { stop: () => cancelAnimationFrame(raf) };
}

const state = {
  modes: ['initial', 'genre'],
  language: 'schinese',
  scope: 'library',
  plan: [],
  planId: null,
  planSummary: null,
  planConfig: null,
  planFresh: false,
  planCommitted: false,
  selected: new Set(),
  server: null,
  csrfToken: null,
  scanReady: false,
  metadataReady: false,
  steamRunning: null,
  showAccountId: false,
  booted: false,
  diagnosticsAutoOpened: false,
  busy: {
    scan: false,
    plan: false,
    apply: false,
    restore: false,
    reveal: false,
    root: false,
  },
};

const MODE_CARDS = [
  { id: 'initial', title: '首字母', sub: '拼音 / A–Z', icon: 'type' },
  { id: 'genre', title: '游戏类型', sub: '动作 · 角色扮演', icon: 'tag' },
  { id: 'series', title: '游戏系列', sub: '本地系列资料 / 名称规则', icon: 'layers' },
  { id: 'form', title: '条目形式', sub: '游戏 · DLC · 工具', icon: 'layers' },
  { id: 'developer', title: '开发商', sub: '开发团队', icon: 'build' },
  { id: 'publisher', title: '发行商', sub: '发行公司', icon: 'flag' },
  { id: 'state', title: '安装状态', sub: '已安装 · 未安装', icon: 'check' },
  { id: 'recent', title: '最近游玩', sub: '最后启动时间', icon: 'clock' },
  { id: 'playtime', title: '游玩时长', sub: '累计小时', icon: 'timer' },
];

const MODE_BY_ID = Object.fromEntries(MODE_CARDS.map((mode) => [mode.id, mode]));
const RULE_PRESETS = {
  recommended: ['initial', 'genre'],
  simple: ['initial', 'state'],
  habits: ['recent', 'playtime'],
};
const PREFERENCES_KEY = 'steam-organizer-preferences-v1';

function loadPreferences() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(PREFERENCES_KEY));
    if (!saved || typeof saved !== 'object') return;
    if (Array.isArray(saved.modes) && saved.modes.every((id) => typeof id === 'string' && Object.hasOwn(MODE_BY_ID, id))) {
      state.modes = MODE_CARDS.map((mode) => mode.id).filter((id) => saved.modes.includes(id));
    }
    if (['library', 'games', 'all'].includes(saved.scope)) state.scope = saved.scope;
    if (['schinese', 'tchinese', 'english'].includes(saved.language)) state.language = saved.language;
    if (Number.isInteger(saved.developer_min)) $('developer-min').value = Math.min(100, Math.max(1, saved.developer_min));
  } catch (_) { /* Unavailable storage or invalid settings should never block startup. */ }
}

function savePreferences() {
  try {
    window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(currentPlanConfig()));
  } catch (_) {}
}

function syncRuleControls() {
  $('mode-count').textContent = `已选 ${state.modes.length} 项`;
  document.querySelectorAll('.preset').forEach((button) => {
    const modes = RULE_PRESETS[button.dataset.preset];
    const enabled = modes.length === state.modes.length && modes.every((id) => state.modes.includes(id));
    button.classList.toggle('is-on', enabled);
    button.setAttribute('aria-pressed', String(enabled));
  });
  document.querySelectorAll('.seg').forEach((button) => {
    const enabled = button.dataset.lang === state.language;
    button.classList.toggle('is-on', enabled);
    button.setAttribute('aria-pressed', String(enabled));
  });
}

const DEFAULT_SCOPES = [
  {
    id: 'library',
    title: '游戏库',
    description: '已确认的库内游戏',
  },
  {
    id: 'games',
    title: '仅游戏',
    description: '排除已识别的 DLC、工具与辅助项',
  },
  {
    id: 'all',
    title: '全部条目',
    description: '含 DLC、工具、试玩和共享缓存',
  },
];

const ICONS = {
  type: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7V5h16v2"/><path d="M12 5v14"/><path d="M9 19h6"/></svg>',
  tag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0l-7.2-7.2A2 2 0 0 1 3 12V5a2 2 0 0 1 2-2h7a2 2 0 0 1 1.4.6l7.2 7.2a2 2 0 0 1 0 2.6Z"/><circle cx="7.5" cy="7.5" r="1.4"/></svg>',
  layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/></svg>',
  build: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21V6a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v15"/><path d="M15 10h3a2 2 0 0 1 2 2v9"/><path d="M8 8h3M8 12h3M8 16h3"/></svg>',
  flag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4"/><path d="M5 4h11l-1.5 4L16 12H5"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  timer: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3h4"/><path d="M12 8v5"/><circle cx="12" cy="14" r="7"/></svg>',
  caret: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',
};

const $ = (id) => document.getElementById(id);
const formatNumber = (value) => Number.isFinite(Number(value)) ? Number(value).toLocaleString('zh-CN') : '—';
const numberOr = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;

function make(tag, className = '', text = '') {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== '') element.textContent = String(text);
  return element;
}

function log(message, kind = '') {
  const line = make('span', `log-line${kind ? ` is-${kind}` : ''}`);
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  line.textContent = `[${time}] ${message}`;
  $('log').appendChild(line);
  $('log').scrollTop = $('log').scrollHeight;
  $('log-hint').textContent = message;
  if (kind === 'error') {
    state.diagnosticsAutoOpened = true;
    $('diagnostics').open = true;
  } else if (kind === 'good' && state.diagnosticsAutoOpened) {
    $('diagnostics').open = false;
    state.diagnosticsAutoOpened = false;
  }
}

let toastTimer = 0;
function toast(message, isError = false) {
  const element = $('toast');
  element.textContent = message;
  element.classList.toggle('is-error', isError);
  element.setAttribute('aria-live', isError ? 'assertive' : 'polite');
  element.hidden = false;
  requestAnimationFrame(() => element.classList.add('is-on'));
  clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    element.classList.remove('is-on');
    window.setTimeout(() => { element.hidden = true; }, reducedMotion ? 160 : 260);
  }, isError ? 4200 : 2800);
}

async function api(path, body) {
  const bridge = window.pywebview?.api;
  if (bridge) {
    try {
      if (path.startsWith('/api/state')) return await bridge.get_state(path.includes('refresh=1'));
      if (path === '/api/plan') return await bridge.make_plan(body || {});
      if (path === '/api/apply') return await bridge.apply(body || {});
      if (path === '/api/restore') return await bridge.restore();
      if (path === '/api/reveal') return await bridge.reveal_folder();
      if (path === '/api/choose-root') return await bridge.choose_steam_root();
      if (path === '/api/open-log') return await bridge.open_log_file();
      if (path === '/api/local-games/scan') return await bridge.scan_local_games(body || {});
      if (path === '/api/local-games/cancel') return await bridge.cancel_local_scan();
      if (path === '/api/local-games/import') return await bridge.import_local_games(body || {});
      if (path === '/api/local-games/undo') return await bridge.undo_local_import();
      if (path === '/api/local-games/folder') return await bridge.choose_game_folder();
      if (['/api/library/load', '/api/library/cover', '/api/library/edit', '/api/library/preview', '/api/library/publish'].includes(path)) return await bridge.manage_library(path.split('/').pop(), body || {});
      if (['load', 'current', 'search', 'preview', 'apply', 'auto', 'undo'].some(action => path === `/api/artwork/${action}`)) return await bridge.manage_artwork(path.split('/').pop(), body || {});
      throw new Error(`未知本地操作：${path}`);
    } catch (error) {
      const message = error?.message || String(error || '本地操作失败');
      throw new Error(message.replace(/^Error:\s*/, ''));
    }
  }

  let options = {};
  if (body !== undefined) {
    if (!state.csrfToken) {
      throw new Error('安全令牌缺失，请重新扫描后再试');
    }
    options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Steam-Organizer-Token': state.csrfToken,
      },
      body: JSON.stringify(body),
    };
  }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.error) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function maskedAccount(value) {
  const text = String(value || '');
  if (state.showAccountId || text.length < 9) return text;
  return `${text.slice(0, 5)}••••${text.slice(-4)}`;
}

function setSteamPill(kind, label, title = '') {
  const pill = $('steam-pill');
  pill.className = `pill pill-${kind}`;
  pill.title = title;
  pill.replaceChildren(make('span', 'pill-dot'), make('span', 'pill-label', label));
}

function updateProgress() {
  let current = 1;
  if (state.scanReady) current = 2;
  if (state.plan.length) current = 3;
  if (state.busy.apply || state.planCommitted) current = 4;
  document.querySelectorAll('.progress-step').forEach((step) => {
    const value = Number(step.dataset.step);
    step.classList.toggle('is-current', value === current);
    step.classList.toggle('is-complete', value < current);
    if (value === current) step.setAttribute('aria-current', 'step');
    else step.removeAttribute('aria-current');
    const index = step.querySelector('.progress-index');
    index.textContent = value < current ? '✓' : String(value);
  });
}

function currentPlanConfig() {
  return {
    modes: MODE_CARDS.map((mode) => mode.id).filter((id) => state.modes.includes(id)),
    developer_min: Math.min(100, Math.max(1, numberOr($('developer-min').value, 3))),
    language: state.language,
    scope: state.scope,
  };
}

function configsEqual(left, right) {
  return Boolean(left && right && JSON.stringify(left) === JSON.stringify(right));
}

function syncPlanFreshness(message = '') {
  savePreferences();
  syncRuleControls();
  if (!state.plan.length) {
    state.planFresh = false;
    $('plan-status').textContent = state.scanReady ? '选择分类方式，再生成预览。' : '扫描完成后可生成预览。';
    updateProgress();
    updateActionState();
    return;
  }

  state.planFresh = Boolean(state.planId) && !state.planCommitted && configsEqual(state.planConfig, currentPlanConfig());
  const panel = $('preview-panel');
  panel.classList.toggle('is-stale', !state.planFresh);
  $('stale-banner').hidden = state.planFresh;
  $('preview-badge').textContent = state.planCommitted ? '已写入' : (state.planFresh ? '待确认' : '需要更新');
  if (state.planFresh) {
    $('plan-status').textContent = '勾选要写入的分类。';
  } else {
    $('stale-banner').textContent = message || (state.planCommitted
      ? '这些分类已写入 Steam。再次写入前，请重新生成预览。'
      : '设置已更改，请重新生成预览后再写入。');
    $('plan-status').textContent = state.planCommitted
      ? '已写入 Steam。再次整理前，请重新生成预览。'
      : '设置已改变，请重新生成预览。';
  }
  updateProgress();
  updateActionState();
}

/* Classification controls ---------------------------------------------- */
function renderModes() {
  const host = $('modes');
  host.replaceChildren();
  MODE_CARDS.forEach((card) => {
    const button = make('button', `mode${state.modes.includes(card.id) ? ' is-on' : ''}`);
    button.type = 'button';
    button.dataset.mode = card.id;
    button.setAttribute('aria-pressed', String(state.modes.includes(card.id)));
    button.innerHTML = `<span class="mode-icon" aria-hidden="true">${ICONS[card.icon]}</span>
      <span class="mode-text"><span class="mode-title">${card.title}</span>
      <span class="mode-sub">${card.sub}</span></span>`;
    button.addEventListener('click', () => {
      const enabled = state.modes.includes(card.id);
      state.modes = enabled
        ? state.modes.filter((mode) => mode !== card.id)
        : MODE_CARDS.map((mode) => mode.id).filter((mode) => [...state.modes, card.id].includes(mode));
      button.classList.toggle('is-on', !enabled);
      button.setAttribute('aria-pressed', String(!enabled));
      updateCompanyOptions();
      syncPlanFreshness();
    });
    host.appendChild(button);
  });
  updateCompanyOptions();
  syncRuleControls();
}

function updateCompanyOptions() {
  $('company-options').hidden = !state.modes.some((mode) => mode === 'developer' || mode === 'publisher');
}

function scopeMetric(value, scope = state.scope) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return numberOr(value[scope] ?? value.total, 0);
  }
  return numberOr(value, 0);
}

function countForScope(scope, counts = state.server?.counts || {}) {
  if (scope === 'library') return numberOr(counts.library, numberOr(counts.games, numberOr(counts.candidates, 0)));
  if (scope === 'games') return numberOr(counts.games, numberOr(counts.named, numberOr(counts.candidates, 0)));
  return numberOr(counts.all, numberOr(counts.candidates, numberOr(counts.library, 0)));
}

function normalizeScopes(rawScopes) {
  const lookup = {};
  if (Array.isArray(rawScopes)) {
    rawScopes.forEach((entry) => {
      if (typeof entry === 'string') lookup[entry] = {};
      else if (entry && typeof entry === 'object') lookup[entry.id || entry.key] = entry;
    });
  } else if (rawScopes && typeof rawScopes === 'object') {
    Object.entries(rawScopes).forEach(([key, value]) => {
      lookup[key] = value && typeof value === 'object'
        ? value
        : { available: value !== false, count: Number.isFinite(Number(value)) ? Number(value) : undefined };
    });
  }

  return DEFAULT_SCOPES.map((fallback) => {
    const serverScope = lookup[fallback.id] || {};
    return {
      ...fallback,
      title: serverScope.title || serverScope.label || fallback.title,
      description: serverScope.description || serverScope.note || fallback.description,
      available: serverScope.available !== false && serverScope.enabled !== false,
      count: numberOr(serverScope.count, countForScope(fallback.id)),
    };
  });
}

function renderScopes() {
  const scopes = normalizeScopes(state.server?.scopes);
  const available = scopes.filter((scope) => scope.available);
  if (!available.some((scope) => scope.id === state.scope)) state.scope = available[0]?.id || 'library';

  const host = $('scopes');
  host.replaceChildren();
  scopes.forEach((scope) => {
    const label = make('label', 'scope-option');
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'scope';
    input.value = scope.id;
    input.checked = scope.id === state.scope;
    input.disabled = !scope.available;
    const card = make('span', 'scope-card');
    card.append(
      make('span', 'scope-name', scope.title),
      make('span', 'scope-count', formatNumber(scope.count)),
      make('span', 'scope-description', scope.description),
    );
    label.append(input, card);
    host.appendChild(label);
  });
}

function sourceSummary(sources) {
  if (!sources) {
    const counts = state.server?.counts || {};
    const parts = [];
    if (Number.isFinite(Number(counts.local))) parts.push(`本地记录 ${formatNumber(counts.local)}`);
    if (Number.isFinite(Number(counts.cached))) parts.push(`库缓存 ${formatNumber(counts.cached)}`);
    return parts.join(' · ');
  }
  if (Array.isArray(sources)) {
    return sources.map((source) => typeof source === 'string'
      ? source
      : `${source.label || source.name || source.id}${Number.isFinite(Number(source.count)) ? ` ${formatNumber(source.count)}` : ''}`
    ).join(' · ');
  }
  if (typeof sources === 'object') {
    const labels = {
      local: '本地记录',
      cached: '客户端缓存',
      installed: '已安装',
      session: 'API 会话',
    };
    return Object.entries(sources)
      .filter(([, value]) => Number.isFinite(Number(value)) || typeof value === 'string')
      .map(([key, value]) => `${labels[key] || key} ${Number.isFinite(Number(value)) ? formatNumber(value) : value}`)
      .join(' · ');
  }
  return String(sources);
}

function renderScanCounts() {
  if (!state.server?.counts) return;
  const counts = state.server.counts;
  const total = countForScope(state.scope, counts);
  const games = numberOr(counts.games, numberOr(counts.named, total));
  const all = numberOr(counts.all, numberOr(counts.candidates, total));
  const unresolved = scopeMetric(counts.unresolved ?? Math.max(0, all - numberOr(counts.named, all)));
  const auxiliary = scopeMetric(counts.auxiliary);
  const installed = numberOr(counts.installed, 0);
  const scope = normalizeScopes(state.server.scopes).find((item) => item.id === state.scope);

  $('stat-scope-label').textContent = scope?.title || '当前范围';
  $('stat-scope').textContent = formatNumber(total);
  $('stat-scope-note').textContent = state.scope === 'all' && auxiliary
    ? `含 ${formatNumber(auxiliary)} 个辅助条目`
    : '当前整理范围';
  $('stat-games').textContent = formatNumber(games);
  $('stat-games-note').textContent = counts.library !== undefined
    ? `游戏库 ${formatNumber(counts.library)}`
    : '名称已识别';
  $('stat-unresolved').textContent = formatNumber(unresolved);
  $('stat-unresolved-note').textContent = all
    ? `占本地记录 ${Math.min(100, (unresolved / all) * 100).toFixed(1)}%`
    : '名称或资料不完整';
  $('stat-installed').textContent = formatNumber(installed);

  const metadataError = state.server.appinfo_error;
  const scanWarnings = Array.isArray(state.server.scan_warnings)
    ? state.server.scan_warnings.filter(Boolean)
    : [];
  $('quality-title').textContent = metadataError
    ? '游戏资料读取失败，请重新扫描'
    : (unresolved
      ? `${formatNumber(unresolved)} 个条目资料不完整`
      : '游戏资料已就绪');
  const sources = sourceSummary(state.server.sources || counts.sources);
  $('quality-copy').textContent = [
    metadataError
      ? `${state.server.appinfo_stale ? '当前显示的是上一次成功读取的数据。' : '未能读取可用的游戏资料。'} 错误：${metadataError}`
      : '',
    sources ? `来源：${sources}。` : '',
    unresolved ? (state.scope === 'all' ? '“全部条目”包含资料不完整的条目。' : '当前范围不包含资料不完整的条目。') : '',
    auxiliary ? `${formatNumber(auxiliary)} 个 DLC、工具或辅助条目。` : '',
    scanWarnings.join(' '),
    '同一条目可能出现在多个范围中。',
  ].filter(Boolean).join(' ');
  $('quality-card').classList.toggle(
    'is-warning',
    unresolved > 0 || Boolean(metadataError) || scanWarnings.length > 0,
  );

  const collections = Array.isArray(state.server.collections) ? state.server.collections : [];
  const managed = collections.filter((collection) => collection.ours).length;
  const preserved = collections.length - managed;
  $('safety-copy').textContent = managed || preserved
    ? `${formatNumber(managed)} 个自动分类；保留 ${formatNumber(preserved)} 个其他分类。`
    : '写入前自动备份，保留其他 Steam 分类。';
}

function renderState(data) {
  if (!data?.counts) throw new Error('未能读取有效的 Steam 数据，请重新扫描');
  state.server = data;
  state.csrfToken = typeof data.csrf_token === 'string' && data.csrf_token
    ? data.csrf_token
    : null;
  state.scanReady = true;
  state.metadataReady = !data.appinfo_error;
  state.steamRunning = typeof data.steam_running === 'boolean' ? data.steam_running : null;
  $('connection-error').hidden = true;
  $('quality-card').hidden = false;
  $('scan-indicator').classList.add('is-connected');
  $('demo-badge').hidden = !data.demo;

  $('stats').setAttribute('aria-busy', 'false');
  $('account-line').textContent = data.steamid64
    ? `${data.steam_root} · 账号 ${maskedAccount(data.steamid64)}`
    : (data.steam_root || '已连接本机 Steam');
  $('account-line').title = data.steamid64
    ? `${data.steam_root} · 账号 ${state.showAccountId ? data.steamid64 : '已隐藏，点击可更换 Steam 目录'}`
    : (data.steam_root || '点击选择 Steam 目录');

  if (state.steamRunning === true) {
    setSteamPill('warn', 'Steam 运行中 · 仅可预览');
  } else if (state.steamRunning === false) {
    setSteamPill('ok', 'Steam 已退出 · 可写入');
  } else {
    setSteamPill('warn', '无法确认 Steam 状态', data.steam_check_error || '');
  }

  renderScopes();
  renderScanCounts();
  if (!state.metadataReady) {
    $('plan-status').textContent = '游戏资料未就绪，请重新扫描。';
  } else if (!state.plan.length) {
    $('plan-status').textContent = '选择分类方式，再生成预览。';
  }
  updateProgress();
  updateActionState();
}

async function refreshState(silent = false) {
  if (Object.values(state.busy).some(Boolean)) return;
  if (!silent && state.plan.length) {
    state.planConfig = null;
    syncPlanFreshness('数据已重新扫描，请重新生成预览。');
  }
  state.busy.scan = true;
  $('stats').setAttribute('aria-busy', 'true');
  if (!silent) setSteamPill('wait', '正在扫描本机 Steam…');
  updateActionState();
  try {
    const data = await api(silent ? '/api/state' : '/api/state?refresh=1');
    renderState(data);
    if (!silent) {
      const total = countForScope(state.scope, data.counts);
      log(`扫描完成：当前范围 ${formatNumber(total)} 个条目`, 'good');
    }
  } catch (error) {
    state.scanReady = false;
    state.metadataReady = false;
    state.steamRunning = null;
    state.csrfToken = null;
    state.planConfig = null;
    if (state.plan.length) syncPlanFreshness('无法读取当前游戏库，请重新连接后生成预览。');
    $('stats').setAttribute('aria-busy', 'false');
    $('scan-indicator').classList.remove('is-connected');
    $('connection-error').hidden = false;
    $('connection-error-copy').textContent = error.message;
    $('account-line').textContent = '点击选择 Steam 安装目录';
    $('quality-card').hidden = true;
    ['stat-scope', 'stat-games', 'stat-installed', 'stat-unresolved'].forEach((id) => { $(id).textContent = '—'; });
    setSteamPill('warn', '读取失败', error.message);
    $('plan-status').textContent = `无法读取 Steam：${error.message}`;
    if (!silent) log(`读取 Steam 状态失败：${error.message}`, 'error');
  } finally {
    state.busy.scan = false;
    updateProgress();
    updateActionState();
  }
}

/* Preview --------------------------------------------------------------- */
function normalizeSummary(raw, groups) {
  const appids = new Set(groups.flatMap((group) => Array.isArray(group.appids) ? group.appids : []));
  const memberships = groups.reduce((total, group) => total + numberOr(group.count, group.appids?.length || 0), 0);
  const missingFromGroups = new Set(
    groups
      .filter((group) => /资料缺失|未识别/.test(`${group.bucket || ''} ${group.name || ''}`))
      .flatMap((group) => Array.isArray(group.appids) ? group.appids : []),
  ).size;
  return {
    unique_apps: numberOr(raw?.unique_apps, appids.size),
    memberships: numberOr(raw?.memberships, memberships),
    missing_metadata: scopeMetric(raw?.missing_metadata ?? missingFromGroups),
    mode_stats: raw?.mode_stats || {},
    existing_managed: numberOr(raw?.existing_managed, (state.server?.collections || []).filter((item) => item.ours).length),
    manual_preserved: numberOr(raw?.manual_preserved, (state.server?.collections || []).filter((item) => !item.ours).length),
    warnings: Array.isArray(raw?.warnings) ? raw.warnings : [],
  };
}

function warningText(warning) {
  if (typeof warning === 'string') return warning;
  if (warning && typeof warning === 'object') return warning.message || warning.text || warning.title || '';
  return '';
}

function renderWarnings() {
  const host = $('preview-warnings');
  host.replaceChildren();
  const warnings = (state.planSummary?.warnings || []).map(warningText).filter(Boolean);
  if (!warnings.length && state.planSummary?.missing_metadata > 0) {
    warnings.push(`${formatNumber(state.planSummary.missing_metadata)} 个条目的分类资料不完整，请重点检查“资料缺失”分组。`);
  }
  const largest = state.plan.reduce((best, group) => numberOr(group.count) > numberOr(best?.count) ? group : best, null);
  if (!warnings.length && largest && numberOr(largest.count) > Math.max(100, state.planSummary.unique_apps * 0.5)) {
    warnings.push(`“${largest.name}”包含 ${formatNumber(largest.count)} 个条目，建议确认这个大分组是否有帮助。`);
  }
  warnings.forEach((warning) => host.appendChild(make('p', 'warning-item', warning)));
  host.hidden = warnings.length === 0;
}

function selectedGroups() {
  return state.plan.filter((group) => state.selected.has(String(group.id)));
}

function selectedSummary() {
  const groups = selectedGroups();
  const appids = new Set(groups.flatMap((group) => Array.isArray(group.appids) ? group.appids : []));
  const memberships = groups.reduce((total, group) => total + numberOr(group.count, group.appids?.length || 0), 0);
  const uniqueApps = appids.size || (groups.length === state.plan.length ? numberOr(state.planSummary?.unique_apps) : 0);
  return { groups: groups.length, uniqueApps, memberships };
}

function updateSectionCheckboxes() {
  document.querySelectorAll('.mode-section').forEach((section) => {
    const groupChecks = [...section.querySelectorAll('.group:not([data-filtered="true"]) .group-checkbox')];
    const sectionCheck = section.querySelector('.mode-checkbox');
    const selected = groupChecks.filter((input) => input.checked).length;
    sectionCheck.checked = selected === groupChecks.length && groupChecks.length > 0;
    sectionCheck.indeterminate = selected > 0 && selected < groupChecks.length;
  });
}

function renderSelectionSummary() {
  const summary = selectedSummary();
  $('preview-groups').textContent = formatNumber(summary.groups);
  $('preview-unique').textContent = formatNumber(summary.uniqueApps);
  $('preview-memberships').textContent = formatNumber(summary.memberships);
  $('preview-missing').textContent = formatNumber(state.planSummary?.missing_metadata || 0);
  updateSectionCheckboxes();
  updateProgress();
  updateActionState();
}

function modeStat(mode, groups) {
  const raw = Array.isArray(state.planSummary?.mode_stats)
    ? state.planSummary.mode_stats.find((item) => item.mode === mode || item.id === mode)
    : state.planSummary?.mode_stats?.[mode];
  const unique = new Set(groups.flatMap((group) => Array.isArray(group.appids) ? group.appids : []));
  return {
    groups: numberOr(raw?.groups ?? raw?.count, groups.length),
    unique: numberOr(raw?.unique_apps ?? raw?.apps, unique.size),
  };
}

function createGroup(group, groupIndex) {
  const groupId = String(group.id);
  const article = make('article', 'group is-on');
  article.dataset.id = groupId;
  article.style.setProperty('--row-index', String(Math.min(groupIndex, 10)));

  const row = make('div', 'group-row');
  const choice = make('label', 'group-choice');
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.className = 'native-check group-checkbox';
  checkbox.checked = true;
  checkbox.setAttribute('aria-label', `选择分类 ${group.name}`);
  const name = make('span', 'group-name', group.name || group.bucket || groupId);
  choice.append(checkbox, name);

  const count = make('span', 'group-count', `${formatNumber(group.count ?? group.appids?.length ?? 0)} 项`);
  const disclosure = make('button', 'disclosure');
  disclosure.type = 'button';
  disclosure.innerHTML = ICONS.caret;
  const bodyId = `group-detail-${groupIndex}`;
  disclosure.setAttribute('aria-expanded', 'false');
  disclosure.setAttribute('aria-controls', bodyId);
  disclosure.setAttribute('aria-label', `展开 ${group.name || '分类'} 的示例`);
  row.append(choice, count, disclosure);

  const body = make('div', 'group-body');
  body.id = bodyId;
  body.hidden = true;
  const sample = Array.isArray(group.sample) && group.sample.length
    ? group.sample
    : (Array.isArray(group.appids) ? group.appids.slice(0, 6).map((appid) => `App ${appid}`) : []);
  article.dataset.search = `${group.name || ''} ${group.bucket || ''} ${sample.join(' ')}`.toLocaleLowerCase('zh-CN');
  body.appendChild(make('p', 'sample-label', sample.length
    ? `示例 ${formatNumber(sample.length)} / ${formatNumber(group.count ?? group.appids?.length ?? sample.length)}`
    : '暂无名称示例'));
  if (sample.length) {
    const chips = make('div', 'chips');
    sample.forEach((item) => chips.appendChild(make('span', 'chip', item)));
    body.appendChild(chips);
  }

  checkbox.addEventListener('change', () => {
    if (checkbox.checked) state.selected.add(groupId); else state.selected.delete(groupId);
    article.classList.toggle('is-on', checkbox.checked);
    renderSelectionSummary();
  });

  disclosure.addEventListener('click', () => {
    const expanded = disclosure.getAttribute('aria-expanded') === 'true';
    disclosure.setAttribute('aria-expanded', String(!expanded));
    disclosure.setAttribute('aria-label', `${expanded ? '展开' : '收起'} ${group.name || '分类'} 的示例`);
    body.hidden = expanded;
  });

  article.append(row, body);
  return article;
}

function createModeSection(mode, groups, runningIndex) {
  const info = MODE_BY_ID[mode] || { title: mode || '其他分类' };
  const section = make('section', 'mode-section');
  section.dataset.mode = mode;
  section.style.animationDelay = `${Math.min(runningIndex * 14, 140)}ms`;

  const heading = make('div', 'mode-section-head');
  const select = make('label', 'mode-select');
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.className = 'native-check mode-checkbox';
  checkbox.checked = true;
  checkbox.setAttribute('aria-label', `选择全部${info.title}分类`);
  select.append(checkbox, make('span', 'mode-section-name', info.title));
  const stat = modeStat(mode, groups);
  heading.append(select, make('span', 'mode-section-meta', `${formatNumber(stat.groups)} 个分类 · ${formatNumber(stat.unique)} 个条目`));

  const list = make('div', 'mode-section-list');
  groups.forEach((group, index) => list.appendChild(createGroup(group, runningIndex + index)));

  checkbox.addEventListener('change', () => {
    list.querySelectorAll('.group:not([data-filtered="true"])').forEach((row) => {
      const id = row.dataset.id;
      if (checkbox.checked) state.selected.add(id); else state.selected.delete(id);
      row.classList.toggle('is-on', checkbox.checked);
      row.querySelector('.group-checkbox').checked = checkbox.checked;
    });
    renderSelectionSummary();
  });

  section.append(heading, list);
  return section;
}

function renderGroups(groups) {
  state.plan = groups;
  state.selected = new Set(groups.map((group) => String(group.id)));
  const host = $('groups');
  host.replaceChildren();
  $('preview-panel').classList.add('has-preview');
  $('preview-empty').hidden = groups.length > 0;
  $('empty-title').textContent = '没有可分类的条目';
  $('empty-copy').textContent = '换个范围或分类方式再试。';
  $('preview-panel').classList.toggle('has-plan', groups.length > 0);
  if (!groups.length) {
    $('preview-panel').classList.remove('is-stale');
    $('stale-banner').hidden = true;
  }
  $('preview-stats').hidden = groups.length === 0;
  $('preview-badge').textContent = groups.length ? '待确认' : '无可用分类';

  const byMode = new Map();
  groups.forEach((group) => {
    const mode = group.mode || String(group.id || '').split(':', 1)[0] || 'other';
    if (!byMode.has(mode)) byMode.set(mode, []);
    byMode.get(mode).push(group);
  });

  const orderedModes = [
    ...MODE_CARDS.map((mode) => mode.id).filter((mode) => byMode.has(mode)),
    ...[...byMode.keys()].filter((mode) => !MODE_BY_ID[mode]),
  ];
  let runningIndex = 0;
  orderedModes.forEach((mode) => {
    const modeGroups = byMode.get(mode);
    host.appendChild(createModeSection(mode, modeGroups, runningIndex));
    runningIndex += modeGroups.length;
  });

  $('preview-panel').hidden = false;
  $('preview-context').textContent = `将替换 ${formatNumber(state.planSummary.existing_managed)} 个旧自动分类；${formatNumber(state.planSummary.manual_preserved)} 个其他分类保持不变。`;
  renderWarnings();
  renderSelectionSummary();
  $('preview-search').value = '';
  filterPreview();
  $('preview-scroll').scrollTop = 0;
}

async function makePlan() {
  if (!state.scanReady || !state.metadataReady || !state.modes.length || Object.values(state.busy).some(Boolean)) return;
  const config = currentPlanConfig();
  state.busy.plan = true;
  state.planConfig = null;
  state.planFresh = false;
  $('plan-status').textContent = '正在生成预览…';
  updateActionState();
  try {
    const data = await api('/api/plan', config);
    if (!Array.isArray(data.groups)) throw new Error('预览数据格式不完整');
    state.planId = data.plan_id || null;
    state.planConfig = config;
    state.planCommitted = false;
    state.planFresh = configsEqual(config, currentPlanConfig());
    state.planSummary = normalizeSummary(data.summary, data.groups);
    window.dispatchEvent(new CustomEvent('organizer-preview-will-render'));
    renderGroups(data.groups);
    syncPlanFreshness();
    $('result-panel').hidden = true;
    window.dispatchEvent(new CustomEvent('organizer-preview-ready'));
    log(`预览已生成：${formatNumber(data.groups.length)} 个分类，${formatNumber(state.planSummary.unique_apps)} 个唯一条目，${formatNumber(state.planSummary.memberships)} 次归属`, 'good');
    $('preview-search').focus({ preventScroll: true });
  } catch (error) {
    state.planConfig = null;
    state.planFresh = false;
    syncPlanFreshness(`生成预览失败：${error.message}`);
    $('plan-status').textContent = `生成预览失败：${error.message}`;
    log(`生成预览失败：${error.message}`, 'error');
    toast(error.message, true);
  } finally {
    state.busy.plan = false;
    updateActionState();
  }
}

/* Dialog --------------------------------------------------------------- */
const sheet = {
  host: null,
  scrim: null,
  offset: 0,
  animation: null,
  lastFocus: null,
  onConfirm: null,
  dismissible: true,
  confirmLabel: '确认',

  init() {
    this.host = $('sheet');
    this.scrim = $('scrim');
    $('sheet-cancel').addEventListener('click', () => this.close());
    $('sheet-close').addEventListener('click', () => this.close());
    $('sheet-confirm').addEventListener('click', () => this.onConfirm?.());
    this.scrim.addEventListener('click', () => this.close());
    this.host.addEventListener('keydown', (event) => this.handleKeydown(event));
    this.setupDrag();
  },

  handleKeydown(event) {
    if (event.key === 'Escape') {
      if (this.dismissible) this.close();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = [...this.host.querySelectorAll('button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')]
      .filter((element) => !element.hidden && element.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  },

  setupDrag() {
    const grip = $('sheet-grip');
    let startY = 0;
    let startOffset = 0;
    let lastY = 0;
    let lastTime = 0;
    let velocity = 0;
    let dragging = false;

    grip.addEventListener('pointerdown', (event) => {
      if (!mobileSheetQuery.matches || !this.dismissible) return;
      dragging = true;
      this.animation?.stop();
      grip.setPointerCapture(event.pointerId);
      startY = event.clientY;
      startOffset = this.offset;
      lastY = event.clientY;
      lastTime = performance.now();
      velocity = 0;
    });

    grip.addEventListener('pointermove', (event) => {
      if (!dragging) return;
      const rawOffset = startOffset + event.clientY - startY;
      const nextOffset = rawOffset < 0 ? rawOffset * 0.14 : rawOffset;
      const now = performance.now();
      const elapsed = now - lastTime;
      if (elapsed > 8) {
        velocity = ((event.clientY - lastY) / elapsed) * 1000;
        lastY = event.clientY;
        lastTime = now;
      }
      this.setMobileOffset(nextOffset);
    });

    const finish = () => {
      if (!dragging) return;
      dragging = false;
      const height = this.host.offsetHeight;
      const shouldClose = velocity > 520 || this.offset > height * 0.42;
      if (shouldClose) this.scrim.classList.remove('is-open');
      this.animateMobile(shouldClose ? height : 0, velocity, shouldClose);
    };
    grip.addEventListener('pointerup', finish);
    grip.addEventListener('pointercancel', finish);
  },

  setMobileOffset(value) {
    this.offset = value;
    this.host.style.setProperty('--sheet-y', `${value}px`);
    const height = Math.max(1, this.host.offsetHeight);
    const opacity = Math.max(0, Math.min(1, 1 - Math.max(0, value) / height));
    this.scrim.style.opacity = String(opacity);
  },

  animateMobile(to, velocity = 0, thenHide = false) {
    this.animation?.stop();
    this.animation = spring({
      from: this.offset,
      to,
      velocity,
      damping: 1,
      response: 0.34,
      onUpdate: (value) => this.setMobileOffset(value),
      onDone: () => {
        this.offset = to;
        this.scrim.style.opacity = '';
        if (thenHide) this.hide();
      },
    });
  },

  open({ kicker = '确认操作', title, body, note = '', confirmLabel = '确认', danger = false, onConfirm }) {
    this.lastFocus = document.activeElement;
    this.onConfirm = onConfirm;
    this.dismissible = true;
    this.confirmLabel = confirmLabel;
    $('sheet-kicker').textContent = kicker;
    $('sheet-title').textContent = title;
    const bodyHost = $('sheet-body');
    bodyHost.replaceChildren();
    if (body instanceof Node) bodyHost.appendChild(body); else bodyHost.textContent = String(body || '');
    $('sheet-note').textContent = note;
    $('sheet-note').hidden = !note;
    $('sheet-note').classList.toggle('is-warning', danger);
    $('sheet-error').hidden = true;
    $('sheet-error').textContent = '';
    const confirm = $('sheet-confirm');
    confirm.textContent = confirmLabel;
    confirm.classList.toggle('btn-danger', danger);
    this.setBusy(false);

    this.host.hidden = false;
    this.scrim.hidden = false;
    document.body.classList.add('modal-open');
    [$('page-header'), $('workspace'), $('actionbar'), $('diagnostics'), document.querySelector('.progress-rail')].forEach((element) => { element.inert = true; });

    this.scrim.style.opacity = '';
    requestAnimationFrame(() => {
      this.scrim.classList.add('is-open');
      this.host.classList.add('is-open');
      if (mobileSheetQuery.matches) {
        this.offset = this.host.offsetHeight || 360;
        this.host.style.setProperty('--sheet-y', `${this.offset}px`);
        requestAnimationFrame(() => this.animateMobile(0));
      }
      window.setTimeout(() => $('sheet-cancel').focus(), reducedMotion ? 0 : 100);
    });
  },

  setBusy(busy, label = '') {
    this.dismissible = !busy;
    $('sheet-confirm').disabled = busy;
    $('sheet-cancel').disabled = busy;
    $('sheet-close').disabled = busy;
    $('sheet-confirm').textContent = busy ? (label || '正在处理…') : this.confirmLabel;
    this.host.setAttribute('aria-busy', String(busy));
  },

  setError(message) {
    const error = $('sheet-error');
    error.textContent = message;
    error.hidden = false;
    error.focus?.();
  },

  close() {
    if (!this.dismissible || this.host.hidden) return;
    this.scrim.classList.remove('is-open');
    if (mobileSheetQuery.matches) {
      this.animateMobile(this.host.offsetHeight, 0, true);
    } else {
      this.host.classList.remove('is-open');
      window.setTimeout(() => this.hide(), reducedMotion ? 160 : 240);
    }
  },

  hide() {
    this.animation?.stop();
    this.host.classList.remove('is-open');
    this.scrim.classList.remove('is-open');
    this.scrim.style.opacity = '';
    this.host.style.removeProperty('--sheet-y');
    this.host.hidden = true;
    this.scrim.hidden = true;
    this.offset = 0;
    document.body.classList.remove('modal-open');
    [$('page-header'), $('workspace'), $('actionbar'), $('diagnostics'), document.querySelector('.progress-rail')].forEach((element) => { element.inert = false; });
    if (this.lastFocus instanceof HTMLElement) this.lastFocus.focus();
  },
};

function confirmBody(intro, summary) {
  const fragment = document.createDocumentFragment();
  fragment.appendChild(make('p', '', intro));
  if (summary) {
    const metrics = make('div', 'confirm-metrics');
    [
      [summary.groups, '分类'],
      [summary.uniqueApps, '条目数（去重）'],
      [summary.memberships, '归类次数'],
    ].forEach(([value, label]) => {
      const item = make('div');
      item.append(make('strong', '', formatNumber(value)), make('span', '', label));
      metrics.appendChild(item);
    });
    fragment.appendChild(metrics);
  }
  return fragment;
}

function showResult(title, copy, path = '') {
  $('result-title').textContent = title;
  $('result-copy').textContent = copy;
  $('result-path').textContent = path;
  $('result-path').hidden = !path;
  $('result-panel').hidden = false;
}

function askApply() {
  const summary = selectedSummary();
  if (!state.planFresh || !summary.groups || state.steamRunning !== false || Object.values(state.busy).some(Boolean)) return;
  sheet.open({
    kicker: '最后确认',
    title: '备份并写入 Steam',
    body: confirmBody('先备份，再替换本工具生成的旧自动分类。其他分类保留。', summary),
    note: `请先完全退出 Steam。将替换 ${formatNumber(state.planSummary.existing_managed)} 个旧自动分类，并保留 ${formatNumber(state.planSummary.manual_preserved)} 个其他分类。`,
    confirmLabel: `备份并写入 ${formatNumber(summary.groups)} 个分类`,
    onConfirm: async () => {
      state.busy.apply = true;
      sheet.setBusy(true, '正在备份并写入…');
      updateActionState();
      try {
        const payload = { selected: [...state.selected] };
        if (state.planId) payload.plan_id = state.planId;
        const data = await api('/api/apply', payload);
        if (data.state) renderState(data.state); else await refreshState(true);
        if (data.state_error) log(`写入已完成，但状态刷新失败：${data.state_error}`);
        log(`写入完成：${formatNumber(data.collections ?? summary.groups)} 个分类，${formatNumber(data.apps ?? summary.uniqueApps)} 个条目`, 'good');
        if (data.backup) log(`写入前备份：${data.backup}`);
        showResult('写入完成', '重启 Steam 后可在游戏库左侧查看新分类。如需撤销，可恢复备份。', data.backup || '');
        state.planCommitted = true;
        state.planFresh = false;
        syncPlanFreshness('这份预览已成功写入。如需再次整理，请重新生成预览。');
        toast('写入完成，重启 Steam 后查看分类');
        sheet.setBusy(false);
        sheet.close();
      } catch (error) {
        log(`写入失败：${error.message}`, 'error');
        sheet.setError(`写入失败：${error.message}`);
        toast('写入失败，请查看窗口中的错误信息', true);
        sheet.setBusy(false);
      } finally {
        state.busy.apply = false;
        updateActionState();
      }
    },
  });
}

function askRestore() {
  if (!state.scanReady || state.steamRunning !== false || Object.values(state.busy).some(Boolean)) return;
  sheet.open({
    kicker: '恢复保护',
    title: '恢复最近一次备份？',
    body: confirmBody('将用最近一次备份替换当前 Steam 分类。恢复后，重启 Steam 查看结果。'),
    note: '请先完全退出 Steam。恢复前会备份当前分类，再次恢复可撤销这次操作。',
    confirmLabel: '备份并恢复',
    danger: true,
    onConfirm: async () => {
      state.busy.restore = true;
      sheet.setBusy(true, '正在安全恢复…');
      updateActionState();
      try {
        const data = await api('/api/restore', {});
        if (data.state) renderState(data.state); else await refreshState(true);
        if (data.state_error) log(`恢复已完成，但状态刷新失败：${data.state_error}`);
        const safetyBackup = data.safety_backup || '';
        log(`已恢复备份：${data.restored}`, 'good');
        if (safetyBackup) log(`恢复前安全备份：${safetyBackup}`);
        showResult('备份已恢复', '已恢复到最近一次备份。重启 Steam 后查看分类。', safetyBackup ? `恢复前安全备份：${safetyBackup}` : (data.restored || ''));
        state.planConfig = null;
        state.planFresh = false;
        state.planCommitted = false;
        if (state.plan.length) syncPlanFreshness('收藏夹已经恢复，原预览不再对应当前状态，请重新生成。');
        toast('已恢复最近备份');
        sheet.setBusy(false);
        sheet.close();
      } catch (error) {
        log(`恢复失败：${error.message}`, 'error');
        sheet.setError(`恢复失败：${error.message}`);
        toast('恢复失败，请查看窗口中的错误信息', true);
        sheet.setBusy(false);
      } finally {
        state.busy.restore = false;
        updateActionState();
      }
    },
  });
}

async function revealFolder() {
  if (state.busy.reveal) return;
  state.busy.reveal = true;
  updateActionState();
  try {
    const data = await api('/api/reveal', {});
    log(`已打开配置目录：${data.opened || state.server?.steam_root || ''}`, 'good');
  } catch (error) {
    log(`打开配置目录失败：${error.message}`, 'error');
    toast(error.message, true);
  } finally {
    state.busy.reveal = false;
    updateActionState();
  }
}

async function chooseSteamRoot() {
  if (Object.values(state.busy).some(Boolean)) return;
  state.busy.root = true;
  closeMoreMenu();
  updateActionState();
  try {
    const data = await api('/api/choose-root', {});
    if (!data) return;
    state.plan = [];
    state.planId = null;
    state.planSummary = null;
    state.planConfig = null;
    state.planFresh = false;
    state.planCommitted = false;
    state.selected.clear();
    $('groups').replaceChildren();
    $('preview-empty').hidden = false;
    $('preview-panel').classList.remove('has-plan', 'has-preview', 'is-stale');
    $('stale-banner').hidden = true;
    $('preview-stats').hidden = true;
    $('preview-warnings').hidden = true;
    $('preview-badge').textContent = '尚未生成';
    $('preview-context').textContent = '确认分类后再写入 Steam。';
    $('empty-title').textContent = '尚未生成分类';
    $('empty-copy').textContent = '选择分类方式，再生成预览。';
    $('preview-search').value = '';
    filterPreview();
    $('result-panel').hidden = true;
    renderState(data.state || data);
    log(`已切换 Steam 目录：${(data.state || data).steam_root}`, 'good');
    toast('Steam 目录已更新');
  } catch (error) {
    log(`切换 Steam 目录失败：${error.message}`, 'error');
    toast(error.message, true);
  } finally {
    state.busy.root = false;
    updateProgress();
    updateActionState();
  }
}

async function openLogFile() {
  closeMoreMenu();
  try {
    await api('/api/open-log', {});
  } catch (error) {
    log(`打开日志文件失败：${error.message}`, 'error');
    toast(error.message, true);
  }
}

function closeMoreMenu() {
  $('more-menu').hidden = true;
  $('more-btn').setAttribute('aria-expanded', 'false');
}

function toggleMoreMenu() {
  const willOpen = $('more-menu').hidden;
  $('more-menu').hidden = !willOpen;
  $('more-btn').setAttribute('aria-expanded', String(willOpen));
  if (willOpen) $('more-menu').querySelector('button:not([disabled])')?.focus();
}

function filterPreview() {
  const query = $('preview-search').value.trim().toLocaleLowerCase('zh-CN');
  document.querySelectorAll('.group').forEach((row) => {
    const filtered = Boolean(query && !row.dataset.search.includes(query));
    row.dataset.filtered = String(filtered);
    row.hidden = filtered;
  });
  document.querySelectorAll('.mode-section').forEach((section) => {
    const visible = [...section.querySelectorAll('.group')].some((row) => row.dataset.filtered !== 'true');
    section.hidden = !visible;
  });
  const visibleCount = document.querySelectorAll('.group:not([data-filtered="true"])').length;
  $('search-empty').hidden = !query || !state.plan.length || visibleCount > 0;
  $('search-result-count').textContent = query && state.plan.length ? `${visibleCount} / ${state.plan.length} 个分类` : '';
  $('select-all').textContent = query ? '全选结果' : '全选';
  $('select-none').textContent = query ? '取消结果选择' : '取消全选';
  updateSectionCheckboxes();
  updateActionState();
}

function selectVisibleGroups(checked) {
  if (state.busy.apply || state.busy.restore || state.busy.plan) return;
  document.querySelectorAll('.group:not([data-filtered="true"])').forEach((row) => {
    if (checked) state.selected.add(row.dataset.id); else state.selected.delete(row.dataset.id);
    row.classList.toggle('is-on', checked);
    row.querySelector('.group-checkbox').checked = checked;
  });
  renderSelectionSummary();
}

function updateActionState() {
  window.dispatchEvent(new CustomEvent('organizer-state-change'));
  updateProgress();
  const anyBusy = Object.values(state.busy).some(Boolean);
  document.documentElement.dataset.activity = ['apply', 'restore', 'plan', 'scan', 'root'].find((key) => state.busy[key]) || 'idle';
  const summary = selectedSummary();
  const planButton = $('plan-btn');
  const applyButton = $('apply-btn');
  planButton.disabled = anyBusy || !state.scanReady || !state.metadataReady || state.modes.length === 0;
  planButton.textContent = state.busy.plan ? '正在生成…' : (state.plan.length ? '更新预览' : '生成预览');

  let applyBlock = '';
  if (state.busy.apply) applyBlock = '正在写入';
  else if (!state.scanReady) applyBlock = '请先完成扫描';
  else if (!state.metadataReady) applyBlock = 'Steam 元数据未就绪，请重新扫描';
  else if (!state.plan.length) applyBlock = '请先生成预览';
  else if (!state.planFresh) applyBlock = '预览已过期，请重新生成';
  else if (!summary.groups) applyBlock = '请至少选择一个分类';
  else if (state.steamRunning === true) applyBlock = '请先完全退出 Steam';
  else if (state.steamRunning !== false) applyBlock = '无法确认 Steam 状态，请重新扫描';
  else if (anyBusy) applyBlock = '请等待当前操作完成';

  applyButton.disabled = Boolean(applyBlock);
  applyButton.title = applyBlock;

  const needsPlan = !state.plan.length || !state.planFresh;
  planButton.hidden = !needsPlan;
  applyButton.hidden = needsPlan;

  const applyLabel = applyButton.querySelector('.btn-label');
  if (state.busy.apply) applyLabel.textContent = '正在备份并写入…';
  else if (state.steamRunning === true) applyLabel.textContent = '退出 Steam 后即可写入';
  else if (!summary.groups) applyLabel.textContent = '请至少选择一个分类';
  else applyLabel.textContent = `备份并写入 ${formatNumber(summary.groups)} 个分类`;

  if (state.busy.scan) {
    $('action-title').textContent = '正在扫描 Steam';
    $('action-hint').textContent = '读取本地游戏记录';
  } else if (!state.scanReady) {
    $('action-title').textContent = '尚未连接 Steam';
    $('action-hint').textContent = '重新扫描或选择安装目录';
  } else if (state.busy.plan) {
    $('action-title').textContent = '正在生成预览';
    $('action-hint').textContent = '预览不会改动 Steam';
  } else if (!state.metadataReady) {
    $('action-title').textContent = '游戏资料未就绪';
    $('action-hint').textContent = '请重新扫描';
  } else if (!state.plan.length && state.planId) {
    $('action-title').textContent = '没有可用分类';
    $('action-hint').textContent = '换个范围或规则再试';
  } else if (!state.plan.length) {
    $('action-title').textContent = '可以生成预览';
    $('action-hint').textContent = state.modes.length ? '先预览，再写入' : '请至少选择一种分类方式';
  } else if (!state.planFresh) {
    $('action-title').textContent = '预览需要更新';
    $('action-hint').textContent = '规则或数据已改变，请重新生成';
  } else if (state.steamRunning === true) {
    $('action-title').textContent = '当前仅可预览';
    $('action-hint').textContent = '完全退出 Steam 后即可备份并写入';
  } else if (applyBlock) {
    $('action-title').textContent = '预览暂不可写入';
    $('action-hint').textContent = applyBlock;
  } else {
    $('action-title').textContent = '分类已就绪';
    $('action-hint').textContent = `${formatNumber(summary.groups)} 个分类 · ${formatNumber(summary.uniqueApps)} 个条目`;
  }

  $('restore-btn').disabled = anyBusy || !state.scanReady || state.steamRunning !== false;
  $('restore-btn').title = state.steamRunning === true
    ? '请先完全退出 Steam'
    : (state.steamRunning === null ? '无法确认 Steam 状态，请重新扫描' : '');
  $('reveal-btn').disabled = state.busy.reveal || !state.scanReady;
  $('choose-root-btn').disabled = state.busy.root || state.busy.apply || state.busy.restore;
  $('refresh-btn').disabled = anyBusy;
  $('choose-root-btn').disabled = anyBusy;
  $('connect-steam-btn').disabled = anyBusy;
  $('account-line').disabled = anyBusy;
  const configBusy = state.busy.plan || state.busy.apply || state.busy.restore || state.busy.root;
  document.querySelectorAll('.mode, .preset, .seg, .step-btn, #developer-min').forEach((element) => { element.disabled = configBusy; });
  document.querySelectorAll('#scopes input').forEach((element) => {
    const scope = normalizeScopes(state.server?.scopes).find((item) => item.id === element.value);
    element.disabled = configBusy || scope?.available === false;
  });
  document.querySelectorAll('.group-checkbox, .mode-checkbox').forEach((element) => { element.disabled = configBusy; });
  const noVisibleGroups = !document.querySelector('.group:not([data-filtered="true"])');
  $('select-all').disabled = configBusy || noVisibleGroups;
  $('select-none').disabled = configBusy || noVisibleGroups;
  $('preview-scroll').setAttribute('aria-busy', String(state.busy.plan));
  window.dispatchEvent(new CustomEvent('organizer-actions-updated'));
}

/* Boot ------------------------------------------------------------------ */
function boot() {
  if (state.booted) return;
  state.booted = true;
  const storedTheme = readStoredTheme();
  const initialTheme = storedTheme || (systemThemeQuery.matches ? 'light' : 'dark');
  applyTheme(initialTheme);
  loadPreferences();
  renderModes();
  renderScopes();
  sheet.init();
  $('preview-empty').hidden = false;
  updateActionState();
  refreshState();
  window.setInterval(() => refreshState(true), 20000);
  window.addEventListener('steam-organizer-close-blocked', () => {
    toast('正在备份、写入或恢复，请等待操作完成后再关闭窗口。', true);
  });

  $('refresh-btn').addEventListener('click', () => refreshState());
  $('account-line').addEventListener('click', chooseSteamRoot);
  $('choose-root-btn').addEventListener('click', chooseSteamRoot);
  $('connect-steam-btn').addEventListener('click', chooseSteamRoot);
  $('plan-btn').addEventListener('click', makePlan);
  $('apply-btn').addEventListener('click', askApply);
  $('restore-btn').addEventListener('click', askRestore);
  $('reveal-btn').addEventListener('click', revealFolder);
  $('open-log-btn').addEventListener('click', openLogFile);
  $('theme-btn').addEventListener('click', toggleTheme);
  $('quick-theme-btn').addEventListener('click', () => {
    const current = document.documentElement.dataset.theme;
    applyTheme(current === 'light' ? 'dark' : 'light', { persist: true, announce: true });
  });
  document.querySelectorAll('.preset').forEach((button) => {
    button.addEventListener('click', () => {
      state.modes = [...RULE_PRESETS[button.dataset.preset]];
      renderModes();
      syncPlanFreshness();
    });
  });
  $('more-btn').addEventListener('click', (event) => {
    event.stopPropagation();
    toggleMoreMenu();
  });
  $('more-menu').addEventListener('click', (event) => event.stopPropagation());
  $('more-menu').addEventListener('keydown', (event) => {
    const items = [...$('more-menu').querySelectorAll('button:not([disabled])')];
    const index = items.indexOf(document.activeElement);
    if (event.key === 'Escape') {
      event.preventDefault();
      closeMoreMenu();
      $('more-btn').focus();
    } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : (event.key === 'End' ? items.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length);
      items[next]?.focus();
    } else if (event.key === 'Tab') closeMoreMenu();
  });
  document.addEventListener('click', closeMoreMenu);
  $('privacy-btn').addEventListener('click', () => {
    state.showAccountId = !state.showAccountId;
    $('privacy-btn').setAttribute('aria-checked', String(state.showAccountId));
    $('privacy-btn').querySelector('span:last-child').textContent = state.showAccountId
      ? '重新隐藏完整账号'
      : '临时显示完整账号';
    if (state.server) renderState(state.server);
    closeMoreMenu();
  });
  $('preview-search').addEventListener('input', filterPreview);
  $('clear-search-btn').addEventListener('click', () => {
    $('preview-search').value = '';
    filterPreview();
    $('preview-search').focus();
  });

  $('scopes').addEventListener('change', (event) => {
    if (!event.target.matches('input[name="scope"]')) return;
    state.scope = event.target.value;
    renderScanCounts();
    syncPlanFreshness();
  });

  $('select-all').addEventListener('click', () => selectVisibleGroups(true));
  $('select-none').addEventListener('click', () => selectVisibleGroups(false));

  document.querySelectorAll('.step-btn').forEach((button) => {
    button.addEventListener('click', () => {
      const input = $('developer-min');
      input.value = Math.min(100, Math.max(1, numberOr(input.value, 3) + numberOr(button.dataset.step)));
      syncPlanFreshness();
    });
  });

  $('developer-min').addEventListener('input', () => syncPlanFreshness());
  $('developer-min').addEventListener('change', () => {
    $('developer-min').value = Math.min(100, Math.max(1, numberOr($('developer-min').value, 3)));
    syncPlanFreshness();
  });

  document.querySelectorAll('.seg').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.seg').forEach((other) => {
        const enabled = other === button;
        other.classList.toggle('is-on', enabled);
        other.setAttribute('aria-pressed', String(enabled));
      });
      state.language = button.dataset.lang;
      syncPlanFreshness();
    });
  });

  document.addEventListener('keydown', (event) => {
    if (document.querySelector('dialog[open]')) return;
    if (!$('sheet').hidden) return;
    if (!event.ctrlKey || event.altKey || event.metaKey) return;
    const key = event.key.toLowerCase();
    if (key === 'r') {
      event.preventDefault();
      refreshState();
    } else if (key === 'l') {
      event.preventDefault();
      $('diagnostics').open = !$('diagnostics').open;
    } else if (key === 'f') {
      event.preventDefault();
      $('preview-search').focus();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (!$('plan-btn').hidden && !$('plan-btn').disabled) makePlan();
      else if (!$('apply-btn').hidden && !$('apply-btn').disabled) askApply();
    }
  });
}

function scheduleBoot() {
  if (state.booted) return;
  if (window.pywebview?.api || /^https?:$/.test(window.location.protocol)) {
    boot();
    return;
  }
  window.addEventListener('pywebviewready', boot, { once: true });
  window.setTimeout(() => {
    if (!state.booted && window.pywebview?.api) boot();
  }, 1200);
}

// A small shared contract for the separately loaded import surface (also used
// by the offline preview and DOM tests, which evaluate scripts independently).
window.organizerLocalBridge = {
  request: api, create: make, log, toast,
  isBusy: () => Object.values(state.busy).some(Boolean),
  setBusy(value) { state.busy.local = value; updateActionState(); },
};
document.addEventListener('DOMContentLoaded', scheduleBoot);
window.addEventListener('pywebviewready', scheduleBoot, { once: true });
