/* Deterministic title matching; all image/network/file work stays in Python. */
(() => {
  const { request: api, create: make, log, toast, isBusy, setBusy } = window.organizerLocalBridge;
  const el = id => document.getElementById(`artwork-${id}`);
  const dialog = el('dialog'), labels = { cover: '竖版封面', hero: '背景', logo: '徽标', wide: '横版封面' };
  const state = { data: null, game: null, plan: null, selected: new Set(), busy: false, batching: false, stop: false, results: new Map(), reasons: new Map() };
  const identity = () => ({ account: state.data?.account, revision: state.data?.revision });
  const request = (action, extra = {}) => api(`/api/artwork/${action}`, { ...identity(), game_id: state.game, api_key: el('key').value.trim(), ...extra });
  const error = text => { el('error').textContent = text || ''; el('error').hidden = !text; };
  function controls() {
    dialog.querySelectorAll('button,input,select').forEach(input => { input.disabled = state.busy; });
    el('stop').hidden = !state.batching;
    el('stop').disabled = state.stop;
    el('apply').disabled = state.busy || !state.plan || !state.selected.size;
    el('auto').disabled = state.busy || !state.data?.games.length;
    el('search').disabled = state.busy || !state.game;
    el('open').disabled = isBusy();
  }
  function busy(value) { state.busy = value; setBusy(value); controls(); }
  function renderGames() {
    el('games').replaceChildren();
    for (const game of state.data?.games || []) {
      const button = make('button', `artwork-game${game.id === state.game ? ' is-current' : ''}`);
      button.type = 'button'; button.setAttribute('aria-pressed', String(game.id === state.game));
      button.append(make('strong', '', game.name), make('span', '', state.results.get(game.id) || `${Object.values(game.present).filter(Boolean).length} / 4 张图片`));
      button.addEventListener('click', () => selectGame(game.id));
      el('games').append(button);
    }
    controls();
  }
  function renderImages(images, selecting = false, choices = {}, match = null, selection = {}) {
    el('images').replaceChildren(); state.selected.clear();
    const game = state.data?.games.find(x => x.id === state.game);
    for (const [kind, label] of Object.entries(labels)) {
      const data = images[kind], card = make('article', `artwork-image artwork-${kind}`), heading = make('label');
      if (selecting && data) {
        const check = make('input'); check.type = 'checkbox'; check.checked = !game?.present[kind] || el('replace').checked;
        if (check.checked) state.selected.add(kind);
        check.setAttribute('aria-label', `写入${label}`);
        check.addEventListener('change', () => { check.checked ? state.selected.add(kind) : state.selected.delete(kind); controls(); });
        heading.append(check);
      }
      heading.append(make('strong', '', label), make('span', '', game?.present[kind] ? '已设置' : '缺图'));
      const frame = make('div', 'artwork-frame');
      if (data) {
        const image = make('img'); image.alt = label; image.src = selecting ? data.preview : data;
        frame.append(image);
      } else frame.append(make('span', '', selecting ? '来源暂无此图' : '未设置'));
      card.append(heading, frame);
      if (selecting && data) card.append(make('small', '', `${data.width} × ${data.height}`));
      if (choices[kind]?.length > 1 && match) {
        const picker = make('select'); picker.setAttribute('aria-label', `选择本地${label}`);
        choices[kind].forEach((choice, index) => picker.append(new Option(`${choice.name} · ${choice.width} × ${choice.height}`, String(index))));
        picker.value = String(selection[kind] || 0);
        picker.addEventListener('change', () => preview(match, { ...selection, [kind]: Number(picker.value) }));
        card.append(picker);
      }
      el('images').append(card);
    }
    controls();
  }
  async function selectGame(id) {
    if (state.busy) return;
    state.game = id; state.plan = null; state.selected.clear();
    el('folder').value = '';
    const game = state.data.games.find(x => x.id === id);
    el('game-title').textContent = game?.name || '选择一个游戏';
    el('query').value = ''; el('query').placeholder = game?.name || '游戏名称';
    el('matches').replaceChildren(); el('match-name').textContent = ''; renderGames();
    el('status').textContent = state.reasons.get(id) || '选择图片来源，搜索对应游戏。';
    error(''); busy(true);
    try { renderImages((await request('current')).images || {}); }
    catch (e) { error(e.message); }
    finally { busy(false); }
  }
  async function load() {
    state.data = await api('/api/artwork/load', {});
    if (!state.data.games.some(x => x.id === state.game)) state.game = state.data.games[0]?.id || null;
    renderGames();
    if (!state.game) {
      el('game-title').textContent = '尚未导入本机游戏'; el('images').replaceChildren();
      el('status').textContent = '先导入游戏，再设置对应图片。';
    }
  }
  async function open({ appids, auto = false } = {}) {
    if (isBusy()) return;
    error(''); state.results.clear(); state.reasons.clear(); state.plan = null; state.data = null; state.selected.clear();
    el('folder').value = '';
    el('games').replaceChildren(); el('images').replaceChildren(); el('matches').replaceChildren();
    dialog.showModal(); document.body.classList.add('modal-open');
    window.dispatchEvent(new CustomEvent('organizer-state-change'));
    busy(true); el('status').textContent = '正在读取已导入的游戏…';
    try { await load(); el('status').textContent = state.data.games.length ? '选择游戏搜索图片，或自动补齐缺图。' : '先导入游戏，再设置对应图片。'; }
    catch (e) { error(e.message); }
    finally { busy(false); }
    if (auto && state.data?.games.length) await automatic(appids);
    else if (state.game) await selectGame(state.game);
  }
  async function preview(match, selection = {}) {
    if (state.busy) return;
    error(''); busy(true); state.plan = null; el('match-name').textContent = `正在下载：${match.name}…`;
    try {
      const result = await request('preview', { match_id: match.id, local_selection: selection });
      state.plan = result.plan_id;
      el('match-name').textContent = `${result.name} · ${{ steam: 'Steam', sgdb: 'SteamGridDB', local: '本地图片' }[result.provider]}${result.warnings?.length ? ' · 部分来源暂不可用' : ''}`;
      renderImages(result.images, true, result.local_choices, match, selection);
      el('status').textContent = '确认图片对应当前游戏，再写入。已有图片默认保留。';
    } catch (e) { error(e.message); el('match-name').textContent = ''; }
    finally { busy(false); }
  }
  async function search(event) {
    event?.preventDefault(); if (state.busy || !state.game) return;
    error(''); busy(true); state.plan = null; el('matches').replaceChildren();
    el('status').textContent = '正在搜索游戏名称…';
    try {
      const result = await request('search', { query: el('query').value, provider: el('provider').value, folder: el('folder').value });
      for (const match of result.matches) {
        const button = make('button', 'artwork-match', `${match.name}${match.exact ? ' · 名称匹配' : ''}`);
        button.type = 'button'; button.addEventListener('click', () => preview(match)); el('matches').append(button);
      }
      el('status').textContent = (result.message || (result.matches.length ? '选择对应游戏，查看图片。' : '未找到。可使用本地图片，或配置 SteamGridDB。')) + (result.limited ? ' 扫描达到上限，可选择更具体的文件夹。' : '');
    } catch (e) { error(e.message); el('status').textContent = '搜索未完成'; }
    finally { busy(false); }
  }
  async function automatic(appids) {
    if (state.busy || !state.data) return;
    const wanted = appids ? new Set(appids.map(String)) : null;
    const games = state.data.games.filter(game => !wanted || wanted.has(game.id));
    if (!games.length) return;
    state.batching = true; state.stop = false; state.plan = null; error(''); busy(true);
    let changed = 0, needsReview = 0, failed = 0;
    const failures = [];
    try {
      for (let index = 0; index < games.length && !state.stop; index++) {
        const game = games[index]; state.game = game.id;
        state.reasons.delete(game.id);
        el('status').textContent = `正在匹配 ${index + 1} / ${games.length}：${game.name}`;
        try {
          const result = await request('auto');
          if (result.status === 'complete') state.results.set(game.id, '图片已齐全');
          else if (result.status === 'matched') {
            changed += result.saved.length; state.results.set(game.id, `${result.provider === 'local' ? '本地新增' : '补齐'} ${result.saved.length} 张图片`);
          } else {
            needsReview++; state.results.set(game.id, result.label || '需要确认匹配');
            state.reasons.set(game.id, result.message || '请搜索后选择对应游戏。');
          }
        } catch (e) {
          failed++; state.results.set(game.id, '匹配未完成'); failures.push(`${game.name}：${e.message}`);
          if (/Steam 正在运行|账号或快捷方式已变化/.test(e.message)) { state.stop = true; break; }
        }
        renderGames();
      }
      await load();
      el('status').textContent = `${state.stop ? '已停止 · ' : ''}补齐 ${changed} 张图片${needsReview ? ` · ${needsReview} 个未匹配，点击游戏查看原因` : ''}${failed ? ` · ${failed} 个未完成` : ''}。`;
      if (failures.length) error(failures.slice(0, 3).join('\n'));
      if (changed) { log(`游戏图片已补齐：${changed} 张；原图备份保存在 Steam 配置目录。`, 'good'); toast('游戏图片已保存，重启 Steam 后查看'); }
    } catch (e) { error(e.message); }
    finally { state.batching = false; busy(false); }
    if (state.game) {
      // Keep batch outcome visible while loading the selected game's images.
      const message = el('status').textContent, failure = el('error').textContent;
      await selectGame(state.game); el('status').textContent = message; if (failure) error(failure);
    }
  }
  el('open').addEventListener('click', () => open());
  el('close').addEventListener('click', () => { if (!state.busy) dialog.close(); });
  dialog.addEventListener('cancel', event => { if (state.busy) event.preventDefault(); });
  dialog.addEventListener('close', () => {
    el('key').value = ''; state.plan = null; el('images').replaceChildren(); el('matches').replaceChildren();
    document.body.classList.remove('modal-open'); el('open').focus(); window.dispatchEvent(new CustomEvent('organizer-state-change'));
  });
  el('refresh').addEventListener('click', async () => { if (!state.busy) { busy(true); error(''); try { await load(); } catch (e) { error(e.message); } finally { busy(false); } if (state.game) await selectGame(state.game); } });
  el('search-form').addEventListener('submit', search);
  el('provider').addEventListener('change', () => { el('local-folder').hidden = el('provider').value !== 'local'; });
  el('browse').addEventListener('click', async () => {
    if (!window.pywebview?.api?.choose_game_folder) { el('folder').focus(); return; }
    try { const path = await window.pywebview.api.choose_game_folder(); if (path) el('folder').value = path; }
    catch (e) { error(e.message); }
  });
  el('auto').addEventListener('click', () => automatic());
  el('stop').addEventListener('click', () => { state.stop = true; controls(); el('status').textContent = '完成当前游戏后停止…'; });
  el('replace').addEventListener('change', () => {
    if (state.plan) el('status').textContent = el('replace').checked ? '已允许替换已有图片。请勾选要写入的图片。' : '已有图片会保留。';
  });
  el('apply').addEventListener('click', async () => {
    if (state.busy || !state.plan || !state.selected.size) return;
    error(''); busy(true);
    try {
      const result = await request('apply', { plan_id: state.plan, selected: [...state.selected], replace: el('replace').checked });
      state.plan = null; await load(); renderImages((await request('current')).images || {});
      el('status').textContent = `保存 ${result.saved.length} 张图片${result.skipped.length ? ` · 保留 ${result.skipped.length} 张已有图片` : ''}。重启 Steam 后查看。`;
      toast('游戏图片已保存');
    } catch (e) { error(e.message); }
    finally { busy(false); }
  });
  el('undo').addEventListener('click', async () => {
    if (state.busy || !state.data) return;
    error(''); busy(true);
    try { await request('undo'); state.plan = null; await load(); if (state.game) renderImages((await request('current')).images || {}); el('status').textContent = '已撤销上次补图，重启 Steam 后查看。'; }
    catch (e) { error(e.message); }
    finally { busy(false); }
  });
  window.addEventListener('organizer-actions-updated', () => { el('open').disabled = isBusy(); });
  window.organizerArtwork = { open };
})();
