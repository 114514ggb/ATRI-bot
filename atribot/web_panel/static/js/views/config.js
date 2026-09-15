/* 视图：主配置编辑（表单 + 源码双模式） */

import { api } from '../api.js';
import { icon, toast, escapeHtml, confirmDialog, openModal, attachSuggest } from '../ui.js';
import { SCHEMA, CHAT_PARAM_DEFS, CHAT_PARAM_VALUE_TYPES } from '../config-schema.js';
import { createJsonEditor } from '../components/json-editor.js';
import * as kit from '../components/editor-kit.js';

let original = null; // 服务器当前配置（diff 基准）
let formBase = null; // 表单渲染基础（源码→表单时更新）
let pathLabel = '';
let suppliers = []; // [{name, models:{...}}]
let personas = [];
let editor = null;
let saveBar = null;
let mode = 'form';
let observer = null;
let toolCatalog = null; // /api/tools 的缓存 {tools:[...]}，弹窗内可强制刷新

/* ---------- 字段控件渲染 ---------- */

function supplierOptions() {
  return suppliers.map((s) => s.name);
}

function modelOptions(supplierName) {
  const found = suppliers.find((s) => s.name === supplierName);
  return found ? Object.keys(found.models || {}) : [];
}

/* 配置文件里的值不在选项列表时（供应商下架/改名/手改文件），追加占位选项保住原值，
   避免 select 塌缩为「未设置」导致保存时静默丢配置 */
function extraOption(current, options) {
  if (!current || options.includes(current)) return '';
  return `<option value="${escapeHtml(current)}" selected>${escapeHtml(current)}（不在可选列表）</option>`;
}

function renderControl(field, value) {
  const v = value === undefined || value === null ? '' : value;
  switch (field.type) {
    case 'toggle':
      return `<label class="toggle"><input type="checkbox" data-path="${field.path}" data-ftype="toggle" ${v ? 'checked' : ''}><span class="track"></span><span class="thumb"></span></label>`;

    case 'select':
      return `<select class="select" data-path="${field.path}" data-ftype="select">
        ${field.options.map((o) => `<option value="${escapeHtml(o)}" ${o === v ? 'selected' : ''}>${escapeHtml(o === '' ? '（未设置）' : o)}</option>`).join('')}
      </select>`;

    case 'supplier-select':
      return `<select class="select" data-path="${field.path}" data-ftype="select" data-supplier="1">
        <option value="">（未设置）</option>
        ${supplierOptions().map((o) => `<option value="${escapeHtml(o)}" ${o === v ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}
        ${extraOption(v, supplierOptions())}
      </select>`;

    case 'model-select':
      return `<select class="select" data-path="${field.path}" data-ftype="select" data-depends="${field.depends}">
        <option value="">（未设置）</option>
        ${modelOptions(kit.getPath(formBase, field.depends)).map((o) => `<option value="${escapeHtml(o)}" ${o === v ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}
        ${extraOption(v, modelOptions(kit.getPath(formBase, field.depends)))}
      </select>`;

    case 'persona-select':
      return `<select class="select" data-path="${field.path}" data-ftype="select">
        <option value="none">none（无人设）</option>
        ${personas.map((p) => `<option value="${escapeHtml(p.key)}" ${p.key === v ? 'selected' : ''}>${escapeHtml(p.key)}</option>`).join('')}
        ${extraOption(v, ['none', ...personas.map((p) => p.key)])}
      </select>`;

    case 'number':
      return `<input class="input mono" type="number" data-path="${field.path}" data-ftype="number"
        value="${escapeHtml(String(v))}" ${field.step ? `step="${field.step}"` : ''} ${field.min !== undefined ? `min="${field.min}"` : ''} ${field.max !== undefined ? `max="${field.max}"` : ''} placeholder="${field.optional ? '（可选）' : ''}">`;

    case 'password':
      return `<input class="input mono" type="password" data-path="${field.path}" data-ftype="text" value="${escapeHtml(String(v))}" autocomplete="new-password">`;

    case 'chips-int':
      return renderChips(field.path, 'int', Array.isArray(value) ? value : []);

    default:
      return `<input class="input" type="text" data-path="${field.path}" data-ftype="text" value="${escapeHtml(String(v))}" placeholder="${field.optional ? '（可选）' : ''}">`;
  }
}

function renderChips(path, kind, values) {
  const chips = values
    .map((val, i) => `<span class="chip" data-i="${i}">${escapeHtml(String(val))}<button data-del="${i}" title="删除">${icon('x')}</button></span>`)
    .join('');
  return `<div class="chips" data-path="${path}" data-ftype="chips" data-kind="${kind}">
    ${chips}<input placeholder="${kind === 'int' ? '输入 QQ 号/群号后回车' : '输入后回车添加'}">
  </div>`;
}

function fieldHtml(field, value) {
  return `<div class="field ${field.span ? 'span-2' : ''}" data-field="${field.path}">
    <div class="field-label">${escapeHtml(field.label)}${field.optional ? `<span class="muted small">（可选）</span>` : ''}</div>
    ${renderControl(field, value)}
    ${field.desc ? `<p class="field-desc">${field.desc}</p>` : ''}
  </div>`;
}

/* ---------- 特殊区块渲染 ---------- */

function renderPlatforms(platforms) {
  const entries = Object.entries(platforms || {});
  const cards = entries.map(([key, conf], idx) => renderPlatformCard(key, conf || {}, idx)).join('');
  return `
    <div id="platforms-container" data-ftype="platforms">${cards || `<p class="muted" style="margin:4px 0 12px">尚无平台配置，点击下方按钮添加。</p>`}</div>
    <button class="btn sm" id="btn-add-platform">${icon('plus')} 添加平台</button>`;
}

function renderPlatformCard(key, conf, idx) {
  const conn = conf.connection_type || 'WebSocket_client';
  const fields = SCHEMA[0].itemFields.filter((f) => !f.conn || f.conn.includes(conn));
  const controls = fields
    .map((f) => {
      const val = conf[f.key] !== undefined ? conf[f.key] : f.type === 'toggle' ? true : '';
      return `<div class="field ${['url', 'access_token'].includes(f.key) ? 'span-2' : ''}">
        <div class="field-label">${escapeHtml(f.label)}</div>
        ${f.type === 'toggle'
          ? `<label class="toggle"><input type="checkbox" data-pkey="${escapeHtml(key)}" data-fkey="${f.key}" ${val ? 'checked' : ''}><span class="track"></span><span class="thumb"></span></label>`
          : f.type === 'select'
            ? `<select class="select" data-pkey="${escapeHtml(key)}" data-fkey="${f.key}" ${f.key === 'connection_type' ? 'data-conn-switch="1"' : ''}>
                ${f.options.map((o) => `<option value="${escapeHtml(o)}" ${o === conf[f.key] ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}
              </select>`
            : `<input class="input ${f.key.includes('token') || f.key === 'url' ? 'mono' : ''}" type="text" data-pkey="${escapeHtml(key)}" data-fkey="${f.key}" value="${escapeHtml(String(val))}" placeholder="${f.optional ? '（可选）' : ''}">`}
        ${f.desc ? `<p class="field-desc">${f.desc}</p>` : ''}
      </div>`;
    })
    .join('');

  return `<div class="platform-card" data-pkey="${escapeHtml(key)}" style="animation-delay:${Math.min(idx * 60, 300)}ms">
    <div class="platform-head">
      <span class="name">${escapeHtml(key)}</span>
      <span class="badge blue">${escapeHtml(conf.adapter || 'onebot')}</span>
      <span style="flex:1"></span>
      <button class="icon-btn del" data-del-platform="${escapeHtml(key)}" title="删除该平台">${icon('trash')}</button>
    </div>
    <div class="field-grid">${controls}</div>
  </div>`;
}

function renderStandby(list) {
  const arr = Array.isArray(list) ? list : [];
  const items = arr.map((m, i) => `
    <div class="sortable-item" data-idx="${i}">
      <span class="drag-num">${i + 1}</span>
      <div class="content">
        <select class="select" data-sb="supplier">
          <option value="">（供应商）</option>
          ${supplierOptions().map((o) => `<option value="${escapeHtml(o)}" ${o === m.supplier ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}
          ${extraOption(m.supplier, supplierOptions())}
        </select>
        <select class="select" data-sb="model">
          <option value="">（模型）</option>
          ${modelOptions(m.supplier).map((o) => `<option value="${escapeHtml(o)}" ${o === m.model_name ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}
          ${extraOption(m.model_name, modelOptions(m.supplier))}
        </select>
      </div>
      <div class="ops">
        <button class="icon-btn" data-op="up" ${i === 0 ? 'disabled' : ''}>${icon('up')}</button>
        <button class="icon-btn" data-op="down" ${i === arr.length - 1 ? 'disabled' : ''}>${icon('down')}</button>
        <button class="icon-btn del" data-op="del">${icon('trash')}</button>
      </div>
    </div>`).join('');

  return `<div class="sortable-list" id="standby-container">${items || '<p class="muted" style="margin:2px 0 10px">未配置备用模型。主模型失败后将直接报错。</p>'}</div>
    <button class="btn sm" id="btn-add-standby">${icon('plus')} 添加备用模型</button>`;
}

/* ---------- 聊天请求参数（自由键值对，原样透传给模型 API） ---------- */

/* 值的 JS 类型 → 通用控件类型 */
function inferValueType(v) {
  if (typeof v === 'boolean') return 'bool';
  if (typeof v === 'number') return 'num';
  if (v !== null && typeof v === 'object') return 'json';
  return 'str';
}

function chatParamValueControl(key, vtype, value) {
  const def = CHAT_PARAM_DEFS[key];
  if (def?.type === 'select') {
    const v = value === undefined || value === null ? '' : String(value);
    const opts = def.optional ? ['', ...def.options] : def.options;
    return `<select class="select" data-cp="value" data-vtype="select">
      ${opts.map((o) => `<option value="${escapeHtml(o)}" ${o === v ? 'selected' : ''}>${escapeHtml(o === '' ? '（未设置）' : o)}</option>`).join('')}
      ${extraOption(v, opts)}
    </select>`;
  }
  switch (vtype) {
    case 'bool':
      return `<label class="toggle"><input type="checkbox" data-cp="value" data-vtype="bool" ${value ? 'checked' : ''}><span class="track"></span><span class="thumb"></span></label>`;
    case 'num':
      return `<input class="input mono" type="number" data-cp="value" data-vtype="num" value="${escapeHtml(String(value ?? ''))}"${def?.step ? ` step="${def.step}"` : ''}${def?.min !== undefined ? ` min="${def.min}"` : ''}${def?.max !== undefined ? ` max="${def.max}"` : ''} placeholder="（可选）">`;
    case 'json':
      return `<input class="input mono kv-json" type="text" data-cp="value" data-vtype="json" value="${escapeHtml(value !== null && typeof value === 'object' ? JSON.stringify(value) : String(value ?? ''))}" placeholder='如 {"type": "json_object"}' spellcheck="false">`;
    default:
      return `<input class="input" type="text" data-cp="value" data-vtype="str" value="${escapeHtml(String(value ?? ''))}" placeholder="（可选）">`;
  }
}

function renderChatParamRow(key, value) {
  const def = CHAT_PARAM_DEFS[key];
  const vtype = def ? def.type : inferValueType(value);
  const typeSel = def
    ? ''
    : `<select class="select kv-type" data-cp="type" title="值类型">${CHAT_PARAM_VALUE_TYPES.map((t) => `<option value="${t.key}" ${t.key === vtype ? 'selected' : ''}>${t.label}</option>`).join('')}</select>`;
  const desc = def && (def.label || def.desc) ? `<p class="kv-desc">${escapeHtml(def.label)}${def.desc ? ` · ${escapeHtml(def.desc)}` : ''}</p>` : '';
  return `<div class="kv-row${def ? ' known' : ''}" data-known="${def ? '1' : '0'}">
    <div class="kv-line">
      <input class="input mono kv-key" data-cp="key" value="${escapeHtml(String(key ?? ''))}" placeholder="参数名" spellcheck="false" autocomplete="off">
      ${typeSel}
      <div class="kv-value">${chatParamValueControl(key, vtype, value)}</div>
      <button class="icon-btn del" data-cp-del title="删除该参数">${icon('trash')}</button>
    </div>
    ${desc}
  </div>`;
}

function renderChatParams(params) {
  const rows = Object.entries(params || {}).map(([k, v]) => renderChatParamRow(k, v)).join('');
  return `
    <div class="sortable-list" id="chatparams-container">${rows || '<p class="muted kv-empty" style="margin:2px 0 10px">未配置请求参数，将使用内置默认参数。点击下方按钮添加。</p>'}</div>
    <button class="btn sm" id="btn-add-chatparam">${icon('plus')} 添加参数</button>`;
}

/* 参数名建议列表：已知参数中排除其他行已用与当前值本身，按输入子串过滤 */
function chatKeySuggestProvider(inputEl) {
  return (query) => {
    const used = new Set();
    document.querySelectorAll('#chatparams-container [data-cp="key"]').forEach((el) => {
      if (el !== inputEl && el.value.trim()) used.add(el.value.trim());
    });
    const current = inputEl.value.trim();
    const q = query.trim().toLowerCase();
    return Object.entries(CHAT_PARAM_DEFS)
      .filter(([k]) => !q || k.toLowerCase().includes(q))
      .filter(([k]) => !used.has(k) && k !== current)
      .map(([k, d]) => ({ value: k, label: k, desc: d.label || d.desc || '' }));
  };
}

/* 行内当前值（键名/类型变化整行重渲染时保住已输入的值；JSON 非法时保留原文） */
function readChatRowValue(row) {
  const el = row.querySelector('[data-cp="value"]');
  if (!el) return undefined;
  const vtype = el.dataset.vtype;
  if (vtype === 'bool') return el.checked;
  if (vtype === 'num') return el.value === '' ? undefined : Number(el.value);
  if (vtype === 'json') { try { return JSON.parse(el.value); } catch { return el.value; } }
  return el.value === '' ? undefined : el.value;
}

function replaceChatParamRow(row, key, value) {
  const tmp = document.createElement('div');
  tmp.innerHTML = renderChatParamRow(key, value);
  row.replaceWith(tmp.firstElementChild);
  refreshDirty();
}

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

const TOOL_MODULE_TITLES = { private_chat: '私聊 private_chat', agency_Agent: '子代理 agency_Agent' };

function renderToolModule(key, value) {
  const st = toolPresetState(value);
  const dim = st.isNull ? ' style="opacity:.4;pointer-events:none"' : '';
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
      <p class="field-desc">列表为空 = 该模块没有任何可用工具。在上方输入 <code>tool_search</code> 并回车，自动切换为「默认 + 待发现」双列表模式（同群聊 group_chat）。</p>`;
  return `<div class="field" data-tools-field="${key}">
    <div class="toggle-row">
      <div class="field-label" style="margin:0">${TOOL_MODULE_TITLES[key]} · 限制工具</div>
      <label class="toggle"><input type="checkbox" data-tools-restrict="${key}" ${st.isNull ? '' : 'checked'}><span class="track"></span><span class="thumb"></span></label>
    </div>
    <p class="field-desc">开关开启 = 白名单模式：该模块只能使用下方列出的工具。开关关闭 = 不限制：向模型暴露全部已加载的工具（保存为 <code>null</code>，不推荐——其中包含禁言、执行命令等场景专用工具），下方列表不生效。</p>
    <div class="tools-body"${dim}>${body}</div>
  </div>`;
}

/* 就地重渲染某个工具模块（切换 白名单 ⇄ 双列表 模式时使用） */
function replaceToolModule(key, value) {
  const wrap = document.querySelector(`[data-tools-field="${key}"]`);
  if (!wrap) return;
  const tmp = document.createElement('div');
  tmp.innerHTML = renderToolModule(key, value);
  wrap.replaceWith(tmp.firstElementChild);
  refreshDirty();
}

/* 删除工具 chip 后的联动：default 失去 tool_search 时收敛/告警 */
function afterToolChipRemoved(fieldWrap) {
  if (!fieldWrap || !fieldWrap.isConnected) return;
  const key = fieldWrap.dataset.toolsField;
  const defEl = fieldWrap.querySelector(`[data-path="__tools.${key}.default"]`);
  if (!defEl) return; /* 单列表模式，无需处理 */
  const defNames = readChips(defEl);
  const deferredNames = readChips(fieldWrap.querySelector(`[data-path="__tools.${key}.deferred"]`) || document.createElement('div'));
  if (defNames.includes('tool_search')) {
    if (deferredNames.length === 0) {
      toast('deferred 已清空：请至少添加一个待发现工具，或删除 default 中的 tool_search 切回白名单，否则无法保存', 'error', 6000);
    }
    return;
  }
  if (deferredNames.length === 0) {
    replaceToolModule(key, defNames);
    toast('已切回工具白名单模式', 'info');
  } else {
    toast('default 中已没有 tool_search，deferred 里的工具将无法被模型发现', 'error');
  }
}

function renderToolPresets(presets) {
  const gc = presets?.group_chat || {};
  const gcDef = Array.isArray(gc.default) ? gc.default : [];
  const gcDeferred = Array.isArray(gc.deferred) ? gc.deferred : [];

  return `
    <div class="notice info">${icon('info')}<div><b>default</b> 中的工具直接暴露给模型；<b>deferred</b>（待发现）中的工具不直接暴露，模型需通过 default 里的 <code>tool_search</code> 搜索后才在当轮临时启用。<code>tool_search</code> 与 deferred 必须成对出现——配了 tool_search 就要在 deferred 中至少放一个工具，配了 deferred 就必须把 tool_search 加进 default，否则保存时会被拦截。私聊 / 子代理在白名单里输入 <code>tool_search</code> 回车即可切换为双列表模式；「限制工具」开关关闭 = 保存为 null = 全部工具（不推荐）。</div></div>
    <div class="field-grid">
      <div class="field span-2">
        ${toolListHead('群聊 group_chat · 默认工具 default（直接暴露给模型）', '__tools.group_chat.default')}
        ${renderChips('__tools.group_chat.default', 'str', gcDef)}
      </div>
      <div class="field span-2">
        ${toolListHead('群聊 group_chat · 待发现工具 deferred（不直接暴露）', '__tools.group_chat.deferred')}
        ${renderChips('__tools.group_chat.deferred', 'str', gcDeferred)}
        <p class="field-desc">模型通过 default 中的 tool_search 搜索后本轮临时启用；default 必须包含 tool_search</p>
      </div>
      ${renderToolModule('private_chat', presets?.private_chat)}
      ${renderToolModule('agency_Agent', presets?.agency_Agent)}
    </div>`;
}

/* ---------- 工具选择弹窗（数据来自 GET /api/tools） ---------- */

const PICK_TITLES = {
  '__tools.group_chat.default': '群聊 group_chat · 默认工具 default',
  '__tools.group_chat.deferred': '群聊 group_chat · 待发现工具 deferred',
  '__tools.private_chat.default': '私聊 private_chat · 默认工具 default',
  '__tools.private_chat.deferred': '私聊 private_chat · 待发现工具 deferred',
  '__tools.private_chat': '私聊 private_chat · 工具白名单',
  '__tools.agency_Agent.default': '子代理 agency_Agent · 默认工具 default',
  '__tools.agency_Agent.deferred': '子代理 agency_Agent · 待发现工具 deferred',
  '__tools.agency_Agent': '子代理 agency_Agent · 工具白名单',
};

const SCOPE_BADGES = { group: '<span class="badge blue">群聊</span>', private: '<span class="badge purple">私聊</span>', both: '' };

/* 列表标题行：标题 + 「从列表选择」按钮 */
function toolListHead(label, path) {
  return `<div class="tool-list-head">
    <div class="field-label" style="margin:0">${label}</div>
    <button type="button" class="btn sm ghost" data-tool-pick="${path}">${icon('edit')} 从列表选择</button>
  </div>`;
}

async function fetchToolCatalog(force = false) {
  if (toolCatalog && !force) return toolCatalog;
  const res = await api.get('/tools');
  if (!res || res.available === false) return null; /* bot 未启动 / ToolCalls 未注册 */
  toolCatalog = { tools: res.tools || [] };
  return toolCatalog;
}

/* 勾选结果写回 chips，并联动 白名单⇄双列表 模式切换 */
function applyChips(path, names) {
  const chipsEl = document.querySelector(`[data-path="${path}"]`);
  if (!chipsEl) return;
  const moduleField = chipsEl.closest('[data-tools-field]');
  const moduleKey = moduleField?.dataset.toolsField || null;

  /* 白名单勾入 tool_search → 自动升级为「默认+待发现」双列表（与手动输入一致） */
  if (moduleKey && path === `__tools.${moduleKey}` && names.includes('tool_search')) {
    replaceToolModule(moduleKey, { default: names, deferred: [] });
    toast('已切换为「默认 + 待发现」双列表模式，请继续为 deferred 选择待发现工具', 'success');
    return;
  }

  const tmp = document.createElement('div');
  tmp.innerHTML = renderChips(path, 'str', names);
  const fresh = tmp.firstElementChild;
  chipsEl.replaceWith(fresh);
  onFieldInput({ target: fresh });
  refreshDirty();

  /* default 勾掉 tool_search → 复用删除联动：deferred 空则收回白名单，非空则告警 */
  if (moduleKey && path === `__tools.${moduleKey}.default` && !names.includes('tool_search')) {
    afterToolChipRemoved(moduleField);
  }
}

async function openToolPicker(path) {
  const chipsEl = document.querySelector(`[data-path="${path}"]`);
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

  const scope = path.includes('group_chat') ? 'group' : path.includes('private_chat') ? 'private' : null;
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
    title: `选择工具 · ${PICK_TITLES[path] || path}`,
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
          applyChips(path, names);
          close();
        },
      },
    ],
  });

  const root = modal.el;
  const confirmBtn = root.querySelector('.modal-foot [data-action="1"]');
  const updateCount = () => {
    const n = root.querySelectorAll('#tp-list input[data-pick]:checked').length;
    if (confirmBtn) confirmBtn.textContent = `确定（已选 ${n}）`;
  };
  const applyFilter = () => {
    const q = root.querySelector('#tp-search')?.value.trim().toLowerCase() || '';
    const scopeOnly = root.querySelector('#tp-scope')?.checked ?? false;
    root.querySelectorAll('.tool-pick-row').forEach((row) => {
      const checked = row.querySelector('input').checked;
      const hitSearch = !q || row.dataset.namelc.includes(q) || row.dataset.desclc.includes(q);
      const hitScope = !scopeOnly || checked || row.dataset.scope === 'both' || row.dataset.scope === scope;
      row.classList.toggle('hidden', !(hitSearch && hitScope));
    });
  };

  root.querySelector('#tp-search')?.addEventListener('input', applyFilter);
  root.querySelector('#tp-scope')?.addEventListener('change', applyFilter);
  root.querySelector('#tp-list').addEventListener('change', (e) => {
    if (!e.target.matches('input[data-pick]')) return;
    updateCount();
    applyFilter(); /* 已勾选的行不受「仅适用场景」过滤影响 */
  });
  root.querySelector('#tp-refresh').addEventListener('click', async () => {
    try {
      const fresh = await fetchToolCatalog(true);
      if (!fresh) { toast('工具服务未就绪，刷新失败', 'error'); return; }
    } catch (e) {
      toast(`刷新失败：${e.message}`, 'error', 5000);
      return;
    }
    modal.close();
    openToolPicker(path); /* 用新目录重开（勾选状态以当前 chips 为准） */
  });
  applyFilter();
}

/* ---------- DOM 读取 → payload ---------- */

function readChips(el) {
  return Array.from(el.querySelectorAll('.chip')).map((c) => c.textContent.trim());
}

export function buildPayload() {
  const data = kit.deepClone(formBase || {});

  /* 普通字段 */
  document.querySelectorAll('[data-path][data-ftype]').forEach((el) => {
    const path = el.dataset.path;
    if (path.startsWith('__')) return;
    const ftype = el.dataset.ftype;
    let value;
    if (ftype === 'toggle') value = el.checked;
    else if (ftype === 'number') {
      if (el.value === '') { kit.unsetPath(data, path); return; }
      value = Number(el.value);
    } else if (ftype === 'chips') {
      value = readChips(el).map((x) => (el.dataset.kind === 'int' ? Number(x) : x));
    } else value = el.value;

    const field = findField(path);
    if (field?.optional && (value === '' || value === null)) { kit.unsetPath(data, path); return; }
    kit.setPath(data, path, value);
  });

  /* 平台 */
  const platforms = {};
  document.querySelectorAll('#platforms-container .platform-card').forEach((card) => {
    const key = card.dataset.pkey;
    const conf = {};
    card.querySelectorAll('[data-fkey]').forEach((el) => {
      const fkey = el.dataset.fkey;
      conf[fkey] = el.type === 'checkbox' ? el.checked : el.type === 'number' ? Number(el.value) : el.value;
    });
    if (!conf.source_name) delete conf.source_name;
    if (conf.enabled !== false) delete conf.enabled; /* 省略 = 默认启用，避免假 diff */
    platforms[key] = conf;
  });
  if (Object.keys(platforms).length) data.platforms = platforms;

  /* 备用模型 */
  const standby = [];
  document.querySelectorAll('#standby-container .sortable-item').forEach((item) => {
    const supplier = item.querySelector('[data-sb="supplier"]').value;
    const model = item.querySelector('[data-sb="model"]').value;
    if (supplier && model) standby.push({ supplier, model_name: model });
  });
  data.model = data.model || {};
  if (standby.length) data.model.standby_model = standby;
  else delete data.model.standby_model;

  /* 聊天请求参数：整表按行重建，键值对原样透传给模型 API */
  const cpContainer = document.querySelector('#chatparams-container');
  if (cpContainer) {
    const chatParams = {};
    cpContainer.querySelectorAll('.kv-row').forEach((row) => {
      const key = row.querySelector('[data-cp="key"]')?.value.trim();
      const el = row.querySelector('[data-cp="value"]');
      if (!key || !el) return;
      const vtype = el.dataset.vtype;
      let value;
      if (vtype === 'bool') value = el.checked;
      else if (vtype === 'num') {
        if (el.value === '' || !Number.isFinite(Number(el.value))) return;
        value = Number(el.value);
      } else if (vtype === 'json') {
        if (el.value.trim() === '') return;
        try { value = JSON.parse(el.value); } catch { return; } /* 非法 JSON 由 validateChatParams 拦截 */
      } else {
        if (el.value === '') return;
        value = el.value;
      }
      chatParams[key] = value;
    });
    if (Object.keys(chatParams).length) data.model.chat_parameter = chatParams;
    else delete data.model.chat_parameter; /* 空 dict 在后端为 falsy，等价走内置默认参数，保持配置干净 */
  }

  /* 工具预设 */
  const tools = {};
  tools.group_chat = {
    default: readChips(document.querySelector('[data-path="__tools.group_chat.default"]') || document.createElement('div')),
    deferred: readChips(document.querySelector('[data-path="__tools.group_chat.deferred"]') || document.createElement('div')),
  };
  for (const key of ['private_chat', 'agency_Agent']) {
    const restrictEl = document.querySelector(`[data-tools-restrict="${key}"]`);
    if (!restrictEl) { tools[key] = kit.getPath(formBase, `tool_presets.${key}`) ?? null; continue; }
    if (!restrictEl.checked) { tools[key] = null; continue; } /* 限制关闭 = null = 全部工具 */
    const defEl = document.querySelector(`[data-path="__tools.${key}.default"]`);
    if (defEl) {
      const def = readChips(defEl);
      const deferred = readChips(document.querySelector(`[data-path="__tools.${key}.deferred"]`) || document.createElement('div'));
      /* deferred 为空时双列表等价于白名单，统一回写成列表，避免产生歧义配置 */
      tools[key] = deferred.length ? { default: def, deferred } : def;
    } else {
      tools[key] = readChips(document.querySelector(`[data-path="__tools.${key}"]`) || document.createElement('div'));
    }
  }
  data.tool_presets = tools;

  return data;
}

function findField(path) {
  for (const section of SCHEMA) {
    for (const f of section.fields || []) if (f.path === path) return f;
  }
  return null;
}

/* 工具预设保存校验：tool_search 与 deferred 必须成对出现，缺一个就没有意义 */
function validateToolPresets(payload) {
  const errors = [];
  const presets = payload?.tool_presets;
  if (!presets || typeof presets !== 'object') return errors;
  const labels = { group_chat: '群聊 group_chat', private_chat: '私聊 private_chat', agency_Agent: '子代理 agency_Agent' };
  for (const [key, label] of Object.entries(labels)) {
    const v = presets[key];
    if (v === null || v === undefined) continue; /* null/缺省 = 全部或无工具，不涉及 deferred */
    const def = Array.isArray(v) ? v : Array.isArray(v.default) ? v.default : [];
    const deferred = Array.isArray(v?.deferred) ? v.deferred : [];
    if (def.includes('tool_search') && deferred.length === 0) {
      errors.push(`${label}：default 中配置了 tool_search，但 deferred 为空，没有可发现的内容。请在 deferred 中至少添加一个工具，或删除 tool_search 切回白名单模式`);
    } else if (!def.includes('tool_search') && deferred.length > 0) {
      errors.push(`${label}：配置了 deferred 工具，但 default 中没有 tool_search，这些工具将永远无法被模型发现。请把 tool_search 加进 default 或清空 deferred`);
    }
  }
  return errors;
}

/* 聊天请求参数保存校验（仅表单模式）：空键名 / 重复键 / 非法数字 / 非法 JSON，出错行标红 */
function validateChatParams() {
  const errors = [];
  const seen = new Set();
  document.querySelectorAll('#chatparams-container .kv-row').forEach((row) => {
    row.classList.remove('error');
    const key = row.querySelector('[data-cp="key"]')?.value.trim() ?? '';
    const el = row.querySelector('[data-cp="value"]');
    const hasValue = !!el && (el.dataset.vtype === 'bool' ? el.checked : String(el.value).trim() !== '');
    if (!key) {
      if (hasValue) { errors.push('有一行参数未填写参数名，该行会被忽略'); row.classList.add('error'); }
      return;
    }
    if (seen.has(key)) { errors.push(`参数名重复：${key}`); row.classList.add('error'); return; }
    seen.add(key);
    if (!el) return;
    if (el.dataset.vtype === 'num' && el.value !== '' && !Number.isFinite(Number(el.value))) {
      errors.push(`参数 ${key} 的数字值无效`); row.classList.add('error');
    } else if (el.dataset.vtype === 'json' && el.value.trim() !== '') {
      try { JSON.parse(el.value); } catch { errors.push(`参数 ${key} 的 JSON 值无效`); row.classList.add('error'); }
    }
  });
  return errors;
}

/* ---------- 表单整体渲染 ---------- */

function renderForm(section) {
  const anchor = section.querySelector('.config-anchor');
  const sectionsEl = section.querySelector('.config-sections');

  anchor.innerHTML = SCHEMA.map(
    (s) => `<a data-target="${s.id}">${icon(s.icon)} ${escapeHtml(s.label)}</a>`
  ).join('');

  sectionsEl.innerHTML = SCHEMA.map((s, i) => {
    let inner = '';
    if (s.type === 'platforms') inner = renderPlatforms(formBase.platforms);
    else if (s.type === 'standby-list') inner = renderStandby(formBase.model?.standby_model);
    else if (s.type === 'chat-params') inner = renderChatParams(kit.getPath(formBase, s.path));
    else if (s.type === 'tool-presets') inner = renderToolPresets(formBase.tool_presets);
    else {
      inner = `<div class="field-grid">${s.fields.map((f) => fieldHtml(f, kit.getPath(formBase, f.path))).join('')}</div>`;
    }
    return `<div class="config-section" id="cfgsec-${s.id}" style="animation-delay:${Math.min(i * 50, 400)}ms">
      <h3>${icon(s.icon)} ${escapeHtml(s.label)}</h3>
      ${s.desc ? `<p class="section-desc">${s.desc}</p>` : ''}
      ${inner}
    </div>`;
  }).join('');

  bindForm(section);
  updateChangedMarks();
}

let anchorLockUntil = 0; /* 点击锚点后的平滑滚动期间，不让 IntersectionObserver 抢走高亮 */

function setAnchorActive(id) {
  document.querySelectorAll('.config-anchor a').forEach((l) => l.classList.toggle('active', l.dataset.target === id));
}

function bindForm(section) {
  /* 锚点点击：先高亮再滚动（锚点元素每次渲染都是新的，需要重复绑定） */
  section.querySelectorAll('.config-anchor a').forEach((a) => {
    a.addEventListener('click', () => {
      anchorLockUntil = Date.now() + 900;
      setAnchorActive(a.dataset.target);
      const target = document.getElementById(`cfgsec-${a.dataset.target}`);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  /* 以下 section 级委托只绑一次：重复渲染（切换模式/回滚）时避免监听器累积 */
  if (section.dataset.formBound) return;
  section.dataset.formBound = '1';

  /* 字段变更 → 高亮 + dirty */
  section.addEventListener('input', onFieldInput);
  section.addEventListener('change', onFieldInput);

  /* 模型级联：供应商变化 → 更新依赖它的模型下拉 */
  section.addEventListener('change', (e) => {
    const el = e.target;
    if (el.matches('[data-supplier]')) {
      const supplierName = el.value;
      document.querySelectorAll(`[data-depends="${el.dataset.path}"]`).forEach((modelSel) => {
        const current = modelSel.value;
        modelSel.innerHTML = `<option value="">（未设置）</option>${modelOptions(supplierName)
          .map((o) => `<option value="${escapeHtml(o)}" ${o === current ? 'selected' : ''}>${escapeHtml(o)}</option>`)
          .join('')}${extraOption(current, modelOptions(supplierName))}`;
      });
    }
    /* 备用模型卡片内的供应商联动 */
    if (el.matches('[data-sb="supplier"]')) {
      const item = el.closest('.sortable-item');
      const modelSel = item.querySelector('[data-sb="model"]');
      const current = modelSel.value;
      modelSel.innerHTML = `<option value="">（模型）</option>${modelOptions(el.value)
        .map((o) => `<option value="${escapeHtml(o)}" ${o === current ? 'selected' : ''}>${escapeHtml(o)}</option>`)
        .join('')}${extraOption(current, modelOptions(el.value))}`;
    }
    /* 平台连接方式切换 → 重渲染该卡 */
    if (el.matches('[data-conn-switch]')) {
      const card = el.closest('.platform-card');
      const key = card.dataset.pkey;
      const conf = readPlatformCard(card);
      conf.connection_type = el.value;
      const idx = [...document.querySelectorAll('#platforms-container .platform-card')].indexOf(card);
      const tmp = document.createElement('div');
      tmp.innerHTML = renderPlatformCard(key, conf, idx);
      card.replaceWith(tmp.firstElementChild);
      toast(`已切换 ${key} 的连接方式为 ${el.value}，请补全对应字段`, 'info');
    }
    /* 工具「限制工具」开关 → 启用/禁用对应模块的工具列表 */
    if (el.matches('[data-tools-restrict]')) {
      const body = document.querySelector(`[data-tools-field="${el.dataset.toolsRestrict}"] .tools-body`);
      if (body) {
        body.style.opacity = el.checked ? '' : '0.4';
        body.style.pointerEvents = el.checked ? '' : 'none';
      }
    }
  });

  /* chips 交互（委托） */
  section.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.matches('.chips input')) {
      e.preventDefault();
      const raw = e.target.value.trim();
      if (!raw) return;
      const chipsEl = e.target.closest('.chips');
      const kind = chipsEl.dataset.kind;
      if (kind === 'int' && !/^\d+$/.test(raw)) { toast('请输入纯数字 ID', 'error'); return; }
      /* 白名单中输入 tool_search → 自动切换为「默认 + 待发现」双列表模式 */
      const toolMod = chipsEl.dataset.path?.match(/^__tools\.(private_chat|agency_Agent)$/);
      if (toolMod && raw === 'tool_search') {
        const defNames = readChips(chipsEl);
        if (!defNames.includes('tool_search')) defNames.push('tool_search');
        replaceToolModule(toolMod[1], { default: defNames, deferred: [] });
        toast('已切换为「默认 + 待发现」双列表模式，可在 deferred 中添加待发现工具', 'success');
        return;
      }
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.innerHTML = `${escapeHtml(raw)}<button data-del-x>${icon('x')}</button>`;
      chipsEl.insertBefore(chip, e.target);
      e.target.value = '';
      onFieldInput({ target: chipsEl });
    }
  });
  section.addEventListener('click', (e) => {
    const del = e.target.closest('[data-del]') || e.target.closest('[data-del-x]');
    if (del) {
      const chip = del.closest('.chip');
      if (chip) {
        const chipsEl = chip.parentElement; /* remove 后 parentElement 会变 null，先取 */
        const toolsField = chip.closest('[data-tools-field]');
        chip.style.transform = 'scale(0.7)'; chip.style.opacity = '0';
        setTimeout(() => {
          chip.remove();
          afterToolChipRemoved(toolsField);
          onFieldInput({ target: chipsEl });
        }, 140);
      }
      return;
    }
    /* 「从列表选择」→ 打开工具勾选弹窗 */
    const pickBtn = e.target.closest('[data-tool-pick]');
    if (pickBtn) openToolPicker(pickBtn.dataset.toolPick);
    if (e.target.closest('#btn-add-platform')) promptAddPlatform();
  });

  section.addEventListener('click', async (e) => {
    const delBtn = e.target.closest('[data-del-platform]');
    if (delBtn) {
      const key = delBtn.dataset.delPlatform;
      if (await confirmDialog({ title: '删除平台', message: `确定删除平台 <b>${escapeHtml(key)}</b> 的配置吗？`, danger: true, confirmText: '删除' })) {
        delBtn.closest('.platform-card').remove();
        onFieldInput({ target: document.body });
      }
    }
  });

  /* 各「添加」按钮与行内操作全部走 section 级委托：
     renderForm 每次重渲染（重进视图/切回表单模式）都会重建这些按钮与容器，
     直接绑定的监听随节点销毁丢失，会导致重进视图后按钮失效 */
  section.addEventListener('click', (e) => {
    if (e.target.closest('#btn-add-standby')) {
      const box = section.querySelector('#standby-container');
      if (!box) return;
      const item = document.createElement('div');
      item.className = 'sortable-item';
      item.innerHTML = `
        <span class="drag-num"></span>
        <div class="content">
          <select class="select" data-sb="supplier"><option value="">（供应商）</option>${supplierOptions().map((o) => `<option>${escapeHtml(o)}</option>`).join('')}</select>
          <select class="select" data-sb="model"><option value="">（模型）</option></select>
        </div>
        <div class="ops">
          <button class="icon-btn" data-op="up">${icon('up')}</button>
          <button class="icon-btn" data-op="down">${icon('down')}</button>
          <button class="icon-btn del" data-op="del">${icon('trash')}</button>
        </div>`;
      box.appendChild(item);
      renumberStandby();
      return;
    }

    /* 备用模型排序操作 */
    const opBtn = e.target.closest('.sortable-item [data-op]');
    if (opBtn) {
      const item = opBtn.closest('.sortable-item');
      if (opBtn.dataset.op === 'del') { item.remove(); renumberStandby(); }
      if (opBtn.dataset.op === 'up' && item.previousElementSibling) item.previousElementSibling.before(item);
      if (opBtn.dataset.op === 'down' && item.nextElementSibling) item.nextElementSibling.after(item);
      if (opBtn.dataset.op !== 'del') renumberStandby();
      if (opBtn.dataset.op === 'del') toast('已删除该备用模型（尚未保存）', 'info');
      return;
    }

    /* 聊天请求参数：添加行 / 删除行 */
    if (e.target.closest('#btn-add-chatparam')) {
      const box = section.querySelector('#chatparams-container');
      if (!box) return;
      box.querySelector('.kv-empty')?.remove();
      const tmp = document.createElement('div');
      tmp.innerHTML = renderChatParamRow('', undefined);
      box.appendChild(tmp.firstElementChild);
      box.lastElementChild.querySelector('[data-cp="key"]').focus();
      refreshDirty();
      return;
    }
    const cpDel = e.target.closest('[data-cp-del]');
    if (cpDel) {
      cpDel.closest('.kv-row').remove();
      toast('已删除该参数（尚未保存）', 'info');
      refreshDirty();
    }
  });

  /* 聊天请求参数：键名命中已知参数时升级控件 / 未知行类型切换 */
  section.addEventListener('input', (e) => {
    const el = e.target;
    if (!el.matches?.('[data-cp="key"]')) return;
    const row = el.closest('.kv-row');
    if (!row) return;
    const key = el.value.trim();
    /* 已知 ⇄ 未知 切换时才整行重渲染（已输入的值保住），避免每次按键都重建丢焦点 */
    if ((row.dataset.known === '1') !== !!CHAT_PARAM_DEFS[key]) replaceChatParamRow(row, key, readChatRowValue(row));
  });

  section.addEventListener('change', (e) => {
    const el = e.target;
    if (!el.matches?.('[data-cp="type"]')) return;
    const row = el.closest('.kv-row');
    const key = row.querySelector('[data-cp="key"]').value.trim();
    row.querySelector('.kv-value').innerHTML = chatParamValueControl(key, el.value, readChatRowValue(row));
    refreshDirty();
  });

  /* 参数名输入框绑定 themed 建议弹层（attachSuggest 自带去重；
     键名命中已知参数会整行重渲染产生新 input，靠 focusin 补绑） */
  section.addEventListener('focusin', (e) => {
    const el = e.target;
    if (el.matches?.('[data-cp="key"]')) attachSuggest(el, chatKeySuggestProvider(el));
  });
}

function readPlatformCard(card) {
  const conf = {};
  card.querySelectorAll('[data-fkey]').forEach((el) => {
    conf[el.dataset.fkey] = el.type === 'checkbox' ? el.checked : el.value;
  });
  return conf;
}

function renumberStandby() {
  const items = document.querySelectorAll('#standby-container .sortable-item');
  items.forEach((item, i) => {
    item.querySelector('.drag-num').textContent = i + 1;
    item.querySelector('[data-op="up"]').disabled = i === 0;
    item.querySelector('[data-op="down"]').disabled = i === items.length - 1;
  });
}

function promptAddPlatform() {
  openModal({
    title: '添加平台',
    bodyHtml: `<div class="field"><div class="field-label">平台名称（key）</div>
      <input class="input" id="new-platform-key" placeholder="如 napcat2">
      <p class="field-desc">可随意命名，用于区分多个平台实例</p></div>`,
    actions: [
      { label: '取消', class: 'ghost', onClick: ({ close }) => close() },
      {
        label: '添加',
        class: 'primary',
        onClick: ({ close, el }) => {
          const key = el.querySelector('#new-platform-key').value.trim();
          if (!key) return;
          if (!/^[\w-]+$/.test(key)) { toast('名称只能包含字母、数字、下划线和短横线', 'error'); return; }
          const container = document.getElementById('platforms-container');
          const tmp = document.createElement('div');
          tmp.innerHTML = renderPlatformCard(key, { adapter: 'onebot', connection_type: 'WebSocket_client', access_token: '', enabled: true }, container.children.length);
          container.appendChild(tmp.firstElementChild);
          close();
          toast('已添加平台，请填写配置（尚未保存）', 'info');
        },
      },
    ],
  });
}

/* ---------- 变更标记 ---------- */

function onFieldInput(e) {
  const el = e.target;
  if (el.dataset?.path && !el.dataset.path.startsWith('__')) {
    const fieldWrap = el.closest('.field');
    if (fieldWrap) {
      const field = findField(el.dataset.path);
      let cur;
      if (el.dataset.ftype === 'toggle') cur = el.checked;
      else if (el.dataset.ftype === 'number') cur = el.value === '' ? undefined : Number(el.value);
      else if (el.dataset.ftype === 'chips') cur = readChips(el.closest('.chips')).map((x) => (el.dataset.kind === 'int' ? Number(x) : x));
      else cur = el.value;
      const orig = kit.getPath(original, el.dataset.path);
      fieldWrap.classList.toggle('changed', JSON.stringify(orig) !== JSON.stringify(cur) && !(field?.optional && (cur === '' || cur === undefined) && orig === undefined));
    }
  }
  refreshDirty();
}

function updateChangedMarks() {
  document.querySelectorAll('.field[data-field]').forEach((wrap) => {
    const path = wrap.dataset.field;
    const el = wrap.querySelector('[data-path]');
    if (!el) return;
    onFieldInput({ target: el });
  });
}

function refreshDirty() {
  if (!saveBar) return;
  try {
    const payload = buildPayload();
    const dirty = kit.diffObjects(original, payload).length > 0;
    saveBar.setDirty(dirty);
  } catch { /* 忽略中间态 */ }
}

/* ---------- 源码模式 ---------- */

function renderSource(section) {
  const box = section.querySelector('#source-editor');
  box.innerHTML = '';
  let content;
  try {
    content = JSON.stringify(buildPayload(), null, 2);
  } catch {
    content = JSON.stringify(formBase, null, 2);
  }
  editor = createJsonEditor(box, {
    content,
    onChange: () => {
      if (!saveBar) return;
      try {
        const payload = JSON.parse(editor.getContent());
        saveBar.setDirty(kit.diffObjects(original, payload).length > 0);
      } catch {
        saveBar.setDirty(true);
      }
    },
  });
}

/* ---------- 保存 / 回滚 / 下载 ---------- */

function currentPayload() {
  if (mode === 'source') {
    if (!editor || !editor.isValid()) throw new Error('源码存在 JSON 语法错误，请先修正');
    return JSON.parse(editor.getContent());
  }
  return buildPayload();
}

async function save() {
  let payload;
  try {
    payload = currentPayload();
  } catch (e) {
    toast(e.message, 'error');
    return;
  }

  /* 工具预设合法性校验：tool_search 必须搭配非空 deferred（反之亦然） */
  const toolErrors = validateToolPresets(payload);
  if (toolErrors.length) {
    toast(`无法保存：${toolErrors[0]}${toolErrors.length > 1 ? `（还有 ${toolErrors.length - 1} 处工具预设问题）` : ''}`, 'error', 8000);
    return;
  }

  /* 聊天请求参数合法性校验（表单模式下读行；源码模式由 JSON 编辑器保证语法） */
  if (mode === 'form') {
    const cpErrors = validateChatParams();
    if (cpErrors.length) {
      toast(`无法保存：${cpErrors[0]}${cpErrors.length > 1 ? `（还有 ${cpErrors.length - 1} 处参数问题）` : ''}`, 'error', 8000);
      return;
    }
  }

  const diffs = kit.diffObjects(original, payload);
  if (!diffs.length) { toast('当前没有需要保存的更改', 'info'); return; }

  const ok = await kit.showDiffModal(diffs);
  if (!ok) return;

  try {
    await api.post('/config', { content: JSON.stringify(payload, null, 2) });
    original = kit.deepClone(payload);
    formBase = kit.deepClone(payload);
    saveBar.setDirty(false);
    toast('配置已保存，已生成 .bak 备份', 'success');
    await kit.needsRestartFlow('主配置');
  } catch (e) {
    toast(`保存失败：${e.message}`, 'error', 5000);
  }
}

async function rollback() {
  const ok = await confirmDialog({
    title: '回滚配置',
    message: '将把上一次保存时的备份（.bak）写回主配置文件，<b>当前未保存的编辑会丢失</b>。当前内容会转存到 .bak，可再次回滚撤销。',
    danger: true,
    confirmText: '回滚',
  });
  if (!ok) return;
  try {
    await api.post('/config/rollback', { target: 'config' });
    toast('已回滚到备份版本', 'success');
    await load();
  } catch (e) {
    toast(`回滚失败：${e.message}`, 'error', 5000);
  }
}

/* ---------- 初始化 ---------- */

async function load() {
  const [configRes, supplierRes, personaRes] = await Promise.all([
    api.get('/config'),
    api.get('/supplier_config').catch(() => ({ suppliers: [] })),
    api.get('/personas').catch(() => ({ items: [] })),
  ]);
  original = JSON.parse(configRes.content);
  formBase = kit.deepClone(original);
  pathLabel = configRes.path;
  suppliers = supplierRes.suppliers || [];
  personas = personaRes.items || [];
}

async function init(section) {
  if (!original) {
    section.innerHTML = `<div class="card">${'<div class="skeleton skeleton-card"></div>'.repeat(3)}</div>`;
    await load();
  }

  section.innerHTML = `
    <div id="config-savebar"></div>
    <div id="config-form-wrap">
      <div class="config-layout">
        <nav class="config-anchor"></nav>
        <div class="config-sections"></div>
      </div>
    </div>
    <div id="config-source-wrap" class="hidden">
      <div id="source-editor"></div>
    </div>`;

  saveBar = kit.renderSaveBar(section.querySelector('#config-savebar'), {
    pathLabel,
    onModeChange: switchMode,
    onSave: save,
    onRollback: rollback,
    onDownload: () => kit.downloadText('config.json', JSON.stringify(currentPayload(), null, 2)),
    onDiff: async () => {
      try {
        const diffs = kit.diffObjects(original, currentPayload());
        if (!diffs.length) { toast('当前没有更改', 'info'); return; }
        await kit.showDiffModal(diffs);
      } catch (e) { toast(e.message, 'error'); }
    },
  });

  mode = 'form';
  renderForm(section);
  setupSectionObserver(section);
}

function switchMode(next) {
  if (next === mode) return;
  const formWrap = document.getElementById('config-form-wrap');
  const sourceWrap = document.getElementById('config-source-wrap');

  if (next === 'source') {
    renderSource(document.getElementById('view-config'));
    formWrap.classList.add('hidden');
    sourceWrap.classList.remove('hidden');
    mode = 'source';
  } else {
    if (editor && !editor.isValid()) { toast('源码存在语法错误，无法切回表单模式', 'error'); saveBar.setMode('source'); return; }
    if (editor) {
      try { formBase = JSON.parse(editor.getContent()); } catch { /* keep */ }
    }
    sourceWrap.classList.add('hidden');
    formWrap.classList.remove('hidden');
    mode = 'form';
    renderForm(document.getElementById('view-config'));
    setupSectionObserver(document.getElementById('view-config'));
  }
}

function setupSectionObserver(section) {
  if (observer) observer.disconnect();
  const sectionEls = [...section.querySelectorAll('.config-section')];
  observer = new IntersectionObserver(
    (entries) => {
      if (Date.now() < anchorLockUntil) return;
      if (!entries.some((e) => e.isIntersecting)) return;
      /* 取第一个跨越视口 30% 线的分组（短分组如"沙盒"也能正确命中） */
      const line = innerHeight * 0.3;
      for (const s of sectionEls) {
        const r = s.getBoundingClientRect();
        if (r.top <= line && r.bottom > line) {
          setAnchorActive(s.id.replace('cfgsec-', ''));
          break;
        }
      }
    },
    { rootMargin: '0px 0px -70% 0px' }
  );
  sectionEls.forEach((s) => observer.observe(s));
}

function destroy() {
  if (observer) { observer.disconnect(); observer = null; }
}

export const configView = { title: '主配置', init, destroy };
