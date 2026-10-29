/* Local-only discovery. All writes require a reviewed backend plan. */
(() => {
  const { request: api, create: make, log, toast, isBusy, setBusy } = window.organizerLocalBridge;
  const el = id => document.getElementById(`local-games-${id}`);
  const dialog = el('dialog');
  const local = { roots: [], candidates: [], selected: new Set(), names: {}, expanded: new Set(), plan: null, busy: false, scanning: false, confirming: null };
  const error = message => { el('error').textContent = message || ''; el('error').hidden = !message; };
  const visible = () => local.candidates.filter(item => [item.name, item.exe, ...(item.alternatives || []).map(x => x.exe)].join(' ').toLocaleLowerCase().includes(el('search').value.trim().toLocaleLowerCase()));

  function controls() {
    el('selection').textContent = local.plan ? `已选 ${local.selected.size} / ${local.candidates.filter(x => !x.existing).length}` : '尚未扫描';
    el('import').disabled = local.busy || !local.plan || !local.selected.size || !!local.confirming;
    el('import').hidden = !!local.confirming;
    el('undo').hidden = !!local.confirming;
    el('import').textContent = local.selected.size ? `导入 ${local.selected.size} 个游戏` : '导入所选';
    for (const id of ['scan','auto','browse','add','path','undo','close','select','clear','back','category','confirm-action']) el(id).disabled = local.busy;
    el('cancel').hidden = !local.scanning;
    el('scan').hidden = local.scanning;
    el('progress').hidden = !local.scanning;
    el('list').setAttribute('aria-busy', String(local.scanning));
    dialog.querySelectorAll('.local-game-pick input, .local-game-details input, .local-game-details select, #local-games-roots button').forEach(input => { input.disabled = local.busy || input.dataset.existing === 'true'; });
    el('open').disabled = isBusy();
  }
  function busy(value, scanning = false) {
    local.busy = value;
    local.scanning = value && scanning;
    setBusy(value);
    controls();
  }
  function renderRoots() {
    el('roots').replaceChildren();
    local.roots.forEach(root => {
      const li = make('li'), remove = make('button', 'btn btn-quiet', '移除');
      remove.type = 'button'; remove.setAttribute('aria-label', `移除目录 ${root}`);
      remove.addEventListener('click', () => { local.roots = local.roots.filter(x => x !== root); renderRoots(); });
      li.append(make('span', '', root), remove); el('roots').append(li);
    });
  }
  function addRoot(path) {
    const cleaned = (path || '').trim().replace(/^"|"$/g, '');
    if (!cleaned) return;
    if (local.roots.length >= 12) { error('一次最多添加 12 个文件夹'); return; }
    if (!local.roots.some(x => x.toLowerCase() === cleaned.toLowerCase())) local.roots.push(cleaned);
    el('path').value = ''; renderRoots(); error('');
  }
  function renderList() {
    el('list').replaceChildren();
    const items = visible();
    el('no-match').hidden = items.length > 0;
    for (const item of items) {
      const row = make('article', `local-game-row${item.existing ? ' is-existing' : ''}`);
      const groupId = item.group_id || item.id;
      row.dataset.groupId = groupId;
      const pick = make('label', 'local-game-pick'), check = make('input');
      check.type = 'checkbox'; check.checked = local.selected.has(item.id); check.disabled = item.existing || local.busy;
      check.dataset.existing = String(item.existing); check.setAttribute('aria-label', `选择 ${item.name}`);
      check.addEventListener('change', () => { check.checked ? local.selected.add(item.id) : local.selected.delete(item.id); controls(); });
      pick.append(check);
      const content = make('div'), heading = make('div', 'local-game-heading');
      heading.append(make('span', 'local-game-name', local.names[item.id] || item.name), make('span', `local-game-badge ${item.confidence}`, item.existing ? '已在 Steam' : item.confidence === 'recognized' ? '已识别' : '待确认'));
      const details = make('details', 'local-game-details'), name = make('input');
      details.open = local.expanded.has(groupId);
      details.addEventListener('toggle', () => { details.open ? local.expanded.add(groupId) : local.expanded.delete(groupId); });
      name.value = local.names[item.id] ?? item.name; name.maxLength = 160; name.setAttribute('aria-label', `${item.name} 的显示名称`); name.disabled = item.existing;
      name.dataset.existing = String(item.existing);
      name.addEventListener('input', () => { local.names[item.id] = name.value; heading.querySelector('.local-game-name').textContent = name.value || item.name; });
      details.append(make('summary', '', '启动信息'), make('p', '', `${item.source} · ${item.reason}`), make('p', '', `工作目录：${item.start_dir}`), make('p', '', `启动参数：${item.args || '无'}`), name);
      if (item.alternatives?.length > 1) {
        const label = make('label', 'local-game-variants', `启动方式（${item.alternatives.length}）`), select = make('select');
        select.setAttribute('aria-label', `${item.name} 的启动方式`);
        select.dataset.existing = String(item.existing);
        item.alternatives.forEach(variant => {
          const option = make('option', '', `${variant.source} · ${variant.exe}${variant.args ? ` ${variant.args}` : ''}`);
          option.value = variant.id; option.selected = variant.id === item.id; select.append(option);
        });
        select.addEventListener('change', () => {
          const choice = item.alternatives.find(x => x.id === select.value);
          if (!choice) return;
          const selected = local.selected.delete(item.id);
          if (selected) local.selected.add(choice.id);
          if (Object.hasOwn(local.names, item.id)) local.names[choice.id] = local.names[item.id];
          local.candidates[local.candidates.indexOf(item)] = { ...choice, alternatives: item.alternatives, group_id: groupId, existing: item.existing };
          local.expanded.add(groupId); renderList();
          [...el('list').querySelectorAll('article')].find(x => x.dataset.groupId === groupId)?.querySelector('select')?.focus();
        });
        label.append(select); details.append(label);
        heading.append(make('span', 'local-game-badge', `${item.alternatives.length} 种启动方式`));
      }
      content.append(heading, make('p', 'local-game-path', item.exe), details); row.append(pick, content); el('list').append(row);
    }
    controls();
  }
  function back() {
    local.confirming = null; el('confirm').hidden = true;
    el('results').hidden = !local.plan;
    dialog.querySelector('.local-games-sources').hidden = false;
    controls();
  }
  async function scan() {
    if (local.busy) return;
    if (el('path').value.trim()) addRoot(el('path').value);
    error(''); back(); local.plan = null; local.selected.clear(); local.names = {}; local.expanded.clear();
    el('results').hidden = true; el('empty').hidden = true; el('warnings').hidden = true; el('coverage').hidden = true;
    el('status').textContent = '正在查找启动程序…'; busy(true, true);
    try {
      const data = await api('/api/local-games/scan', { roots: local.roots, automatic: el('auto').checked });
      local.candidates = data.candidates || []; local.plan = data.plan_id;
      local.selected = new Set(local.candidates.filter(x => !x.existing && x.confidence === 'recognized').map(x => x.id));
      el('search').value = '';
      el('status').textContent = data.cancelled ? '扫描已停止，未修改 Steam。' : local.candidates.length ? `发现 ${local.candidates.length} 个游戏 · ${local.candidates.filter(x => x.existing).length} 个已在 Steam${data.merged ? ` · 合并 ${data.merged} 个重复入口` : ''}` : '没有找到游戏。可以添加游戏所在的文件夹，再扫描一次。';
      el('coverage').hidden = !data.locations?.length;
      el('coverage').querySelector('summary').textContent = `扫描范围 · ${data.locations?.length || 0} 个位置${data.limited || data.partial_roots ? ' · 部分目录未扫完' : ''}`;
      const incomplete = new Set(data.incomplete_locations || []);
      el('coverage').querySelector('ul').replaceChildren(...(data.locations || []).map(path => make('li', '', `${path}${incomplete.has(path) ? '（未扫完，可添加具体游戏文件夹）' : ''}`)));
      el('warnings').hidden = !data.warnings?.length;
      el('warnings').querySelector('ul').replaceChildren(...(data.warnings || []).map(message => make('li', '', message)));
      el('results').hidden = !local.candidates.length; el('empty').hidden = !!local.candidates.length;
      renderList();
    } catch (e) { error(e.message); el('status').textContent = '扫描未完成'; el('empty').hidden = false; }
    finally { busy(false); }
  }
  function confirm(action) {
    if (local.busy || (action === 'import' && (!local.plan || !local.selected.size))) return;
    error(''); local.confirming = action;
    el('confirm-title').textContent = action === 'import' ? `将 ${local.selected.size} 个游戏加入 Steam` : '撤销上次导入';
    el('confirm-copy').textContent = action === 'import' ? '保留已添加的非 Steam 游戏。导入后可从 Steam 游戏库启动。' : '恢复导入前的快捷方式。如果之后又改过快捷方式，将取消撤销，避免覆盖这些改动。';
    el('category-label').hidden = action !== 'import';
    el('artwork-label').hidden = action !== 'import';
    el('confirm-action').textContent = action === 'import' ? '备份并导入' : '确认撤销';
    el('confirm').hidden = false; el('results').hidden = true; el('empty').hidden = true;
    dialog.querySelector('.local-games-sources').hidden = true;
    controls(); el('confirm-action').focus();
  }
  async function commit() {
    if (local.busy || !local.confirming) return;
    const action = local.confirming;
    let artworkAppids = null;
    error(''); busy(true);
    el('confirm-action').textContent = action === 'import' ? '正在备份并导入…' : '正在撤销…';
    try {
      const data = await api(`/api/local-games/${action}`, action === 'import' ? { plan_id: local.plan, selected: [...local.selected], names: local.names, category: el('category').value } : {});
      local.plan = null; local.selected.clear(); local.candidates = [];
      back(); el('empty').hidden = false;
      el('status').textContent = action === 'import' ? `已导入 ${data.added} 个游戏。重新启动 Steam 后查看。` : '已恢复导入前的快捷方式。';
      log(action === 'import' ? `本机游戏导入完成：${data.added} 个。备份：${data.backup}` : `本机游戏导入已撤销：${data.restored}`, 'good');
      toast(action === 'import' ? '导入完成，重启 Steam 后查看' : '导入已撤销');
      if (action === 'import' && el('artwork').checked && data.appids?.length) artworkAppids = data.appids;
    } catch (e) { error(e.message); }
    finally { busy(false); el('confirm-action').textContent = action === 'import' ? '备份并导入' : '确认撤销'; }
    if (artworkAppids && window.organizerArtwork) { dialog.close(); await window.organizerArtwork.open({ appids: artworkAppids, auto: true }); }
  }
  el('open').addEventListener('click', () => {
    if (isBusy()) return;
    dialog.showModal(); document.body.classList.add('modal-open');
    window.dispatchEvent(new CustomEvent('organizer-state-change'));
    controls(); el('scan').focus();
  });
  el('close').addEventListener('click', () => { if (!local.busy) dialog.close(); });
  dialog.addEventListener('cancel', event => { if (local.busy) event.preventDefault(); });
  dialog.addEventListener('close', () => { document.body.classList.remove('modal-open'); back(); el('open').focus(); window.dispatchEvent(new CustomEvent('organizer-state-change')); });
  el('scan').addEventListener('click', scan);
  el('cancel').addEventListener('click', async () => { try { await api('/api/local-games/cancel', {}); el('status').textContent = '正在停止扫描…'; } catch (e) { error(e.message); } });
  el('add').addEventListener('click', () => addRoot(el('path').value));
  el('path').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); addRoot(el('path').value); } });
  el('browse').addEventListener('click', async () => {
    if (!window.pywebview?.api?.choose_game_folder) { el('path').focus(); error('网页版请在输入框中填写游戏文件夹的完整路径。'); return; }
    try { addRoot(await api('/api/local-games/folder', {})); } catch (e) { error(e.message); }
  });
  el('search').addEventListener('input', renderList);
  el('select').addEventListener('click', () => { visible().filter(x => !x.existing).forEach(x => local.selected.add(x.id)); renderList(); });
  el('clear').addEventListener('click', () => { local.selected.clear(); renderList(); });
  el('import').addEventListener('click', () => confirm('import'));
  el('undo').addEventListener('click', () => confirm('undo'));
  el('back').addEventListener('click', back);
  el('confirm-action').addEventListener('click', commit);
  window.addEventListener('organizer-actions-updated', () => { el('open').disabled = isBusy(); });
})();
