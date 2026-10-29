/* Local organization is saved separately from Steam collections. */
(() => {
  const { request, create: make, toast, log, isBusy, setBusy } = window.organizerLocalBridge;
  const $ = id => document.getElementById(`library-manager-${id}`);
  const dialog = $('dialog');
  const state = { data: null, folder: '*', selected: new Set(), busy: false, editor: null, drag: [], limit: 100 };
  const error = message => { $('error').textContent = message || ''; $('error').hidden = !message; };
  const identity = () => ({ account: state.data?.account, revision: state.data?.revision });
  const rows = () => {
    const query = $('search').value.trim().toLocaleLowerCase(), tag = $('filter-tag').value;
    let items = (state.data?.games || []).filter(game => (state.folder === '*' || game.folder === state.folder) &&
      (!tag || game.tags.includes(tag)) && `${game.name} ${game.tags.join(' ')}`.toLocaleLowerCase().includes(query));
    if ($('sort').value === 'name') items = [...items].sort((a, b) => a.name.localeCompare(b.name, 'zh-CN', { numeric: true }));
    if ($('sort').value === 'hours') items = [...items].sort((a, b) => (b.minutes ?? b.steam_minutes ?? -1) - (a.minutes ?? a.steam_minutes ?? -1));
    return items;
  };
  function button(text, action, label = text) {
    const node = make('button', 'btn btn-quiet', text); node.type = 'button'; node.setAttribute('aria-label', label);
    node.addEventListener('click', action); return node;
  }
  function controls() {
    dialog.querySelectorAll('button,input,select').forEach(node => { node.disabled = state.busy; });
    $('open').disabled = isBusy();
    dialog.setAttribute('aria-busy', String(state.busy));
    const count = state.selected.size, loaded = !!state.data;
    $('selected').textContent = `已选 ${count} 项`;
    for (const id of ['target', 'move', 'add-tag', 'remove-tag', 'bottom', 'clear']) $(id).hidden = !count;
    for (const id of ['move', 'add-tag', 'remove-tag', 'bottom']) $(id).disabled = state.busy || !count;
    $('undo').disabled = state.busy || !state.data?.can_undo;
    for (const id of ['new-folder', 'sync', 'select', 'clear']) $(id).disabled = state.busy || !loaded;
    $('rename').disabled = $('delete').disabled = state.busy || !state.folder || state.folder === '*';
    dialog.querySelectorAll('[data-reorder]').forEach(node => { node.disabled = state.busy || $('sort').value !== 'manual'; });
  }
  async function run(action, payload = {}, update = true) {
    if (state.busy) return;
    error(''); state.busy = true; setBusy(true); controls();
    $('status').textContent = action === 'load' ? '正在读取游戏…' : '正在保存…';
    try {
      const result = await request(`/api/library/${action}`, { ...identity(), ...payload });
      if (update) {
        state.data = result;
        if (state.folder !== '*' && state.folder && !result.folders.some(f => f.id === state.folder)) state.folder = '';
        const available = new Set(result.games.map(g => g.id));
        state.selected = new Set([...state.selected].filter(id => available.has(id)));
        render();
      }
      $('status').textContent = `${state.data?.games.length ?? 0} 个游戏 · 修改自动保存在本机`;
      return result;
    } catch (e) { error(e.message); $('status').textContent = '操作未完成'; return null; }
    finally { state.busy = false; setBusy(false); controls(); }
  }
  const edit = payload => run('edit', payload);
  function changeFolder(id) {
    if (state.busy) return;
    state.folder = id; state.selected.clear(); state.limit = 100;
    $('search').value = ''; $('filter-tag').value = ''; closeEditor(); render();
  }
  function folderButton(id, name, count) {
    const node = button('', () => changeFolder(id), `${name}，${count} 个游戏`);
    node.className = 'manager-folder'; node.dataset.folder = id;
    node.setAttribute('aria-pressed', String(state.folder === id));
    node.append(make('span', 'manager-folder-icon', id === '*' ? '▦' : '▱'), make('span', 'manager-folder-name', name), make('span', 'manager-folder-count', String(count)));
    return node;
  }
  function render() {
    if (!state.data) return;
    const { games, folders } = state.data;
    $('folders').replaceChildren(folderButton('*', '全部游戏', games.length), folderButton('', '未分类', games.filter(g => !g.folder).length),
      ...folders.map(folder => folderButton(folder.id, folder.name, games.filter(g => g.folder === folder.id).length)));
    const oldTarget = $('target').value;
    $('target').replaceChildren(new Option('未分类', ''), ...folders.map(f => new Option(f.name, f.id)));
    if ([...$('target').options].some(o => o.value === oldTarget)) $('target').value = oldTarget;
    const tag = $('filter-tag').value;
    const tags = [...new Set(games.flatMap(g => g.tags))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
    $('filter-tag').replaceChildren(new Option('全部标签', ''), ...tags.map(t => new Option(t, t)));
    if (tags.includes(tag)) $('filter-tag').value = tag;
    $('folder-title').textContent = state.folder === '*' ? '全部游戏' : folders.find(f => f.id === state.folder)?.name || '未分类';
    const list = rows(); $('count').textContent = `${list.length} 项`;
    $('list').replaceChildren(...list.slice(0, state.limit).map(gameRow));
    $('empty').hidden = !!list.length;
    $('more').hidden = list.length <= state.limit;
    $('more').textContent = `显示更多（${Math.min(state.limit, list.length)} / ${list.length}）`;
    controls();
  }
  function gameRow(game, index) {
    const row = make('div', `manager-row${state.selected.has(game.id) ? ' is-selected' : ''}`); row.dataset.id = game.id;
    const checkLabel = make('label', 'manager-check'), check = make('input'); check.type = 'checkbox';
    check.checked = state.selected.has(game.id); check.setAttribute('aria-label', `选择 ${game.name}`);
    check.addEventListener('change', () => { check.checked ? state.selected.add(game.id) : state.selected.delete(game.id); row.classList.toggle('is-selected', check.checked); controls(); });
    checkLabel.append(check);
    const handle = button('⠿', () => {}, `拖动排序 ${game.name}`); handle.className = 'manager-grip'; handle.draggable = false;
    handle.title = '拖到其他游戏前调整顺序，拖到文件夹可移动游戏';
    // Pointer capture works in both WebView2 and touch browsers; no native
    // HTML drag session is needed to move a game inside this application.
    let start = null, dropTarget = null;
    const clearDrag = () => {
      start = null; dropTarget = null; state.drag = [];
      dialog.classList.remove('is-dragging'); row.classList.remove('is-drag-source');
      dialog.querySelectorAll('.is-drop').forEach(x => x.classList.remove('is-drop'));
    };
    handle.addEventListener('pointerdown', event => {
      if (state.busy || event.button !== 0) return;
      start = { x: event.clientX, y: event.clientY }; handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener('pointermove', event => {
      if (!start) return;
      if (!state.drag.length && Math.hypot(event.clientX - start.x, event.clientY - start.y) < 6) return;
      state.drag = state.selected.has(game.id) ? [...state.selected] : [game.id];
      dialog.classList.add('is-dragging'); row.classList.add('is-drag-source');
      dialog.querySelectorAll('.is-drop').forEach(x => x.classList.remove('is-drop'));
      const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('.manager-folder,.manager-row');
      dropTarget = target && ((target.dataset.folder != null && target.dataset.folder !== '*') ||
        (target.dataset.id && !state.drag.includes(target.dataset.id) && $('sort').value === 'manual')) ? target : null;
      dropTarget?.classList.add('is-drop');
      const scroller = dialog.querySelector('.manager-scroll'), rect = scroller.getBoundingClientRect();
      if (event.clientX > rect.left && event.clientY > rect.top && event.clientY < rect.bottom) {
        if (event.clientY > rect.bottom - 40) scroller.scrollTop += 16;
        if (event.clientY < rect.top + 40) scroller.scrollTop -= 16;
      }
    });
    handle.addEventListener('pointerup', async event => {
      const ids = [...state.drag], target = dropTarget; clearDrag();
      if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
      if (!ids.length || !target || state.busy) return;
      if (target.dataset.folder != null) {
        if (await edit({ action: 'move', ids, folder: target.dataset.folder })) { state.selected.clear(); render(); }
      } else await edit({ action: 'reorder', ids, before: target.dataset.id });
    });
    handle.addEventListener('pointercancel', clearDrag);
    handle.addEventListener('lostpointercapture', clearDrag);
    const text = make('div', 'manager-game'); text.append(make('strong', '', game.name));
    const meta = make('div', 'manager-game-meta');
    meta.append(make('span', '', `${game.source}${game.installed ? ' · 已安装' : ''}`));
    if (state.folder === '*' && game.folder) meta.append(make('span', '', state.data.folders.find(f => f.id === game.folder)?.name || ''));
    game.tags.forEach(tag => meta.append(make('span', 'manager-tag', tag)));
    text.append(meta);
    const minutes = game.minutes ?? game.steam_minutes;
    const hours = button(minutes == null ? '填写时长' : `${(minutes / 60).toLocaleString('zh-CN', { maximumFractionDigits: 1 })} 小时`, () => openEditor('playtime', game), `修改 ${game.name} 的自定义时长`);
    hours.className = 'manager-hours';
    hours.append(make('small', '', game.minutes != null ? '自定义' : game.steam_minutes != null ? 'Steam 记录' : '自定义记录'));
    const arrows = make('div', 'manager-order');
    const up = button('↑', () => reorderOne(game.id, -1), `上移 ${game.name}`), down = button('↓', () => reorderOne(game.id, 1), `下移 ${game.name}`);
    up.dataset.reorder = down.dataset.reorder = 'true'; arrows.append(up, down);
    row.append(checkLabel, handle, make('span', 'manager-index', String(index + 1).padStart(2, '0')), text, hours, arrows);
    return row;
  }
  async function reorderOne(id, delta) {
    if (state.busy || $('sort').value !== 'manual') return;
    const list = rows(), index = list.findIndex(g => g.id === id);
    if (index + delta < 0 || index + delta >= list.length) return;
    const before = delta < 0 ? list[index - 1].id : list[index + 2]?.id ?? null;
    if (await edit({ action: 'reorder', ids: [id], before })) {
      const row = [...$('list').children].find(r => r.dataset.id === id);
      row?.querySelector(delta < 0 ? '.manager-order button' : '.manager-order button:last-child')?.focus();
    }
  }
  function closeEditor() { state.editor = null; $('editor').hidden = true; }
  function openEditor(action, game) {
    if (state.busy) return;
    error(''); state.editor = { action, game, ids: [...state.selected], folder: state.folder };
    const labels = { create_folder: '新建文件夹', rename_folder: '重命名文件夹', delete_folder: '删除文件夹', add_tag: '添加标签', remove_tag: '移除标签', playtime: '自定义时长' };
    $('editor-title').textContent = labels[action];
    $('editor-note').textContent = action === 'playtime' ? `${game.name} · 仅保存在本软件，不修改 Steam 时长。` : action === 'delete_folder' ? '游戏会移到“未分类”，不会删除游戏文件。' : action.includes('tag') ? `已选择 ${state.selected.size} 个游戏` : '';
    $('field-label').textContent = action === 'playtime' ? '小时' : action.includes('tag') ? '标签名称' : '文件夹名称';
    $('field').type = action === 'playtime' ? 'number' : 'text';
    $('field').min = '0'; $('field').max = '1000000'; $('field').step = '0.1'; $('field').maxLength = 60;
    $('field').value = action === 'rename_folder' ? state.data.folders.find(f => f.id === state.folder).name : action === 'playtime' ? ((game.minutes ?? game.steam_minutes) == null ? '' : ((game.minutes ?? game.steam_minutes) / 60).toFixed(1)) : '';
    $('field-wrap').hidden = action === 'delete_folder'; $('reset-time').hidden = action !== 'playtime';
    $('sync-list').hidden = true; $('editor-save').textContent = action === 'delete_folder' ? '删除文件夹' : '保存';
    $('editor').hidden = false;
    (action === 'delete_folder' ? $('editor-save') : $('field')).focus();
  }
  async function saveEditor(reset = false) {
    const editor = state.editor; if (!editor || state.busy) return;
    let result;
    if (editor.action === 'publish') {
      result = await run('publish', { plan_id: editor.plan }, false);
      if (result) { toast(`已同步 ${result.collections} 个分类`); log(`手动分类已写入；备份：${result.backup}`, 'good'); }
    } else {
      const value = $('field').value.trim();
      if (editor.action === 'playtime' && !reset && value === '') { error('请输入小时数，或清除自定义时长'); return; }
      result = await edit({ action: editor.action, folder: editor.folder, ids: editor.game ? [editor.game.id] : editor.ids, name: value, tag: value, hours: reset ? null : Number(value) });
    }
    if (result) { closeEditor(); $('search').focus(); }
  }
  async function open({ query = '' } = {}) {
    if (isBusy()) return;
    state.selected.clear(); closeEditor(); dialog.showModal(); document.body.classList.add('modal-open');
    state.folder = '*'; $('search').value = query; $('filter-tag').value = '';
    await run('load');
  }
  $('open').addEventListener('click', () => open());
  window.organizerLibrary = { open };
  function close() { if (!state.busy) { dialog.close(); document.body.classList.remove('modal-open'); $('open').focus(); } }
  $('close').addEventListener('click', close);
  dialog.addEventListener('cancel', event => { event.preventDefault(); if (state.busy) return; if (state.editor) { closeEditor(); $('search').focus(); } else close(); });
  $('refresh').addEventListener('click', () => { state.selected.clear(); closeEditor(); run('load'); });
  $('import').addEventListener('click', () => { close(); document.getElementById('local-games-open').click(); });
  $('search').addEventListener('input', () => { state.selected.clear(); state.limit = 100; render(); });
  for (const id of ['sort', 'filter-tag']) $(id).addEventListener('change', () => { state.selected.clear(); state.limit = 100; render(); });
  $('select').addEventListener('click', () => { state.selected = new Set(rows().map(g => g.id)); render(); });
  $('clear').addEventListener('click', () => { state.selected.clear(); render(); });
  $('more').addEventListener('click', () => { state.limit += 100; render(); });
  $('move').addEventListener('click', async () => { if (await edit({ action: 'move', ids: [...state.selected], folder: $('target').value })) { state.selected.clear(); render(); } });
  $('bottom').addEventListener('click', async () => {
    if (await edit({ action: 'reorder', ids: [...state.selected], before: null })) {
      $('sort').value = 'manual'; render();
    }
  });
  $('undo').addEventListener('click', async () => { closeEditor(); if (await edit({ action: 'undo' })) { state.selected.clear(); render(); } });
  for (const [id, action] of [['new-folder', 'create_folder'], ['rename', 'rename_folder'], ['delete', 'delete_folder'], ['add-tag', 'add_tag'], ['remove-tag', 'remove_tag']]) $(id).addEventListener('click', () => openEditor(action));
  $('editor-cancel').addEventListener('click', () => { closeEditor(); $('search').focus(); });
  $('editor-save').addEventListener('click', () => saveEditor());
  $('reset-time').addEventListener('click', () => saveEditor(true));
  $('field').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); saveEditor(); } });
  $('sync').addEventListener('click', async () => {
    closeEditor(); const result = await run('preview', {}, false); if (!result) return;
    state.editor = { action: 'publish', plan: result.plan_id };
    $('editor-title').textContent = '同步到 Steam';
    $('editor-note').textContent = `将替换从“游戏管理”同步过的 ${result.replaced} 个分类，其他分类保留。手动排序和自定义时长仅在本软件生效。请先完全退出 Steam。`;
    $('field-wrap').hidden = $('reset-time').hidden = true;
    $('sync-list').replaceChildren(...result.groups.map(g => make('li', '', `${g.name} · ${g.appids.length} 个游戏`)));
    if (!result.groups.length) $('sync-list').append(make('li', '', '将清除从“游戏管理”同步过的分类'));
    $('sync-list').hidden = false; $('editor-save').textContent = '备份并同步'; $('editor').hidden = false; $('editor-save').focus();
  });
  document.addEventListener('organizer-actions-updated', () => { $('open').disabled = isBusy(); });
})();
