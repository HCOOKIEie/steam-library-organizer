/* Steam Library Organizer front end. Safety and clarity come before writes. */

const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
const mobileSheetQuery = window.matchMedia('(max-width: 720px)');
const systemThemeQuery = window.matchMedia('(prefers-color-scheme: light)');
const THEME_STORAGE_KEY = 'steam-organizer-theme';
let reducedMotion = reducedMotionQuery.matches;
reducedMotionQuery.addEventListener?.('change', (event) => { reducedMotion = event.matches; });

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
  document.documentElement.style.colorScheme = nextTheme;
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.content = nextTheme === 'light' ? '#eef4fa' : '#0b1118';

  if (persist) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
      hasStoredTheme = true;
    } catch (_) {}
  }

  syncThemeControl(nextTheme);
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
  { id: 'genre', title: '游戏类型', sub: '动作 · 角色扮演 · 独立', icon: 'tag' },
  { id: 'form', title: '条目形式', sub: '游戏 · DLC · 工具', icon: 'layers' },
  { id: 'developer', title: '开发商', sub: '按开发团队分组', icon: 'build' },
  { id: 'publisher', title: '发行商', sub: '按发行公司分组', icon: 'flag' },
  { id: 'state', title: '安装状态', sub: '已安装 · 未安装', icon: 'check' },
  { id: 'recent', title: '最近游玩', sub: '按最后启动时间', icon: 'clock' },
  { id: 'playtime', title: '游玩时长', sub: '按累计小时分组', icon: 'timer' },
];

const MODE_BY_ID = Object.fromEntries(MODE_CARDS.map((mode) => [mode.id, mode]));

const DEFAULT_SCOPES = [
  {
    id: 'library',
    title: '游戏库',
    description: 'Steam 库中可确认的游戏，推荐',
  },
  {
    id: 'games',
    title: '仅游戏',
    description: '排除可识别的 DLC、工具与辅助项',
  },
  {
    id: 'all',
    title: '全部条目',
    description: '包含 DLC、工具、试玩和共享缓存',
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
  caret: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>',
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
  if (state.planFresh && state.selected.size) current = 4;
  document.querySelectorAll('.progress-step').forEach((step) => {
    const value = Number(step.dataset.step);
    step.classList.toggle('is-current', value === current);
    step.classList.toggle('is-complete', value < current);
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
  if (!state.plan.length) {
    state.planFresh = false;
    $('plan-status').textContent = state.scanReady ? '选择分类方式，然后生成安全预览。' : '扫描完成后即可生成预览。';
    updateProgress();
    updateActionState();
    return;
  }

  state.planFresh = !state.planCommitted && configsEqual(state.planConfig, currentPlanConfig());
  const panel = $('preview-panel');
  panel.classList.toggle('is-stale', !state.planFresh);
  $('stale-banner').hidden = state.planFresh;
  if (state.planFresh) {
    $('plan-status').textContent = '预览与当前设置一致，可以继续审阅。';
  } else {
    $('stale-banner').textContent = message || (state.planCommitted
      ? '这份预览已经执行过。再次写入前，请重新生成预览。'
      : '设置已改变。这份预览已过期，请重新生成后再写入。');
    $('plan-status').textContent = state.planCommitted
      ? '操作已完成；如需再次整理，请重新生成预览。'
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
    ? `其中 ${formatNumber(auxiliary)} 个辅助条目`
    : '将用于生成分类预览';
  $('stat-games').textContent = formatNumber(games);
  $('stat-games-note').textContent = counts.library !== undefined
    ? `游戏库 ${formatNumber(counts.library)}`
    : '具备可用名称的游戏';
  $('stat-unresolved').textContent = formatNumber(unresolved);
  $('stat-unresolved-note').textContent = all
    ? `占全部本地记录的 ${Math.min(100, (unresolved / all) * 100).toFixed(1)}%`
    : '名称或资料不完整';
  $('stat-installed').textContent = formatNumber(installed);

  const metadataError = state.server.appinfo_error;
  const scanWarnings = Array.isArray(state.server.scan_warnings)
    ? state.server.scan_warnings.filter(Boolean)
    : [];
  $('quality-title').textContent = metadataError
    ? 'Steam 元数据刷新失败，请重新扫描'
    : (unresolved
      ? `${formatNumber(total)} 个条目将进入当前范围，另有 ${formatNumber(unresolved)} 个资料不完整`
      : `${formatNumber(total)} 个条目将进入当前范围`);
  const sources = sourceSummary(state.server.sources || counts.sources);
  $('quality-copy').textContent = [
    metadataError
      ? `${state.server.appinfo_stale ? '当前显示的是上一次成功读取的数据。' : '当前没有可安全使用的元数据。'} 错误：${metadataError}`
      : '',
    sources ? `来源：${sources}。` : '',
    unresolved ? (state.scope === 'all' ? '“全部条目”会纳入资料不完整项。' : '资料不完整项已从当前推荐范围排除。') : '',
    auxiliary ? `另检测到 ${formatNumber(auxiliary)} 个 DLC、工具或辅助条目。` : '',
    scanWarnings.join(' '),
    '范围之间可能重叠，数字不能简单相加。',
  ].filter(Boolean).join(' ');
  $('quality-card').classList.toggle(
    'is-warning',
    unresolved > 0 || Boolean(metadataError) || scanWarnings.length > 0,
  );

  const collections = Array.isArray(state.server.collections) ? state.server.collections : [];
  const managed = collections.filter((collection) => collection.ours).length;
  const preserved = collections.length - managed;
  $('safety-copy').textContent = managed || preserved
    ? `当前有 ${formatNumber(managed)} 个自动分类；${formatNumber(preserved)} 个其他分类不会被替换。`
    : '写入前会自动备份；其他 Steam 分类不会被替换。';
}

function renderState(data) {
  if (!data?.counts) return;
  state.server = data;
  state.csrfToken = typeof data.csrf_token === 'string' && data.csrf_token
    ? data.csrf_token
    : null;
  state.scanReady = true;
  state.metadataReady = !data.appinfo_error;
  state.steamRunning = typeof data.steam_running === 'boolean' ? data.steam_running : null;

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
    $('plan-status').textContent = '元数据尚未就绪；请点击“重新扫描”重试。';
  }
  updateProgress();
  updateActionState();
}

async function refreshState(silent = false) {
  if (state.busy.scan) return;
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
    $('stats').setAttribute('aria-busy', 'false');
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
    const groupChecks = [...section.querySelectorAll('.group-checkbox')];
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
    : '暂无可显示的名称示例'));
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
    groups.forEach((group) => {
      const id = String(group.id);
      if (checkbox.checked) state.selected.add(id); else state.selected.delete(id);
    });
    list.querySelectorAll('.group').forEach((row) => row.classList.toggle('is-on', checkbox.checked));
    list.querySelectorAll('.group-checkbox').forEach((input) => { input.checked = checkbox.checked; });
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
  $('preview-empty').hidden = groups.length > 0;

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
  $('preview-scroll').scrollTop = 0;
}

async function makePlan() {
  if (!state.scanReady || !state.modes.length || state.busy.plan) return;
  const config = currentPlanConfig();
  state.busy.plan = true;
  $('plan-status').textContent = '正在根据当前范围生成预览…';
  updateActionState();
  try {
    const data = await api('/api/plan', config);
    if (!Array.isArray(data.groups)) throw new Error('预览数据格式不完整');
    state.planId = data.plan_id || null;
    state.planConfig = config;
    state.planCommitted = false;
    state.planFresh = configsEqual(config, currentPlanConfig());
    state.planSummary = normalizeSummary(data.summary, data.groups);
    renderGroups(data.groups);
    syncPlanFreshness();
    $('result-panel').hidden = true;
    log(`预览已生成：${formatNumber(data.groups.length)} 个分类，${formatNumber(state.planSummary.unique_apps)} 个唯一条目，${formatNumber(state.planSummary.memberships)} 次归属`, 'good');
    $('preview-search').focus({ preventScroll: true });
  } catch (error) {
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
    [$('page-header'), $('workspace'), $('actionbar')].forEach((element) => { element.inert = true; });

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
    [$('page-header'), $('workspace'), $('actionbar')].forEach((element) => { element.inert = false; });
    if (this.lastFocus instanceof HTMLElement) this.lastFocus.focus();
  },
};

function confirmBody(intro, summary) {
  const fragment = document.createDocumentFragment();
  fragment.appendChild(make('p', '', intro));
  if (summary) {
    const metrics = make('div', 'confirm-metrics');
    [
      [summary.groups, '收藏夹'],
      [summary.uniqueApps, '唯一条目'],
      [summary.memberships, '总归属'],
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
  if (!state.planFresh || !summary.groups || state.steamRunning !== false) return;
  sheet.open({
    kicker: '最后确认',
    title: '备份并写入 Steam',
    body: confirmBody('工具会先创建备份，再替换由本工具管理的旧自动分类。你自己的其他分类会保留。', summary),
    note: `需要 Steam 完全退出。将替换 ${formatNumber(state.planSummary.existing_managed)} 个旧自动分类，并保留 ${formatNumber(state.planSummary.manual_preserved)} 个其他分类。`,
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
        showResult('写入完成', '重新启动 Steam 后即可在游戏库左侧查看新分类。本次写入仍可通过备份恢复。', data.backup || '');
        state.planCommitted = true;
        state.planFresh = false;
        syncPlanFreshness('这份预览已成功写入。如需再次整理，请重新生成预览。');
        toast('写入完成，重启 Steam 后查看分类');
        sheet.setBusy(false);
        sheet.close();
      } catch (error) {
        log(`写入失败：${error.message}`, 'error');
        sheet.setError(`写入失败：${error.message}`);
        toast('写入失败，未关闭确认窗口', true);
        sheet.setBusy(false);
      } finally {
        state.busy.apply = false;
        updateActionState();
      }
    },
  });
}

function askRestore() {
  if (!state.scanReady || state.steamRunning !== false || state.busy.restore) return;
  sheet.open({
    kicker: '恢复保护',
    title: '恢复最近一次备份？',
    body: confirmBody('这会用最近一次备份替换当前的 Steam 收藏夹文件。恢复成功后，需要重新启动 Steam 查看结果。'),
    note: 'Steam 必须完全退出。恢复前还会为当前状态创建一份安全备份，便于撤销这次恢复。',
    confirmLabel: '创建安全备份并恢复',
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
        showResult('备份已恢复', '当前收藏夹已替换为最近备份。重新启动 Steam 后查看结果。', safetyBackup ? `恢复前安全备份：${safetyBackup}` : (data.restored || ''));
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
        toast('恢复失败，当前窗口会保留错误详情', true);
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
  if (state.busy.root) return;
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
    state.selected.clear();
    $('groups').replaceChildren();
    $('preview-empty').hidden = false;
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
    row.dataset.filtered = String(Boolean(query && !row.dataset.search.includes(query)));
  });
  document.querySelectorAll('.mode-section').forEach((section) => {
    const visible = [...section.querySelectorAll('.group')].some((row) => row.dataset.filtered !== 'true');
    section.hidden = !visible;
  });
}

function updateActionState() {
  const anyBusy = Object.values(state.busy).some(Boolean);
  const summary = selectedSummary();
  const planButton = $('plan-btn');
  const applyButton = $('apply-btn');
  planButton.disabled = state.busy.plan || state.busy.apply || state.busy.restore || !state.scanReady || !state.metadataReady || state.modes.length === 0;
  planButton.textContent = state.busy.plan ? '正在生成预览…' : (state.plan.length ? '重新生成预览' : '生成分类预览');

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
    $('action-title').textContent = '正在扫描本机 Steam';
    $('action-hint').textContent = '正在读取本地配置、库缓存和安装记录';
  } else if (!state.scanReady) {
    $('action-title').textContent = '尚未连接 Steam';
    $('action-hint').textContent = '请重新扫描，或从右上角选择 Steam 安装目录';
  } else if (state.busy.plan) {
    $('action-title').textContent = '正在生成安全预览';
    $('action-hint').textContent = '正在按所选规则计算分类，不会改动 Steam';
  } else if (!state.plan.length) {
    $('action-title').textContent = '数据已就绪';
    $('action-hint').textContent = state.modes.length ? '检查左侧规则，然后生成分类预览' : '请至少选择一种分类方式';
  } else if (!state.planFresh) {
    $('action-title').textContent = '预览需要更新';
    $('action-hint').textContent = '规则或数据已经变化，请重新生成预览';
  } else if (state.steamRunning === true) {
    $('action-title').textContent = '预览已就绪 · 当前仅可预览';
    $('action-hint').textContent = '完全退出 Steam 后即可备份并写入，当前可以继续检查分类';
  } else if (applyBlock) {
    $('action-title').textContent = '预览暂不可写入';
    $('action-hint').textContent = applyBlock;
  } else {
    $('action-title').textContent = '预览已就绪 · 可以安全写入';
    $('action-hint').textContent = `将创建 ${formatNumber(summary.groups)} 个分类，整理 ${formatNumber(summary.uniqueApps)} 个唯一条目，共 ${formatNumber(summary.memberships)} 次归属`;
  }

  $('restore-btn').disabled = state.busy.restore || state.busy.apply || !state.scanReady || state.steamRunning !== false;
  $('restore-btn').title = state.steamRunning === true
    ? '请先完全退出 Steam'
    : (state.steamRunning === null ? '无法确认 Steam 状态，请重新扫描' : '');
  $('reveal-btn').disabled = state.busy.reveal || !state.scanReady;
  $('choose-root-btn').disabled = state.busy.root || state.busy.apply || state.busy.restore;
  $('refresh-btn').disabled = state.busy.scan || state.busy.apply || state.busy.restore || state.busy.root;
}

/* Boot ------------------------------------------------------------------ */
function boot() {
  if (state.booted) return;
  state.booted = true;
  const storedTheme = readStoredTheme();
  const initialTheme = storedTheme || (systemThemeQuery.matches ? 'light' : 'dark');
  applyTheme(initialTheme);
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
  $('plan-btn').addEventListener('click', makePlan);
  $('apply-btn').addEventListener('click', askApply);
  $('restore-btn').addEventListener('click', askRestore);
  $('reveal-btn').addEventListener('click', revealFolder);
  $('open-log-btn').addEventListener('click', openLogFile);
  $('theme-btn').addEventListener('click', toggleTheme);
  $('more-btn').addEventListener('click', (event) => {
    event.stopPropagation();
    toggleMoreMenu();
  });
  $('more-menu').addEventListener('click', (event) => event.stopPropagation());
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

  $('scopes').addEventListener('change', (event) => {
    if (!event.target.matches('input[name="scope"]')) return;
    state.scope = event.target.value;
    renderScanCounts();
    syncPlanFreshness();
  });

  $('select-all').addEventListener('click', () => {
    state.selected = new Set(state.plan.map((group) => String(group.id)));
    document.querySelectorAll('.group').forEach((row) => row.classList.add('is-on'));
    document.querySelectorAll('.group-checkbox').forEach((input) => { input.checked = true; });
    renderSelectionSummary();
  });

  $('select-none').addEventListener('click', () => {
    state.selected.clear();
    document.querySelectorAll('.group').forEach((row) => row.classList.remove('is-on'));
    document.querySelectorAll('.group-checkbox').forEach((input) => { input.checked = false; });
    renderSelectionSummary();
  });

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

document.addEventListener('DOMContentLoaded', scheduleBoot);
window.addEventListener('pywebviewready', scheduleBoot, { once: true });
