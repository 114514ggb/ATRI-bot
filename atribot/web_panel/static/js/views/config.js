/* 视图：主配置编辑（表单 + 源码双模式） */

import { api } from '../api.js';
import { icon, toast, escapeHtml, confirmDialog, openModal, attachSuggest, helpFold } from '../ui.js';
import { SCHEMA, CHAT_PARAM_DEFS, CHAT_PARAM_VALUE_TYPES } from '../config-schema.js';
import { TOOL_SEARCH_BRIEF, TOOL_SEARCH_RULES, TOOL_SEARCH_HELP_LABEL } from '../copy.js';
import { createJsonEditor } from '../components/json-editor.js';
import * as kit from '../components/editor-kit.js';
import {
  bindChipInteractions,
  readChips,
  renderChips,
  renderToolPresetModule,
  setPresetChangeHandler,
  validatePresetPairing,
} from '../components/tool-preset-editor.js';

let original = null; // 服务器当前配置（diff 基准）
let formBase = null; // 表单渲染基础（源码→表单时更新）
let pathLabel = '';
let suppliers = []; // [{name, models:{...}}]
let personas = [];
let editor = null;
let saveBar = null;
let mode = 'form';
let observer = null;
/* 工具预设清单（config.json 中 tool_presets 的键）：
   首次读取配置时确定，切回表单模式/回滚重载时重读，避免每轮渲染都重新枚举 */
let presetKeysCache = [];

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

/* ---------- 工具预设（清单与取值均由 config.json 决定，不硬编码预设名） ---------- */

/* tool_presets 必须是对象；写成数组/字符串等非法形态时按空处理（后端保存时会拦截） */
function presetSourceOf() {
  const raw = formBase?.tool_presets;
  return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {};
}

/* 重算预设清单缓存：配置解析完成 / 源码模式切回表单 / 保存后调用 */
function refreshPresetKeys() {
  presetKeysCache = Object.keys(presetSourceOf());
}

/* 从 DOM 读回单个预设模块的取值（与 renderToolPresetModule 的形态判定保持一致） */
function readPresetModule(key) {
  const wrap = document.querySelector(`[data-tools-field="${key}"]`);
  if (!wrap) return undefined; /* 未渲染：交给 buildPayload 保留原值 */
  const restrict = wrap.querySelector(`[data-tools-restrict="${key}"]`);
  if (restrict && !restrict.checked) return null; /* 限制关闭 = null = 全部工具 */
  const defEl = wrap.querySelector(`[data-path="__tools.${key}.default"]`);
  if (!defEl) return readChips(wrap.querySelector(`[data-path="__tools.${key}"]`)); /* 单列表白名单 */

  /* deferred 为空时双列表等价于白名单，统一回写成列表，避免产生歧义配置 */
  const deferred = readChips(wrap.querySelector(`[data-path="__tools.${key}.deferred"]`));
  const def = readChips(defEl);
  return deferred.length ? { default: def, deferred } : def;
}

function renderToolPresets() {
  const presets = presetSourceOf();
  if (!presetKeysCache.length) {
    return `<div class="notice info">${icon('info')}<div>尚无工具预设：可在源码模式向 <code>tool_presets</code> 添加预设名，保存后切回表单模式编辑。</div></div>`;
  }
  return `
    <div class="notice info">${icon('info')}<div>预设清单取自 <code>tool_presets</code>（新增后需切回表单模式加载）。${TOOL_SEARCH_BRIEF}${helpFold(TOOL_SEARCH_HELP_LABEL, TOOL_SEARCH_RULES)}</div></div>
    <div class="field-grid">
      ${presetKeysCache.map((key) => renderToolPresetModule(key, presets[key])).join('')}
    </div>`;
}

/* ---------- DOM 读取 → payload ---------- */

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

  /* 工具预设：以配置中既有预设为基底增量覆盖（未渲染的预设原样保留，避免表单模式误删） */
  const tools = { ...presetSourceOf() };
  for (const key of presetKeysCache) {
    const value = readPresetModule(key);
    if (value !== undefined) tools[key] = value; /* undefined = 该预设未渲染，保留既有值 */
  }
  if (Object.keys(tools).length) data.tool_presets = tools;
  else delete data.tool_presets;

  return data;
}

function findField(path) {
  for (const section of SCHEMA) {
    for (const f of section.fields || []) if (f.path === path) return f;
  }
  return null;
}

/* 工具预设保存校验：tool_search 与 deferred 必须成对出现，缺一个就没有意义
   （预设名来自配置，逐项用 validatePresetPairing 校验） */
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
    else if (s.type === 'tool-presets') inner = renderToolPresets();
    else {
      inner = `<div class="field-grid">${s.fields.map((f) => fieldHtml(f, kit.getPath(formBase, f.path))).join('')}</div>`;
    }
    return `<div class="config-section" id="cfgsec-${s.id}" style="animation-delay:${Math.min(i * 50, 400)}ms">
      <h3>${icon(s.icon)} ${escapeHtml(s.label)}</h3>
      ${s.desc ? `<p class="section-desc">${s.desc}</p>` : ''}
      ${s.help ? helpFold(TOOL_SEARCH_HELP_LABEL, s.help) : ''}
      ${inner}
    </div>`;
  }).join('');

  bindForm(section);
  updateChangedMarks();
}

let anchorLockUntil = 0; /* 点击锚点后的平滑滚动期间，不让 IntersectionObserver 抢走高亮 */
let anchorOffsetObserver = null; /* 观察保存栏高度，驱动 --cfg-anchor-top */

function setAnchorActive(id) {
  document.querySelectorAll('.config-anchor a').forEach((l) => l.classList.toggle('active', l.dataset.target === id));
}

/* 保存栏是 sticky 的（top:10px + 自身高度），会遮住左栏顶部与锚点目标区块的标题。
   --cfg-anchor-top = 保存栏高度 + 22（保存栏自身 top 10 + 间距 12），喂给左栏 sticky top、
   左栏最大高度与 .config-section 的 scroll-margin-top；窄屏保存栏换行时高度会变，靠 ResizeObserver 跟随. */
function setupAnchorOffset(section) {
  const bar = section.querySelector('#config-savebar');
  if (!bar) return;
  const apply = () => {
    const h = Math.round(bar.getBoundingClientRect().height);
    if (h > 0) section.style.setProperty('--cfg-anchor-top', `${h + 22}px`);
  };
  apply();
  anchorOffsetObserver?.disconnect();
  anchorOffsetObserver = new ResizeObserver(apply);
  anchorOffsetObserver.observe(bar);
}

/* 锚点跳转：sticky 偏移的参考系是滚动容器的内容区，scrollIntoView/scroll-margin 的参考系是容器顶部
   （不含容器 padding），因此这里手算滚动量并补上 padding-top，两种坐标系才对齐 */
function scrollToSection(section, target) {
  const scroller = section.closest('.view-scroll');
  const padTop = parseFloat(getComputedStyle(scroller).paddingTop) || 0;
  const barH = Math.round(section.querySelector('#config-savebar').getBoundingClientRect().height);
  const offset = padTop + (barH > 0 ? barH + 22 : 0);
  const relTop = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
  scroller.scrollTo({ top: Math.max(0, scroller.scrollTop + relTop - offset), behavior: 'smooth' });
}

function bindForm(section) {
  /* 锚点点击：先高亮再滚动（锚点元素每次渲染都是新的，需要重复绑定） */
  section.querySelectorAll('.config-anchor a').forEach((a) => {
    a.addEventListener('click', () => {
      anchorLockUntil = Date.now() + 900;
      setAnchorActive(a.dataset.target);
      /* 关掉入场动画：fade-slide-in 起始带 translateY(10px)，动画中途测量会让落点偏下 */
      section.querySelector('.config-sections')?.classList.add('no-anim');
      const target = document.getElementById(`cfgsec-${a.dataset.target}`);
      if (target) scrollToSection(section, target);
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
  });

  /* chips 回车添加 / chip 删除 / 「限制工具」开关 / 「从列表选择」统一由共享组件绑定，
     保证配置页与聊天页工具弹窗行为一致（重复调用幂等） */
  bindChipInteractions(section);

  section.addEventListener('click', (e) => {
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
  const toolErrors = Object.entries(payload?.tool_presets ?? {}).flatMap(([key, value]) => validatePresetPairing(key, value));
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
    refreshPresetKeys(); /* 清单随保存后的配置同步（源码模式增删的预设切回表单时即可见） */
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
    message: '将把上一次保存的备份（.bak）写回主配置文件，<b>未保存的编辑会丢失</b>。',
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
  refreshPresetKeys(); /* 预设清单随配置一起（重新）读取 */
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
  /* 工具预设编辑（chips 增删 / 模式切换 / 限制开关）后刷新保存栏 dirty 标记 */
  setPresetChangeHandler(refreshDirty);
  renderForm(section);
  setupAnchorOffset(section);
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
    refreshPresetKeys(); /* 源码模式可能新增/删除预设，切回表单时重读清单 */
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
  if (anchorOffsetObserver) { anchorOffsetObserver.disconnect(); anchorOffsetObserver = null; }
}

export const configView = { title: '主配置', init, destroy };
