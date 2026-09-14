/* 视图：模型供应商配置（supplier_config.json，表单 + 源码双模式） */

import { api } from '../api.js';
import { icon, toast, escapeHtml, confirmDialog } from '../ui.js';
import { MODEL_SENSES } from '../config-schema.js';
import { createJsonEditor } from '../components/json-editor.js';
import * as kit from '../components/editor-kit.js';

let original = null; // 服务器上的内容（diff 基准）
let formBase = null; // 表单渲染基础（源码→表单时更新）
let pathLabel = '';
let editor = null;
let saveBar = null;
let mode = 'form';

/* ---------- 表单渲染 ---------- */

function renderSupplierCard(supplier, idx) {
  const isPool = Array.isArray(supplier.api_key);
  const pool = isPool ? supplier.api_key : [];
  const singleKey = isPool ? '' : supplier.api_key || '';

  const models = Object.entries(supplier.models || {});
  const modelRows = models
    .map(([name, senses], mi) => `
      <tr>
        <td><input class="input model-name-input" data-sup="model-name" data-mi="${mi}" value="${escapeHtml(name)}"></td>
        ${MODEL_SENSES.map(
          (s) => `<td style="text-align:center">
            <label class="check-row" style="justify-content:center">
              <input type="checkbox" data-sup="sense" data-mi="${mi}" data-sense="${s.key}" ${senses?.[s.key] ? 'checked' : ''}>
            </label></td>`
        ).join('')}
        <td><button class="icon-btn del" data-sup="del-model" data-mi="${mi}">${icon('trash')}</button></td>
      </tr>`)
    .join('');

  return `
    <div class="config-section supplier-card" data-sp-idx="${idx}" style="animation-delay:${Math.min(idx * 60, 300)}ms">
      <h3 style="justify-content:space-between">
        <span style="display:flex;align-items:center;gap:9px">${icon('cloud')} <span class="sp-name" data-sup="name" contenteditable="true" spellcheck="false">${escapeHtml(supplier.name || '未命名供应商')}</span></span>
        <span style="display:flex;gap:4px">
          <button class="icon-btn" data-sup="copy" title="复制该供应商">${icon('copy')}</button>
          <button class="icon-btn del" data-sup="del" title="删除该供应商">${icon('trash')}</button>
        </span>
      </h3>
      <p class="section-desc">点击标题可直接重命名</p>
      <div class="field-grid">
        <div class="field span-2">
          <div class="field-label">接口地址 base_url</div>
          <input class="input mono" data-sup="base_url" value="${escapeHtml(supplier.base_url || '')}" placeholder="https://api.example.com/v1/chat/completions">
          <p class="field-desc">只接受 OpenAI 兼容地址。聊天模型一般要以 /v1/chat/completions 结尾；嵌入模型通常不需要</p>
        </div>
        <div class="field span-2">
          <div class="field-label">API 密钥</div>
          <div class="seg" style="margin-bottom:10px">
            <button data-keymode="single" class="${isPool ? '' : 'active'}">单个密钥</button>
            <button data-keymode="pool" class="${isPool ? 'active' : ''}">号池轮询</button>
          </div>
          ${isPool
            ? `<div class="chips" data-sup="apikey-pool">${pool.map((k, i) => `<span class="chip">${escapeHtml(k)}<button data-del>${icon('x')}</button></span>`).join('')}<input placeholder="输入 key 后回车添加"></div>`
            : `<input class="input mono" type="password" data-sup="apikey" value="${escapeHtml(singleKey)}" autocomplete="new-password">`}
          <p class="field-desc">号池模式下多个密钥按顺序轮流使用</p>
        </div>
      </div>

      <div class="field">
        <div class="field-label">模型列表 <span class="muted small">（勾选模型支持的输入能力，可不选）</span></div>
        <div class="table-wrap" style="box-shadow:none">
          <div class="table-scroll">
            <table class="models-table">
              <thead><tr><th>模型名称</th>${MODEL_SENSES.map((s) => `<th style="text-align:center">${s.label}</th>`).join('')}<th></th></tr></thead>
              <tbody data-sup="models">
                ${modelRows || `<tr class="empty-row"><td colspan="6">暂无模型</td></tr>`}
              </tbody>
            </table>
          </div>
        </div>
        <div style="margin-top:10px"><button class="btn sm" data-sup="add-model">${icon('plus')} 添加模型</button></div>
      </div>
    </div>`;
}

function renderForm(section) {
  const list = section.querySelector('#supplier-sections');
  const cards = (formBase.api || []).map((s, i) => renderSupplierCard(s, i)).join('');
  list.innerHTML = cards + `<button class="btn" id="btn-add-supplier">${icon('plus')} 添加供应商</button>`;
  bindForm(section);
}

function bindForm(section) {
  /* key 模式切换 */
  section.addEventListener('click', (e) => {
    const modeBtn = e.target.closest('[data-keymode]');
    if (modeBtn) {
      const card = modeBtn.closest('.supplier-card');
      const seg = modeBtn.parentElement;
      seg.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
      modeBtn.classList.add('active');
      const usePool = modeBtn.dataset.keymode === 'pool';
      const keyField = card.querySelector('[data-sup="apikey"], [data-sup="apikey-pool"]');
      if (usePool && keyField?.dataset.sup === 'apikey') {
        const chips = document.createElement('div');
        chips.className = 'chips';
        chips.dataset.sup = 'apikey-pool';
        if (keyField.value) chips.innerHTML = `<span class="chip">${escapeHtml(keyField.value)}<button data-del>${icon('x')}</button></span>`;
        chips.innerHTML += '<input placeholder="输入 key 后回车添加">';
        keyField.replaceWith(chips);
      } else if (!usePool && keyField?.dataset.sup === 'apikey-pool') {
        const input = document.createElement('input');
        input.className = 'input mono';
        input.type = 'password';
        input.dataset.sup = 'apikey';
        input.autocomplete = 'new-password';
        const first = keyField.querySelector('.chip');
        if (first) input.value = first.textContent.trim();
        keyField.replaceWith(input);
      }
      refreshDirty();
      return;
    }

    const delChip = e.target.closest('.chip [data-del]');
    if (delChip) {
      const chip = delChip.closest('.chip');
      chip.remove();
      refreshDirty();
      return;
    }

    const delModel = e.target.closest('[data-sup="del-model"]');
    if (delModel) {
      delModel.closest('tr').remove();
      renumberModels(section);
      refreshDirty();
      return;
    }

    const addModel = e.target.closest('[data-sup="add-model"]');
    if (addModel) {
      const tbody = addModel.closest('.supplier-card').querySelector('[data-sup="models"]');
      tbody.querySelector('.empty-row')?.remove();
      const tr = document.createElement('tr');
      tr.innerHTML = `<td><input class="input model-name-input" data-sup="model-name" data-mi="new"></td>
        ${MODEL_SENSES.map((s) => `<td style="text-align:center"><label class="check-row" style="justify-content:center"><input type="checkbox" data-sup="sense" data-mi="new" data-sense="${s.key}"></label></td>`).join('')}
        <td><button class="icon-btn del" data-sup="del-model">${icon('trash')}</button></td>`;
      tbody.appendChild(tr);
      tr.querySelector('input').focus();
      renumberModels(section);
      refreshDirty();
      return;
    }

    const copyBtn = e.target.closest('[data-sup="copy"]');
    if (copyBtn) {
      const card = copyBtn.closest('.supplier-card');
      const data = readCard(card);
      data.name = (data.name || 'copy') + '-copy';
      const tmp = document.createElement('div');
      tmp.innerHTML = renderSupplierCard(data, document.querySelectorAll('.supplier-card').length);
      document.getElementById('btn-add-supplier').before(tmp.firstElementChild);
      toast('已复制供应商（尚未保存）', 'info');
      refreshDirty();
      return;
    }

    const delBtn = e.target.closest('[data-sup="del"]');
    if (delBtn) {
      const card = delBtn.closest('.supplier-card');
      const name = card.querySelector('[data-sup="name"]').textContent.trim();
      confirmDialog({ title: '删除供应商', message: `确定删除供应商 <b>${escapeHtml(name)}</b> 吗？`, danger: true, confirmText: '删除' }).then((ok) => {
        if (ok) { card.style.opacity = '0'; card.style.transform = 'scale(0.97)'; setTimeout(() => card.remove(), 180); refreshDirty(); }
      });
      return;
    }

    if (e.target.closest('#btn-add-supplier')) {
      const tmp = document.createElement('div');
      tmp.innerHTML = renderSupplierCard({ name: '', base_url: '', api_key: '', models: {} }, document.querySelectorAll('.supplier-card').length);
      document.getElementById('btn-add-supplier').before(tmp.firstElementChild);
      tmp.firstElementChild.scrollIntoView({ behavior: 'smooth', block: 'center' });
      refreshDirty();
    }
  });

  /* chips 回车添加 key */
  section.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.matches('[data-sup="apikey-pool"] input')) {
      e.preventDefault();
      const val = e.target.value.trim();
      if (!val) return;
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.innerHTML = `${escapeHtml(val)}<button data-del>${icon('x')}</button>`;
      e.target.closest('.chips').insertBefore(chip, e.target);
      e.target.value = '';
      refreshDirty();
    }
  });

  section.addEventListener('input', refreshDirty);
}

function renumberModels(section) {
  section.querySelectorAll('[data-sup="models"]').forEach((tbody) => {
    tbody.querySelectorAll('tr').forEach((tr, i) => {
      tr.querySelectorAll('[data-mi]').forEach((el) => { el.dataset.mi = i; });
    });
  });
}

/* ---------- DOM → payload ---------- */

function readCard(card) {
  const models = {};
  card.querySelectorAll('[data-sup="models"] tr').forEach((tr) => {
    const nameInput = tr.querySelector('[data-sup="model-name"]');
    const name = nameInput?.value.trim();
    if (!name) return;
    const senses = {};
    tr.querySelectorAll('[data-sup="sense"]').forEach((c) => { senses[c.dataset.sense] = c.checked; });
    models[name] = senses;
  });

  const poolEl = card.querySelector('[data-sup="apikey-pool"]');
  const singleEl = card.querySelector('[data-sup="apikey"]');
  const api_key = poolEl
    ? Array.from(poolEl.querySelectorAll('.chip')).map((c) => c.textContent.trim())
    : singleEl?.value || '';

  return {
    name: card.querySelector('[data-sup="name"]').textContent.trim(),
    base_url: card.querySelector('[data-sup="base_url"]').value.trim(),
    api_key,
    models,
  };
}

function buildPayload() {
  return { api: Array.from(document.querySelectorAll('.supplier-card')).map((c) => readCard(c)) };
}

function refreshDirty() {
  if (!saveBar) return;
  try {
    saveBar.setDirty(kit.diffObjects(original, buildPayload()).length > 0);
  } catch { /* 忽略 */ }
}

/* ---------- 源码模式 / 保存 ---------- */

function renderSource(section) {
  const box = section.querySelector('#source-editor');
  box.innerHTML = '';
  let content;
  try {
    content = JSON.stringify(buildPayload(), null, 2);
  } catch {
    content = JSON.stringify(original, null, 2);
  }
  editor = createJsonEditor(box, {
    content,
    onChange: () => {
      if (!saveBar) return;
      try { saveBar.setDirty(kit.diffObjects(original, JSON.parse(editor.getContent())).length > 0); }
      catch { saveBar.setDirty(true); }
    },
  });
}

function currentPayload() {
  if (mode === 'source') {
    if (!editor || !editor.isValid()) throw new Error('源码存在 JSON 语法错误，请先修正');
    return JSON.parse(editor.getContent());
  }
  return buildPayload();
}

async function save() {
  let payload;
  try { payload = currentPayload(); }
  catch (e) { toast(e.message, 'error'); return; }

  if (payload.api.some((s) => !s.name || !s.base_url || !s.api_key || (Array.isArray(s.api_key) && !s.api_key.length))) {
    toast('存在供应商缺少 name / base_url / api_key，请补全后再保存', 'error', 4500);
    return;
  }

  const diffs = kit.diffObjects(original, payload);
  if (!diffs.length) { toast('当前没有需要保存的更改', 'info'); return; }
  if (!(await kit.showDiffModal(diffs))) return;

  try {
    await api.post('/supplier_config', { content: JSON.stringify(payload, null, 2) });
    original = kit.deepClone(payload);
    formBase = kit.deepClone(payload);
    saveBar.setDirty(false);
    toast('供应商配置已保存，已生成 .bak 备份', 'success');
    await kit.needsRestartFlow('供应商配置');
  } catch (e) {
    toast(`保存失败：${e.message}`, 'error', 5000);
  }
}

/* ---------- 初始化 ---------- */

async function load() {
  const res = await api.get('/supplier_config');
  original = res.valid ? JSON.parse(res.content) : { api: [] };
  if (!Array.isArray(original.api)) original = { api: [] };
  formBase = kit.deepClone(original);
  pathLabel = res.path;
}

async function init(section) {
  if (!original) {
    section.innerHTML = `<div class="card">${'<div class="skeleton skeleton-card"></div>'.repeat(2)}</div>`;
    await load();
  }

  section.innerHTML = `
    <div id="supplier-savebar"></div>
    <div id="supplier-form-wrap"><div class="config-sections" id="supplier-sections"></div></div>
    <div id="supplier-source-wrap" class="hidden"><div id="source-editor"></div></div>`;

  saveBar = kit.renderSaveBar(section.querySelector('#supplier-savebar'), {
    pathLabel,
    onModeChange: switchMode,
    onSave: save,
    onDownload: () => kit.downloadText('supplier_config.json', JSON.stringify(currentPayload(), null, 2)),
    onRollback: async () => {
      const ok = await confirmDialog({ title: '回滚供应商配置', message: '将把备份（.bak）写回供应商配置文件，当前未保存的编辑会丢失。', danger: true, confirmText: '回滚' });
      if (!ok) return;
      try {
        await api.post('/config/rollback', { target: 'supplier' });
        toast('已回滚到备份版本', 'success');
        original = null;
        mode = 'form';
        await load();
        renderForm(section);
      } catch (e) { toast(`回滚失败：${e.message}`, 'error', 5000); }
    },
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
}

function switchMode(next) {
  if (next === mode) return;
  const formWrap = document.getElementById('supplier-form-wrap');
  const sourceWrap = document.getElementById('supplier-source-wrap');
  const section = document.getElementById('view-supplier');

  if (next === 'source') {
    renderSource(section);
    formWrap.classList.add('hidden');
    sourceWrap.classList.remove('hidden');
    mode = 'source';
  } else {
    if (editor && !editor.isValid()) { toast('源码存在语法错误，无法切回表单模式', 'error'); saveBar.setMode('source'); return; }
    if (editor) {
      try {
        const parsed = JSON.parse(editor.getContent());
        if (parsed && Array.isArray(parsed.api)) formBase = parsed;
      } catch { /* 保持现有表单 */ }
    }
    sourceWrap.classList.add('hidden');
    formWrap.classList.remove('hidden');
    mode = 'form';
    renderForm(section);
  }
}

export const supplierView = { title: '模型供应商', init };
