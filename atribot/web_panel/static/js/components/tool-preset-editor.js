/* 组件：工具预设编辑器（chip 列表 / 默认+待发现双列表 / 工具勾选弹窗）
 *
 * 配置页「工具预设」区块（views/config.js）与聊天页工具弹窗（views/chat.js）共用，
 * 保证两处界面与行为完全一致（新增预设、切换 default/deferred、从列表选择）。
 *
 * DOM 契约（bindChipInteractions 与两个视图共同依赖，勿随意改名）：
 *   [data-tools-field="<key>"]                        预设模块外壳
 *   [data-tools-restrict="<key>"]                     「限制工具」开关
 *   [data-path="__tools.<key>[.default|.deferred]"]   chips 容器（data-ftype="chips"）
 *   [data-tool-pick="<path>"]                         「从列表选择」按钮
 */

import { api } from '../api.js';
import { icon, toast, escapeHtml, openModal } from '../ui.js';

/* 预设别名：未登记的预设回退显示原始 key（预设清单由 config.json 动态决定） */
const PRESET_ALIASES = {
  group_chat: '群聊',
  private_chat: '私聊',
  agency_Agent: '子代理',
  webui: 'AI 聊天页',
};

/* 适用场景过滤用的预设映射；未登记的不做过滤 */
const PRESET_SCOPES = { group_chat: 'group', private_chat: 'private', webui: 'private' };

/* 待发现机制依赖的搜索工具名：default 组必须含它，deferred 里的工具才能被发现 */
const TOOL_SEARCH_NAME = 'tool_search';

/* 需要额外说明的预设（渲染在「限制工具」描述之后） */
const PRESET_NOTES = {
  webui: '该预设供管理面板的 AI 聊天页使用：「限制工具」关闭会保存为 <code>null</code>，聊天页将没有任何可用工具。',
};

const SCOPE_BADGES = {
  group: '<span class="badge blue">群聊</span>',
  private: '<span class="badge purple">私聊</span>',
  both: '',
};

/* 预设名来自用户可编辑的 config.json，用 hasOwn 防止命中 Object 原型成员（如 constructor） */
function lookup(table, key) {
  return Object.hasOwn(table, key) ? table[key] : undefined;
}

function presetLabel(key) {
  return lookup(PRESET_ALIASES, key) || key;
}

function presetScope(key) {
  return lookup(PRESET_SCOPES, key) || null;
}

/* ---------- 变更通知钩子：视图用它在改动后刷新 dirty 状态 ---------- */

let notifyChange = () => {};

export function setPresetChangeHandler(handler) {
  notifyChange = handler || (() => {});
}

/* ---------- 取值形态判定 ---------- */

/* 工具预设取值 → UI 状态：
   null/缺省 = 不限制（全部工具）；数组 = 白名单；数组含 tool_search 或字典 = 默认+待发现 双列表 */
function toolPresetState(value) {
  if (value === null || value === undefined) return { isNull: true, isDict: false, def: [], deferred: [] };
  if (Array.isArray(value)) {
    return { isNull: false, isDict: value.includes('tool_search'), def: value, deferred: [] };
  }
  const def = Array.isArray(value.default) ? value.default : [];
  const deferred = Array.isArray(value.deferred) ? value.deferred : [];
  return { isNull: false, isDict: def.includes('tool_search') || deferred.length > 0, def, deferred };
}

/* ---------- 校验（两个视图共用同一套规则） ---------- */

/**
 * 校验单个预设的 tool_search ⇄ deferred 配对规则
 * @returns {string[]} 错误信息列表（空数组 = 合法）
 */
export function validatePresetPairing(key, value, label) {
  const errors = [];
  if (value === null || value === undefined) return errors; /* null/缺省 = 全部或无工具，不涉及 deferred */
  const def = Array.isArray(value) ? value : Array.isArray(value.default) ? value.default : [];
  const deferred = Array.isArray(value?.deferred) ? value.deferred : [];
  const name = label || `${presetLabel(key)} ${key}`;
  if (def.includes('tool_search') && deferred.length === 0) {
    errors.push(`${name}：default 中配置了 tool_search，但 deferred 为空，没有可发现的内容。请在 deferred 中至少添加一个工具，或删除 tool_search 切回白名单模式`);
  } else if (!def.includes('tool_search') && deferred.length > 0) {
    errors.push(`${name}：配置了 deferred 工具，但 default 中没有 tool_search，这些工具将永远无法被模型发现。请把 tool_search 加进 default 或清空 deferred`);
  }
  return errors;
}

/* ---------- 基础控件 ---------- */

export function renderChips(path, kind, values) {
  const chips = values
    .map((val, i) => `<span class="chip" data-i="${i}">${escapeHtml(String(val))}<button data-del="${i}" title="删除">${icon('x')}</button></span>`)
    .join('');
  return `<div class="chips" data-path="${escapeHtml(path)}" data-ftype="chips" data-kind="${escapeHtml(kind)}">
    ${chips}<input placeholder="${kind === 'int' ? '输入 QQ 号/群号后回车' : '输入后回车添加'}">
  </div>`;
}

export function readChips(el) {
  if (!el) return [];
  return Array.from(el.querySelectorAll('.chip')).map((c) => c.textContent.trim());
}

/* 列表标题行：标题 + 「从列表选择」按钮 */
function toolListHead(label, path) {
  return `<div class="tool-list-head">
    <div class="field-label" style="margin:0">${label}</div>
    <button type="button" class="btn sm ghost" data-tool-pick="${escapeHtml(path)}">${icon('edit')} 从列表选择</button>
  </div>`;
}

/* ---------- 预设模块渲染 ---------- */

/**
 * 渲染单个工具预设模块
 * @param {string} key 预设名（即 config.json tool_presets 的键）
 * @param {*} value 预设取值（null / string[] / {default,deferred}）
 * @param {{withToggle?: boolean, nullAsEmpty?: boolean}} opts
 *   withToggle: 是否渲染「限制工具」开关（聊天页弹窗传 false）
 *   nullAsEmpty: 值为 null 时降级为空白名单（聊天页弹窗传 true，避免 null 语义歧义）
 */
export function renderToolPresetModule(key, value, opts = {}) {
  const { withToggle = true, nullAsEmpty = false } = opts;
  let st = toolPresetState(value);
  let notice = '';
  if (st.isNull && nullAsEmpty) {
    st = { isNull: false, isDict: false, def: [], deferred: [] };
    notice = '<p class="field-desc">当前配置为 <code>null</code>（不限制 = 全部工具）。勾选并保存后会变为白名单模式。</p>';
  }

  const head = withToggle
    ? `<div class="toggle-row">
        <div class="field-label" style="margin:0">${escapeHtml(presetLabel(key))} ${escapeHtml(key)} · 限制工具</div>
        <label class="toggle"><input type="checkbox" data-tools-restrict="${escapeHtml(key)}" ${st.isNull ? '' : 'checked'}><span class="track"></span><span class="thumb"></span></label>
      </div>
      <p class="field-desc">开关开启 = 白名单模式：该模块只能使用下方列出的工具。开关关闭 = 不限制：向模型暴露全部已加载的工具（保存为 <code>null</code>，不推荐——其中包含禁言、执行命令等场景专用工具），下方列表不生效。</p>`
    : `<div class="field-label" style="margin:0">${escapeHtml(presetLabel(key))} ${escapeHtml(key)} · 工具列表</div>`;

  const body = st.isDict
    ? `
      ${toolListHead('默认工具 default · 直接暴露给模型，可直接调用', `__tools.${key}.default`)}
      ${renderChips(`__tools.${key}.default`, 'str', st.def)}
      ${toolListHead('待发现工具 deferred · 不直接暴露给模型', `__tools.${key}.deferred`)}
      ${renderChips(`__tools.${key}.deferred`, 'str', st.deferred)}
      <p class="field-desc">deferred 中的工具不出现在模型的工具列表里；模型须先调用 default 中的 <code>tool_search</code> 搜索到它，才会在当轮临时启用（仅当轮有效）。两条硬性规则（保存时会校验）：① default 必须保留 <code>tool_search</code>，否则整个 deferred 列表无效；② 配置了 <code>tool_search</code> 就必须在 deferred 中至少放一个工具，否则没有可发现的内容。若删除 default 中的 tool_search 且 deferred 为空，会自动切回单列表白名单模式。</p>`
    : `
      ${toolListHead('工具白名单 · 只有此处列出的工具会暴露给模型', `__tools.${key}`)}
      ${renderChips(`__tools.${key}`, 'str', st.def)}
      <p class="field-desc">列表为空 = 该模块没有任何可用工具。在上方输入 <code>tool_search</code> 并回车，自动切换为「默认 + 待发现」双列表模式。</p>`;

  /* 预设专属说明只在带「限制工具」开关时展示（聊天页弹窗没有该开关，避免误导） */
  const extraNote = withToggle ? lookup(PRESET_NOTES, key) : undefined;

  return `<div class="field" data-tools-field="${escapeHtml(key)}">
    ${head}
    ${notice}
    ${extraNote ? `<p class="field-desc">${extraNote}</p>` : ''}
    <div class="tools-body"${st.isNull ? ' style="opacity:.4;pointer-events:none"' : ''}>${body}</div>
  </div>`;
}

/* 就地重渲染某个预设模块（切换 白名单 ⇄ 双列表 模式时使用）
   按元素定位而不是 document.querySelector(key)：配置页与聊天页弹窗可能同时存在同名模块 */
function replaceModuleInPlace(fieldWrap, key, value) {
  if (!fieldWrap || !fieldWrap.isConnected) return;
  const tmp = document.createElement('div');
  tmp.innerHTML = renderToolPresetModule(key, value, {
    withToggle: !!fieldWrap.querySelector('[data-tools-restrict]'),
  });
  fieldWrap.replaceWith(tmp.firstElementChild);
  notifyChange();
}

/* 删除工具 chip 后的联动：default 失去 tool_search 时收敛/告警 */
function afterToolChipRemoved(fieldWrap) {
  if (!fieldWrap || !fieldWrap.isConnected) return;
  const key = fieldWrap.dataset.toolsField;
  const defEl = fieldWrap.querySelector(`[data-path="__tools.${key}.default"]`);
  if (!defEl) return; /* 单列表模式，无需处理 */
  const defNames = readChips(defEl);
  const deferredNames = readChips(fieldWrap.querySelector(`[data-path="__tools.${key}.deferred"]`));
  if (defNames.includes('tool_search')) {
    if (deferredNames.length === 0) {
      toast('deferred 已清空：请至少添加一个待发现工具，或删除 default 中的 tool_search 切回白名单，否则无法保存', 'error', 6000);
    }
    return;
  }
  if (deferredNames.length === 0) {
    replaceModuleInPlace(fieldWrap, key, defNames);
    toast('已切回工具白名单模式', 'info');
  } else {
    toast('default 中已没有 tool_search，deferred 里的工具将无法被模型发现', 'error');
  }
}

/* ---------- 工具勾选弹窗（数据来自 GET /api/tools） ---------- */

let toolCatalog = null; /* /api/tools 的缓存 {tools:[...]}，弹窗内可强制刷新 */

async function fetchToolCatalog(force = false) {
  if (toolCatalog && !force) return toolCatalog;
  const res = await api.get('/tools');
  if (!res || res.available === false) return null; /* bot 未启动 / ToolCalls 未注册 */
  toolCatalog = { tools: res.tools || [] };
  return toolCatalog;
}

/* 路径 → 弹窗标题：__tools.group_chat.default → 「群聊 group_chat · 默认工具 default」 */
function presetPathTitle(path) {
  const m = /^__tools\.([^.]+)(?:\.(default|deferred))?$/.exec(path);
  if (!m) return path;
  const base = `${presetLabel(m[1])} ${m[1]}`;
  if (m[2] === 'default') return `${base} · 默认工具 default`;
  if (m[2] === 'deferred') return `${base} · 待发现工具 deferred`;
  return `${base} · 工具白名单`;
}

/* 勾选结果写回 chips，并联动 白名单⇄双列表 模式切换 */
function applyChips(path, names, root = document) {
  const chipsEl = root.querySelector(`[data-path="${path}"]`);
  if (!chipsEl) return;
  const moduleField = chipsEl.closest('[data-tools-field]');
  const moduleKey = moduleField?.dataset.toolsField || null;

  /* 白名单勾入 tool_search → 自动升级为「默认+待发现」双列表（与手动输入一致） */
  if (moduleKey && path === `__tools.${moduleKey}` && names.includes('tool_search')) {
    replaceModuleInPlace(moduleField, moduleKey, { default: names, deferred: [] });
    toast('已切换为「默认 + 待发现」双列表模式，请继续为 deferred 选择待发现工具', 'success');
    return;
  }

  const tmp = document.createElement('div');
  tmp.innerHTML = renderChips(path, 'str', names);
  const fresh = tmp.firstElementChild;
  chipsEl.replaceWith(fresh);
  notifyChange();

  /* default 勾掉 tool_search → 复用删除联动：deferred 空则收回白名单，非空则告警 */
  if (moduleKey && path === `__tools.${moduleKey}.default` && !names.includes('tool_search')) {
    afterToolChipRemoved(moduleField);
  }
}

async function openToolPicker(path, { root = document } = {}) {
  const chipsEl = root.querySelector(`[data-path="${path}"]`);
  if (!chipsEl) return;

  let catalog;
  try {
    catalog = await fetchToolCatalog();
  } catch (e) {
    toast(`获取工具列表失败：${e.message}`, 'error', 5000);
    return;
  }
  if (!catalog) {
    toast('工具服务未就绪（bot 未启动或工具未加载），暂无法勾选，可继续手动输入工具名', 'error', 5000);
    return;
  }

  const key = /^__tools\.([^.]+)/.exec(path)?.[1] || '';
  const scope = presetScope(key);
  const scopeBadge = { group: '群聊', private: '私聊' };
  const selected = new Set(readChips(chipsEl));

  const rows = catalog.tools.map((t) => {
    const off = t.active === false;
    return `<label class="tool-pick-row${off ? ' inactive' : ''}"
      data-namelc="${escapeHtml(t.name.toLowerCase())}" data-desclc="${escapeHtml((t.description || '').toLowerCase())}" data-scope="${escapeHtml(t.chat_scope || 'both')}">
      <input type="checkbox" data-pick="${escapeHtml(t.name)}" ${selected.has(t.name) ? 'checked' : ''}${off ? ' disabled' : ''}>
      <div class="tp-main">
        <div class="tp-line">
          <span class="tp-name mono">${escapeHtml(t.name)}</span>
          ${t.source === 'mcp' ? `<span class="badge teal" title="MCP 服务: ${escapeHtml(t.mcp_server || '')}">MCP${t.mcp_server ? ` · ${escapeHtml(t.mcp_server)}` : ''}</span>` : '<span class="badge gray">本地</span>'}
          ${SCOPE_BADGES[t.chat_scope] || ''}
          ${off ? '<span class="badge red">未启用</span>' : ''}
        </div>
        <div class="tp-desc muted small">${escapeHtml(t.description || '（无描述）')}</div>
      </div>
    </label>`;
  }).join('');

  /* chips 里已有但不在当前工具目录中的名字（未加载/已改名/MCP 离线）：
     渲染成置顶的「未加载」行并保持勾选，避免确认时被静默丢弃 */
  const known = new Set(catalog.tools.map((t) => t.name));
  const missingRows = [...selected].filter((n) => !known.has(n)).map((n) => `
    <label class="tool-pick-row" data-namelc="${escapeHtml(n.toLowerCase())}" data-desclc="" data-scope="both">
      <input type="checkbox" data-pick="${escapeHtml(n)}" checked>
      <div class="tp-main">
        <div class="tp-line">
          <span class="tp-name mono">${escapeHtml(n)}</span>
          <span class="badge orange">未加载</span>
        </div>
        <div class="tp-desc muted small">不在当前工具列表中（工具未加载、已改名或所属 MCP 服务离线）；保留勾选则配置维持原样</div>
      </div>
    </label>`).join('');

  const modal = openModal({
    title: `选择工具 · ${presetPathTitle(path)}`,
    wide: true,
    bodyHtml: `
      <div class="filter-bar">
        <input class="input" id="tp-search" placeholder="搜索名称 / 描述" style="width:220px">
        ${scope ? `<label class="check-row"><input type="checkbox" id="tp-scope" checked>仅适用${scopeBadge[scope]}场景</label>` : ''}
        <span class="spacer"></span>
        <button type="button" class="btn sm ghost" id="tp-refresh" title="重新拉取工具列表">${icon('refresh')} 刷新</button>
      </div>
      <div class="tool-pick-list" id="tp-list">${missingRows}${rows || (missingRows ? '' : '<p class="muted" style="padding:12px">当前没有已加载的工具</p>')}</div>
      <p class="field-desc">勾选状态即该列表的最终内容（保存前不会写入配置）。未启用的工具无法勾选；场景不符的工具运行时会被剔除，建议只选适用的。</p>`,
    actions: [
      { label: '取消', class: 'ghost', onClick: ({ close }) => close() },
      {
        label: `确定（已选 ${selected.size}）`,
        class: 'primary',
        onClick: ({ close, el }) => {
          const names = [...el.querySelectorAll('#tp-list input[data-pick]:checked')].map((c) => c.dataset.pick);
          applyChips(path, names, root);
          close();
        },
      },
    ],
  });

  const modalRoot = modal.el;
  const confirmBtn = modalRoot.querySelector('.modal-foot [data-action="1"]');
  const updateCount = () => {
    const n = modalRoot.querySelectorAll('#tp-list input[data-pick]:checked').length;
    if (confirmBtn) confirmBtn.textContent = `确定（已选 ${n}）`;
  };
  const applyFilter = () => {
    const q = modalRoot.querySelector('#tp-search')?.value.trim().toLowerCase() || '';
    const scopeOnly = modalRoot.querySelector('#tp-scope')?.checked ?? false;
    modalRoot.querySelectorAll('.tool-pick-row').forEach((row) => {
      const checked = row.querySelector('input').checked;
      const hitSearch = !q || row.dataset.namelc.includes(q) || row.dataset.desclc.includes(q);
      const hitScope = !scopeOnly || checked || row.dataset.scope === 'both' || row.dataset.scope === scope;
      row.classList.toggle('hidden', !(hitSearch && hitScope));
    });
  };

  modalRoot.querySelector('#tp-search')?.addEventListener('input', applyFilter);
  modalRoot.querySelector('#tp-scope')?.addEventListener('change', applyFilter);
  modalRoot.querySelector('#tp-list').addEventListener('change', (e) => {
    if (!e.target.matches('input[data-pick]')) return;
    updateCount();
    applyFilter(); /* 已勾选的行不受「仅适用场景」过滤影响 */
  });
  modalRoot.querySelector('#tp-refresh').addEventListener('click', async () => {
    try {
      const fresh = await fetchToolCatalog(true);
      if (!fresh) { toast('工具服务未就绪，刷新失败', 'error'); return; }
    } catch (e) {
      toast(`刷新失败：${e.message}`, 'error', 5000);
      return;
    }
    modal.close();
    openToolPicker(path, { root }); /* 用新目录重开（勾选状态以当前 chips 为准） */
  });
  applyFilter();
}

/* ---------- 交互绑定（keydown 回车加 chip / chip 删除 / 限制开关 / 从列表选择） ---------- */

const boundRoots = new WeakSet();

export function bindChipInteractions(root) {
  if (!root || boundRoots.has(root)) return;
  boundRoots.add(root);

  root.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || !e.target.matches('.chips input')) return;
    e.preventDefault();
    const raw = e.target.value.trim();
    if (!raw) return;
    const chipsEl = e.target.closest('.chips');
    const kind = chipsEl.dataset.kind;
    if (kind === 'int' && !/^\d+$/.test(raw)) { toast('请输入纯数字 ID', 'error'); return; }
    /* 白名单中输入 tool_search → 自动切换为「默认 + 待发现」双列表模式（只有这一个名字触发升级） */
    const toolMod = raw === TOOL_SEARCH_NAME ? /^__tools\.([^.]+)$/.exec(chipsEl.dataset.path || '') : null;
    if (toolMod) {
      const defNames = readChips(chipsEl);
      if (!defNames.includes(TOOL_SEARCH_NAME)) defNames.push(TOOL_SEARCH_NAME);
      replaceModuleInPlace(chipsEl.closest('[data-tools-field]'), toolMod[1], { default: defNames, deferred: [] });
      toast('已切换为「默认 + 待发现」双列表模式，可在 deferred 中添加待发现工具', 'success');
      return;
    }
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.innerHTML = `${escapeHtml(raw)}<button data-del-x>${icon('x')}</button>`;
    chipsEl.insertBefore(chip, e.target);
    e.target.value = '';
    notifyChange();
  });

  root.addEventListener('click', (e) => {
    const del = e.target.closest('[data-del]') || e.target.closest('[data-del-x]');
    if (del) {
      const chip = del.closest('.chip');
      if (chip) {
        const toolsField = chip.closest('[data-tools-field]');
        chip.style.transform = 'scale(0.7)';
        chip.style.opacity = '0';
        setTimeout(() => {
          chip.remove();
          afterToolChipRemoved(toolsField);
          notifyChange();
        }, 140);
      }
      return;
    }
    /* 「从列表选择」→ 打开工具勾选弹窗 */
    const pickBtn = e.target.closest('[data-tool-pick]');
    if (pickBtn) openToolPicker(pickBtn.dataset.toolPick, { root });
  });

  root.addEventListener('change', (e) => {
    const el = e.target;
    /* 工具「限制工具」开关 → 启用/禁用对应模块的工具列表 */
    if (!el.matches?.('[data-tools-restrict]')) return;
    const body = root.querySelector(`[data-tools-field="${el.dataset.toolsRestrict}"] .tools-body`);
    if (body) {
      body.style.opacity = el.checked ? '' : '0.4';
      body.style.pointerEvents = el.checked ? '' : 'none';
    }
  });
}
