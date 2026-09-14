/* 视图：群组 / 用户 / 消息记录 / 命令列表（数据表格类） */

import { api } from '../api.js';
import { icon, toast, escapeHtml, renderPagination, skeletonRows, confirmDialog, debounce } from '../ui.js';

/* ---------- 通用表格渲染 ---------- */

function tableShell(headers, bodyHtml) {
  return `<div class="table-wrap"><div class="table-scroll">
    <table class="tbl">
      <thead><tr>${headers.map((h) => `<th>${h}</th>`).join('')}</tr></thead>
      <tbody>${bodyHtml}</tbody>
    </table>
  </div><div class="pagination"></div></div>`;
}

function emptyRow(cols, text = '暂无数据') {
  return `<tr class="empty-row"><td colspan="${cols}">${text}</td></tr>`;
}

/* ============================================================
   群组列表
   ============================================================ */

const groupsState = { page: 1, limit: 20, search: '' };
let groupsReqId = 0;
let groupsLoadedOnce = false;

async function initGroups(section) {
  section.innerHTML = `
    <div class="filter-bar">
      <input class="input" id="grp-search" placeholder="搜索群号或群名…" value="${escapeHtml(groupsState.search)}" style="width:260px">
      <span class="spacer"></span>
      <span class="muted small" id="grp-count"></span>
    </div>
    <div id="grp-table"></div>`;

  const searchInput = section.querySelector('#grp-search');
  searchInput.addEventListener('input', debounce(() => {
    groupsState.search = searchInput.value.trim();
    groupsState.page = 1;
    loadGroups(section);
  }, 350));

  await loadGroups(section);
}

async function loadGroups(section) {
  const box = section.querySelector('#grp-table');
  const reqId = ++groupsReqId;
  /* 每次加载（含翻页/搜索）都先重画骨架，避免旧表格冻结无反馈 */
  box.innerHTML = tableShell(['群号', '群名称'], `<tr><td colspan="2">${skeletonRows(5, 'skeleton-row')}</td></tr>`);

  const params = new URLSearchParams({ page: groupsState.page, limit: groupsState.limit });
  if (groupsState.search) params.set('search', groupsState.search);

  let data;
  try {
    data = await api.get(`/groups?${params}`);
  } catch (e) {
    if (reqId !== groupsReqId) return;
    box.innerHTML = `<div class="notice danger">${icon('alert')}<div>加载群组列表失败：${escapeHtml(e.message)}</div></div>`;
    if (groupsLoadedOnce) toast(`加载群组列表失败：${e.message}`, 'error', 5000);
    return;
  }
  if (reqId !== groupsReqId) return; /* 已有更新的请求，丢弃过期响应 */
  groupsLoadedOnce = true;

  section.querySelector('#grp-count').textContent = `${data.total} 个群`;
  const rows = data.items.length
    ? data.items
        .map(
          (g, i) => `<tr style="animation-delay:${Math.min(i * 30, 300)}ms">
            <td class="mono">${escapeHtml(String(g.group_id))}</td>
            <td>${escapeHtml(g.group_name || '（未记录群名）')}</td>
          </tr>`
        )
        .join('')
    : emptyRow(2, '没有匹配的群');

  box.innerHTML = tableShell(['群号', '群名称'], rows);
  renderPagination(box.querySelector('.pagination'), data, (page, limit) => {
    groupsState.page = page;
    groupsState.limit = limit;
    loadGroups(section);
  });
}

/* ============================================================
   用户列表（含权限管理）
   ============================================================ */

const usersState = { page: 1, limit: 20, search: '' };
let usersReqId = 0;
let usersLoadedOnce = false;

const PERM_BADGE = {
  administrator: '<span class="badge blue perm-badge">管理员</span>',
  blacklist: '<span class="badge red perm-badge">黑名单</span>',
  root: '<span class="badge purple perm-badge">Root</span>',
};

function permCell(user) {
  if (user.is_root) return PERM_BADGE.root;
  if (user.permission_type) return PERM_BADGE[user.permission_type] || `<span class="badge gray">${escapeHtml(user.permission_type)}</span>`;
  return '<span class="badge gray">普通用户</span>';
}

function userActions(user) {
  if (user.is_root) return '<span class="muted small">root 不可变更</span>';
  const btns = [];
  if (user.permission_type === 'administrator') {
    btns.push(`<button class="btn sm ghost" data-perm="demote" data-uid="${user.user_id}">取消管理员</button>`);
  } else {
    btns.push(`<button class="btn sm ghost" data-perm="promote" data-uid="${user.user_id}">设为管理员</button>`);
  }
  if (user.permission_type === 'blacklist') {
    btns.push(`<button class="btn sm ghost" data-perm="unblacklist" data-uid="${user.user_id}">解除黑名单</button>`);
  } else {
    btns.push(`<button class="btn sm danger" data-perm="blacklist" data-uid="${user.user_id}">拉黑</button>`);
  }
  return `<div class="row-actions">${btns.join('')}</div>`;
}

async function initUsers(section) {
  section.innerHTML = `
    <div class="notice info">${icon('info')}<div>权限说明：管理员可使用管理类命令；黑名单用户的消息会被完全忽略。更改立即生效并写入数据库。</div></div>
    <div class="filter-bar">
      <input class="input" id="usr-search" placeholder="搜索 QQ 号或昵称…" value="${escapeHtml(usersState.search)}" style="width:260px">
      <span class="spacer"></span>
    </div>
    <div id="usr-table"></div>`;

  section.querySelector('#usr-search').addEventListener('input', debounce((e) => {
    usersState.search = e.target.value.trim();
    usersState.page = 1;
    loadUsers(section);
  }, 350));

  section.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-perm]');
    if (!btn) return;
    const uid = btn.dataset.uid;
    const action = btn.dataset.perm;
    const labels = {
      promote: `将 ${uid} 提升为管理员`, demote: `取消 ${uid} 的管理员权限`,
      blacklist: `将 ${uid} 加入黑名单（消息将被完全忽略）`, unblacklist: `将 ${uid} 移出黑名单`,
    };
    const ok = await confirmDialog({
      title: '权限变更',
      message: `确定要${labels[action]}吗？`,
      danger: action === 'blacklist',
      confirmText: '确认变更',
    });
    if (!ok) return;
    btn.classList.add('loading');
    try {
      const res = await api.put(`/users/${uid}/permission`, { action });
      toast(`操作成功，当前角色：${res.role}`, 'success');
      loadUsers(section);
    } catch (err) {
      toast(`操作失败：${err.message}`, 'error', 5000);
      btn.classList.remove('loading');
    }
  });

  await loadUsers(section);
}

async function loadUsers(section) {
  const box = section.querySelector('#usr-table');
  const reqId = ++usersReqId;
  box.innerHTML = tableShell(['QQ 号', '昵称', '权限', '最近活跃', '操作'], `<tr><td colspan="5">${skeletonRows(6)}</td></tr>`);

  const params = new URLSearchParams({ page: usersState.page, limit: usersState.limit });
  if (usersState.search) params.set('search', usersState.search);

  let data;
  try {
    data = await api.get(`/users?${params}`);
  } catch (e) {
    if (reqId !== usersReqId) return;
    box.innerHTML = `<div class="notice danger">${icon('alert')}<div>加载用户列表失败：${escapeHtml(e.message)}</div></div>`;
    if (usersLoadedOnce) toast(`加载用户列表失败：${e.message}`, 'error', 5000);
    return;
  }
  if (reqId !== usersReqId) return;
  usersLoadedOnce = true;

  const rows = data.items.length
    ? data.items
        .map(
          (u, i) => `<tr style="animation-delay:${Math.min(i * 30, 300)}ms">
            <td class="mono">${escapeHtml(String(u.user_id))}</td>
            <td>${escapeHtml(u.nickname || '-')}</td>
            <td>${permCell(u)}</td>
            <td class="muted">${escapeHtml(u.last_updated || '-')}</td>
            <td>${userActions(u)}</td>
          </tr>`
        )
        .join('')
    : emptyRow(5, '没有匹配的用户');

  box.innerHTML = tableShell(['QQ 号', '昵称', '权限', '最近活跃', '操作'], rows);
  renderPagination(box.querySelector('.pagination'), data, (page, limit) => {
    usersState.page = page;
    usersState.limit = limit;
    loadUsers(section);
  });
}

/* ============================================================
   消息记录
   ============================================================ */

const msgState = { page: 1, limit: 50, group: '', user: '', search: '' };
let messagesReqId = 0;
let messagesLoadedOnce = false;

async function initMessages(section) {
  section.innerHTML = `
    <div class="filter-bar">
      <input class="input mono" id="msg-group" placeholder="群号筛选" value="${escapeHtml(msgState.group)}" style="width:130px">
      <input class="input mono" id="msg-user" placeholder="用户 QQ 筛选" value="${escapeHtml(msgState.user)}" style="width:140px">
      <input class="input" id="msg-search" placeholder="搜索消息内容…" value="${escapeHtml(msgState.search)}" style="width:200px">
      <button class="btn primary sm" id="msg-apply">${icon('search')} 筛选</button>
      <button class="btn ghost sm" id="msg-reset">重置</button>
      <span class="spacer"></span>
    </div>
    <div id="msg-table"></div>`;

  const apply = () => {
    msgState.group = section.querySelector('#msg-group').value.trim();
    msgState.user = section.querySelector('#msg-user').value.trim();
    msgState.search = section.querySelector('#msg-search').value.trim();
    msgState.page = 1;
    loadMessages(section);
  };
  section.querySelector('#msg-apply').addEventListener('click', apply);
  section.querySelector('#msg-reset').addEventListener('click', () => {
    section.querySelector('#msg-group').value = '';
    section.querySelector('#msg-user').value = '';
    section.querySelector('#msg-search').value = '';
    apply();
  });
  section.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.matches('.filter-bar .input')) apply(); });

  await loadMessages(section);
}

async function loadMessages(section) {
  const box = section.querySelector('#msg-table');
  const reqId = ++messagesReqId;
  box.innerHTML = tableShell(['时间', '群号', '发送者', '内容'], `<tr><td colspan="4">${skeletonRows(7)}</td></tr>`);

  const params = new URLSearchParams({ page: msgState.page, limit: msgState.limit });
  if (msgState.group) params.set('group_id', msgState.group);
  if (msgState.user) params.set('user_id', msgState.user);
  if (msgState.search) params.set('search', msgState.search);

  let data;
  try {
    data = await api.get(`/messages?${params}`);
  } catch (e) {
    if (reqId !== messagesReqId) return;
    box.innerHTML = `<div class="notice danger">${icon('alert')}<div>加载消息记录失败：${escapeHtml(e.message)}</div></div>`;
    if (messagesLoadedOnce) toast(`加载消息记录失败：${e.message}`, 'error', 5000);
    return;
  }
  if (reqId !== messagesReqId) return;
  messagesLoadedOnce = true;

  const rows = data.items.length
    ? data.items
        .map(
          (m) => `<tr>
            <td class="muted" style="white-space:nowrap">${escapeHtml(m.time_str || '-')}</td>
            <td>${m.group_id ? escapeHtml(String(m.group_id)) : '<span class="badge gray">私聊</span>'}</td>
            <td>${escapeHtml(m.nickname || '')} <span class="muted small mono">${escapeHtml(String(m.user_id))}</span></td>
            <td class="msg-cell">${escapeHtml(m.message_content)}</td>
          </tr>`
        )
        .join('')
    : emptyRow(4, '没有匹配的消息');

  box.innerHTML = tableShell(['时间', '群号', '发送者', '内容'], rows);
  renderPagination(box.querySelector('.pagination'), data, (page, limit) => {
    msgState.page = page;
    msgState.limit = limit;
    loadMessages(section);
  });
}

/* ============================================================
   命令列表
   ============================================================ */

const commandsState = { search: '', level: 'all' };

/* 权限等级 = 命令的最低可执行用户等级（黑名单0 < 普通1 < 管理员2 < Root3） */
const LEVEL_LABEL = {
  3: ['purple', 'Root'],
  2: ['blue', '管理员'],
  1: ['green', '所有人'],
  0: ['teal', '任何人（含黑名单）'],
};

const LEVEL_FILTERS = [
  ['all', '全部'],
  [0, '任何人'],
  [1, '所有人'],
  [2, '管理员'],
  [3, 'Root'],
];

function fmtShort(s) {
  return s.startsWith('-') ? s : `-${s}`;
}

function fmtLong(s) {
  return s.startsWith('--') ? s : `--${s}`;
}

/* 参数的语法形式：位置参数用 metavar，选项/标志用 -s / --long 形式 */
function paramSyntax(p) {
  if (p.type === 'positional') {
    let name = p.metavar || p.name;
    if (p.multiple) name += '...';
    return name;
  }
  const parts = [];
  if (p.short_option) parts.push(fmtShort(p.short_option));
  if (p.long_option) parts.push(fmtLong(p.long_option));
  let s = parts.join(' / ') || p.name;
  if (p.type === 'option') {
    const mv = p.metavar || p.name.toUpperCase();
    s += ` ${p.multiple ? `${mv}...` : mv}`;
  }
  return s;
}

function paramBadges(p) {
  if (p.type === 'flag') return ''; // 标志天然是可选布尔，无需必填/类型标注
  const badges = [`<span class="badge ${p.required ? 'red' : 'gray'}">${p.required ? '必填' : '可选'}</span>`];
  if (p.data_type) badges.push(`<span class="badge gray param-type">${escapeHtml(p.data_type)}</span>`);
  if (p.multiple) badges.push('<span class="badge orange">可多值</span>');
  return badges.join('');
}

function paramRow(p) {
  const def = p.type !== 'flag' && p.default !== null && p.default !== undefined && p.default !== ''
    ? `<span class="cmd-default">默认: ${escapeHtml(p.default)}</span>`
    : '';
  const choices = p.choices?.length
    ? `<span class="cmd-choices">${p.choices.map((c) => `<span class="badge green">${escapeHtml(c)}</span>`).join('')}</span>`
    : '';
  return `<div class="cmd-param">
    <code class="cmd-opt">${escapeHtml(paramSyntax(p))}</code>
    <span class="cmd-param-meta">${paramBadges(p)}${def}</span>
    <span class="cmd-param-desc">${escapeHtml(p.description || '')}${choices}</span>
  </div>`;
}

function cmdCard(cmd, i) {
  const [lvCls, lvText] = LEVEL_LABEL[cmd.authority_level] || ['gray', 'Lv' + cmd.authority_level];
  const cooldown = cmd.cooldown > 0 ? `<span class="badge orange">${cmd.cooldown}s 冷却</span>` : '';
  const params = cmd.params || [];
  const groups = [
    ['positional', '位置参数'],
    ['option', '选项'],
    ['flag', '标志'],
  ]
    .map(([t, label]) => {
      const rows = params.filter((p) => p.type === t);
      return rows.length ? `<div class="cmd-sec">${label}</div>${rows.map(paramRow).join('')}` : '';
    })
    .join('');
  const examples = cmd.examples?.length
    ? `<div class="cmd-sec">示例</div>${cmd.examples.map((ex, n) => `<div class="cmd-ex"><span class="cmd-ex-n">${n + 1}</span>${escapeHtml(ex)}</div>`).join('')}`
    : '';
  return `<div class="card cmd-card" style="animation-delay:${Math.min(i * 40, 500)}ms">
    <h4><span class="cmd-name">/${escapeHtml(cmd.name)}</span>${cooldown}
      <span class="badge ${lvCls}" style="margin-left:auto">${lvText}</span></h4>
    <p>${escapeHtml(cmd.description || '')}</p>
    <p class="usage">${escapeHtml(cmd.usage || '')}</p>
    ${cmd.aliases?.length ? `<p class="small"><b>别名:</b> ${cmd.aliases.map((a) => `<span class="badge gray">${escapeHtml(a)}</span>`).join(' ')}</p>` : ''}
    ${groups ? `<div class="cmd-sec">参数</div>${groups}` : ''}
    ${examples}
  </div>`;
}

async function initCommands(section) {
  section.innerHTML = `<div class="cmd-grid">${Array.from({ length: 6 }, () => '<div class="skeleton" style="height:150px;border-radius:18px"></div>').join('')}</div>`;

  let data;
  try {
    data = await api.get('/commands');
  } catch (e) {
    section.innerHTML = `<div class="notice danger">${icon('alert')}<div>命令系统不可用：${escapeHtml(e.message)}</div></div>`;
    return;
  }

  if (!data.length) {
    section.innerHTML = '<div class="card"><p class="muted">没有注册任何命令。</p></div>';
    return;
  }

  section.innerHTML = `
    <div class="filter-bar">
      <input class="input" id="cmd-search" placeholder="搜索命令名、别名或描述…" value="${escapeHtml(commandsState.search)}" style="width:260px">
      <div class="seg" id="cmd-level">
        ${LEVEL_FILTERS.map(([v, label]) => `<button data-level="${v}" class="${String(commandsState.level) === String(v) ? 'active' : ''}">${label}</button>`).join('')}
      </div>
      <span class="spacer"></span>
      <span class="muted small" id="cmd-count"></span>
    </div>
    <div class="cmd-grid" id="cmd-grid"></div>`;

  const render = () => {
    const q = commandsState.search.toLowerCase();
    const list = data.filter((c) => {
      if (commandsState.level !== 'all' && c.authority_level !== Number(commandsState.level)) return false;
      if (!q) return true;
      const hay = [c.name, ...(c.aliases || []), c.description].join(' ').toLowerCase();
      return hay.includes(q);
    });
    section.querySelector('#cmd-count').textContent = `${list.length} / ${data.length} 个命令`;
    section.querySelector('#cmd-grid').innerHTML = list.length
      ? list.map(cmdCard).join('')
      : '<div class="card"><p class="muted">没有匹配的命令。</p></div>';
  };

  const searchInput = section.querySelector('#cmd-search');
  searchInput.addEventListener('input', debounce(() => {
    commandsState.search = searchInput.value.trim();
    render();
  }, 200));

  section.querySelector('#cmd-level').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-level]');
    if (!btn) return;
    commandsState.level = btn.dataset.level;
    section.querySelectorAll('#cmd-level button').forEach((b) => b.classList.toggle('active', b === btn));
    render();
  });

  render();
}

export const groupsView = { title: '群组列表', init: initGroups };
export const usersView = { title: '用户管理', init: initUsers };
export const messagesView = { title: '消息记录', init: initMessages };
export const commandsView = { title: '命令列表', init: initCommands };
