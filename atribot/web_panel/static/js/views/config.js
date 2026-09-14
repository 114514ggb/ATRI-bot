/* 视图：主配置编辑（表单 + 源码双模式） */

import { api } from '../api.js';
import { icon, toast, escapeHtml, confirmDialog, openModal } from '../ui.js';
import { SCHEMA } from '../config-schema.js';
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

/* ---------- 字段控件渲染 ---------- */

function supplierOptions() {
  return suppliers.map((s) => s.name);
}

function modelOptions(supplierName) {
  const found = suppliers.find((s) => s.name === supplierName);
  return found ? Object.keys(found.models || {}) : [];
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
      </select>`;

    case 'model-select':
      return `<select class="select" data-path="${field.path}" data-ftype="select" data-depends="${field.depends}">
        <option value="">（未设置）</option>
        ${modelOptions(kit.getPath(formBase, field.depends)).map((o) => `<option value="${escapeHtml(o)}" ${o === v ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}
      </select>`;

    case 'persona-select':
      return `<select class="select" data-path="${field.path}" data-ftype="select">
        <option value="none">none（无人设）</option>
        ${personas.map((p) => `<option value="${escapeHtml(p.key)}" ${p.key === v ? 'selected' : ''}>${escapeHtml(p.key)}</option>`).join('')}
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
        </select>
        <select class="select" data-sb="model">
          <option value="">（模型）</option>
          ${modelOptions(m.supplier).map((o) => `<option value="${escapeHtml(o)}" ${o === m.model_name ? 'selected' : ''}>${escapeHtml(o)}</option>`).join('')}
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

function renderToolPresets(presets) {
  const gc = presets?.group_chat || {};
  const gcDef = Array.isArray(gc.default) ? gc.default : [];
  const gcDeferred = Array.isArray(gc.deferred) ? gc.deferred : [];
  const privNull = Array.isArray(presets?.private_chat) ? false : presets?.private_chat === null || presets?.private_chat === undefined;
  const agencyNull = Array.isArray(presets?.agency_Agent) ? false : presets?.agency_Agent === null || presets?.agency_Agent === undefined;

  const chipsStr = (path, values) => renderChips(path, 'str', values);

  return `
    <div class="notice info">${icon('info')}<div>配置了 <code>deferred</code>（待发现工具）就必须把 <code>tool_search</code> 加进 default，否则模型无法发现它们。列表为空代表无工具；设为「全部」代表不限制（不推荐）。</div></div>
    <div class="field-grid">
      <div class="field span-2">
        <div class="field-label">群聊 group_chat · 默认工具</div>
        ${chipsStr('__tools.group_chat.default', gcDef)}
      </div>
      <div class="field span-2">
        <div class="field-label">群聊 group_chat · 待发现工具（deferred）</div>
        ${chipsStr('__tools.group_chat.deferred', gcDeferred)}
        <p class="field-desc">不直接暴露给模型；模型通过 tool_search 搜索后本轮临时启用</p>
      </div>
      <div class="field">
        <div class="toggle-row"><div class="field-label" style="margin:0">私聊 private_chat</div>
          <label class="toggle"><input type="checkbox" data-tools-null="private_chat" ${privNull ? 'checked' : ''}><span class="track"></span><span class="thumb"></span></label></div>
        <p class="field-desc">开关开启 = 全部工具（null）</p>
        <div class="tools-chips" data-tools-for="private_chat">${chipsStr('__tools.private_chat', privNull ? [] : presets?.private_chat || [])}</div>
      </div>
      <div class="field">
        <div class="toggle-row"><div class="field-label" style="margin:0">子代理 agency_Agent</div>
          <label class="toggle"><input type="checkbox" data-tools-null="agency_Agent" ${agencyNull ? 'checked' : ''}><span class="track"></span><span class="thumb"></span></label></div>
        <p class="field-desc">开关开启 = 全部工具（null）</p>
        <div class="tools-chips" data-tools-for="agency_Agent">${chipsStr('__tools.agency_Agent', agencyNull ? [] : presets?.agency_Agent || [])}</div>
      </div>
    </div>`;
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

  /* 工具预设 */
  const tools = {};
  tools.group_chat = {
    default: readChips(document.querySelector('[data-path="__tools.group_chat.default"]') || document.createElement('div')),
    deferred: readChips(document.querySelector('[data-path="__tools.group_chat.deferred"]') || document.createElement('div')),
  };
  const privNullEl = document.querySelector('[data-tools-null="private_chat"]');
  tools.private_chat = privNullEl?.checked ? null : readChips(document.querySelector('[data-path="__tools.private_chat"]') || document.createElement('div'));
  const agencyNullEl = document.querySelector('[data-tools-null="agency_Agent"]');
  tools.agency_Agent = agencyNullEl?.checked ? null : readChips(document.querySelector('[data-path="__tools.agency_Agent"]') || document.createElement('div'));
  data.tool_presets = tools;

  return data;
}

function findField(path) {
  for (const section of SCHEMA) {
    for (const f of section.fields || []) if (f.path === path) return f;
  }
  return null;
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
          .join('')}`;
      });
    }
    /* 备用模型卡片内的供应商联动 */
    if (el.matches('[data-sb="supplier"]')) {
      const item = el.closest('.sortable-item');
      const modelSel = item.querySelector('[data-sb="model"]');
      const current = modelSel.value;
      modelSel.innerHTML = `<option value="">（模型）</option>${modelOptions(el.value)
        .map((o) => `<option value="${escapeHtml(o)}" ${o === current ? 'selected' : ''}>${escapeHtml(o)}</option>`)
        .join('')}`;
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
    /* 工具「全部」开关 → 禁用对应 chips */
    if (el.matches('[data-tools-null]')) {
      const wrap = document.querySelector(`.tools-chips[data-tools-for="${el.dataset.toolsNull}"]`);
      if (wrap) wrap.style.opacity = el.checked ? '0.4' : '1';
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
      if (chip) { chip.style.transform = 'scale(0.7)'; chip.style.opacity = '0'; setTimeout(() => { chip.remove(); onFieldInput({ target: chip.parentElement }); }, 140); }
    }
  });

  /* 添加/删除平台 */
  const addPlatform = section.querySelector('#btn-add-platform');
  if (addPlatform) addPlatform.addEventListener('click', promptAddPlatform);

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

  /* 备用模型排序操作 */
  const standbyBox = section.querySelector('#standby-container');
  if (standbyBox) {
    section.querySelector('#btn-add-standby')?.addEventListener('click', () => {
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
      standbyBox.appendChild(item);
      renumberStandby();
    });

    standbyBox.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-op]');
      if (!btn) return;
      const item = btn.closest('.sortable-item');
      if (btn.dataset.op === 'del') { item.remove(); renumberStandby(); }
      if (btn.dataset.op === 'up' && item.previousElementSibling) item.previousElementSibling.before(item);
      if (btn.dataset.op === 'down' && item.nextElementSibling) item.nextElementSibling.after(item);
      if (btn.dataset.op !== 'del') renumberStandby();
      if (btn.dataset.op === 'del') toast('已删除该备用模型（尚未保存）', 'info');
    });
  }
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
