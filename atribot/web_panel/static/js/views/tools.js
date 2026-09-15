/* 视图：LLM 工具（内部函数工具 + MCP 工具总览与测试） */

import { api } from '../api.js';
import { icon, toast, openModal, escapeHtml, debounce } from '../ui.js';

const state = { search: '', source: 'all', testableOnly: false };
let toolsData = [];

async function init(section) {
  section.innerHTML = `<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>`;

  let data;
  try {
    data = await api.get('/tools');
  } catch (e) {
    section.innerHTML = `<div class="notice danger">${icon('alert')}<div>工具列表加载失败：${escapeHtml(e.message)}</div></div>`;
    return;
  }

  if (!data.available) {
    section.innerHTML = `<div class="notice info">${icon('info')}<div>工具系统不可用：bot 未启动或 ToolCalls 服务尚未注册。</div></div>`;
    return;
  }

  toolsData = data.tools;
  const localCount = data.tools.filter((t) => t.source === 'local').length;
  const mcpCount = data.tools.length - localCount;
  const testableCount = data.tools.filter((t) => t.testable).length;

  section.innerHTML = `
    <div class="tools-stats">
      <div class="stat-card"><span class="stat-num">${data.tools.length}</span><span class="stat-label">全部工具</span></div>
      <div class="stat-card"><span class="stat-num purple">${localCount}</span><span class="stat-label">内部函数工具</span></div>
      <div class="stat-card"><span class="stat-num teal">${mcpCount}</span><span class="stat-label">MCP 工具</span></div>
      <div class="stat-card"><span class="stat-num green">${testableCount}</span><span class="stat-label">可在面板测试</span></div>
    </div>
    <div class="filter-bar">
      <input class="input" id="tools-search" placeholder="搜索工具名、描述或 MCP 服务…" style="width:280px">
      <select class="select" id="tools-source">
        <option value="all">全部来源 (${data.tools.length})</option>
        <option value="local">内部函数工具 (${localCount})</option>
        ${(data.mcp_servers || []).map((s) => `<option value="mcp:${escapeHtml(s.name)}">MCP · ${escapeHtml(s.name)} (${s.tool_count})</option>`).join('')}
      </select>
      <label class="toggle-row small"><label class="toggle"><input type="checkbox" id="tools-testable-only"><span class="track"></span><span class="thumb"></span></label>仅看可测试</label>
      <span class="spacer"></span>
      <span class="muted small" id="tools-count"></span>
    </div>
    <div id="tools-groups"></div>`;

  const render = () => {
    const q = state.search.toLowerCase();
    const list = toolsData.filter((t) => {
      if (state.testableOnly && !t.testable) return false;
      if (state.source === 'local' && t.source !== 'local') return false;
      if (state.source.startsWith('mcp:') && t.mcp_server !== state.source.slice(4)) return false;
      if (!q) return true;
      const hay = [t.name, t.description, t.source_detail, t.mcp_server].filter(Boolean).join(' ').toLowerCase();
      return hay.includes(q);
    });

    section.querySelector('#tools-count').textContent = `${list.length} / ${toolsData.length} 个工具`;

    const groups = [];
    const locals = list.filter((t) => t.source === 'local');
    if (locals.length) groups.push({ title: '内部函数工具', count: locals.length, tools: locals });
    for (const t of list) {
      if (t.source !== 'mcp') continue;
      const name = t.mcp_server || '未知服务';
      let g = groups.find((x) => x.server === name);
      if (!g) { g = { title: `MCP 服务 · ${name}`, server: name, count: 0, tools: [] }; groups.push(g); }
      g.tools.push(t);
      g.count++;
    }
    const wrap = section.querySelector('#tools-groups');
    wrap.innerHTML = groups.length
      ? groups.map(groupHtml).join('')
      : '<div class="card"><p class="muted">没有匹配的工具。</p></div>';
    wrap.querySelectorAll('[data-detail]').forEach((el) =>
      el.addEventListener('click', () => {
        const tool = toolsData.find((t) => t.name === el.dataset.detail);
        if (tool) openToolModal(tool);
      }));
    wrap.querySelectorAll('[data-test]').forEach((el) =>
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const tool = toolsData.find((t) => t.name === el.dataset.test);
        if (tool) openToolModal(tool, true);
      }));
  };

  const searchInput = section.querySelector('#tools-search');
  searchInput.value = state.search;
  searchInput.addEventListener('input', debounce(() => {
    state.search = searchInput.value.trim();
    render();
  }, 200));

  const sourceSelect = section.querySelector('#tools-source');
  sourceSelect.value = state.source;
  sourceSelect.addEventListener('change', () => { state.source = sourceSelect.value; render(); });

  const testableToggle = section.querySelector('#tools-testable-only');
  testableToggle.checked = state.testableOnly;
  testableToggle.addEventListener('change', () => { state.testableOnly = testableToggle.checked; render(); });

  render();
}

/* ---------- 列表渲染 ---------- */

function scopeBadges(t) {
  const out = [];
  out.push(`<span class="badge gray">${t.chat_scope === 'group' ? '群聊' : t.chat_scope === 'private' ? '私聊' : '通用'}</span>`);
  if (t.background) out.push('<span class="badge blue">后台</span>');
  if (t.concurrent) out.push('<span class="badge blue">可并发</span>');
  if (Object.values(t.presets || {}).includes('deferred')) out.push('<span class="badge orange">待发现</span>');
  if (!t.active) out.push('<span class="badge red">已停用</span>');
  return out.join('');
}

function sourceBadges(t) {
  if (t.source === 'mcp') {
    return `<span class="badge teal">MCP</span><span class="badge gray">${escapeHtml(t.mcp_server || '未知服务')}</span>`;
  }
  return '<span class="badge purple">内部工具</span>';
}

function groupHtml(g) {
  const rows = g.tools.map((t) => `
    <tr data-detail="${escapeHtml(t.name)}" class="tool-row">
      <td class="mono">${escapeHtml(t.name)}</td>
      <td>${sourceBadges(t)}</td>
      <td>${scopeBadges(t)}</td>
      <td class="tool-desc-cell" title="${escapeHtml(t.description || '')}">${escapeHtml(t.description || '')}</td>
      <td class="tool-actions">
        ${t.testable
          ? `<button class="btn sm primary" data-test="${escapeHtml(t.name)}">测试</button>`
          : '<span class="muted small">不可测试</span>'}
      </td>
    </tr>`).join('');
  return `
    <div class="tools-group">
      <div class="tools-group-head">
        ${g.server ? icon('plug') : icon('terminal')}
        <span>${escapeHtml(g.title)}</span>
        <span class="badge gray">${g.count}</span>
      </div>
      <div class="card table-wrap">
        <table class="tbl">
          <thead><tr><th style="width:200px">工具名</th><th style="width:180px">来源</th><th style="width:220px">属性</th><th>描述</th><th style="width:100px">操作</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

/* ---------- 详情 / 测试弹窗 ---------- */

function paramTypeLabel(schema) {
  const items = schema.items && schema.items.type ? `<${schema.items.type}>` : '';
  return `${schema.type || 'string'}${items}${Array.isArray(schema.enum) ? ' (枚举)' : ''}`;
}

function paramsTableHtml(t) {
  const props = (t.parameters && t.parameters.properties) || {};
  const names = Object.keys(props);
  if (!names.length) return '<p class="muted small">该工具没有参数。</p>';
  const rows = names.map((n) => {
    const p = props[n] || {};
    const def = p.default !== undefined ? JSON.stringify(p.default) : '';
    const desc = [p.description, Array.isArray(p.enum) ? `可选: ${p.enum.join(' / ')}` : ''].filter(Boolean).join('。');
    return `<tr><td class="mono">${escapeHtml(n)}</td><td>${escapeHtml(paramTypeLabel(p))}</td><td class="mono">${escapeHtml(def)}</td><td>${escapeHtml(desc)}</td></tr>`;
  }).join('');
  return `<div class="table-wrap"><table class="tbl">
    <thead><tr><th>参数名</th><th>类型</th><th>默认值</th><th>说明</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function fieldHtml(name, schema) {
  const type = schema.type || 'string';
  const desc = schema.description || '';
  const def = schema.default;
  if (Array.isArray(schema.enum)) {
    const opts = ['<option value="">（默认）</option>', ...schema.enum.map((v) =>
      `<option value="${escapeHtml(String(v))}"${String(v) === String(def) ? ' selected' : ''}>${escapeHtml(String(v))}</option>`)].join('');
    return `<select class="input" data-param="${escapeHtml(name)}" data-type="enum">${opts}</select>`;
  }
  if (type === 'boolean') {
    return `<select class="input" data-param="${escapeHtml(name)}" data-type="boolean">
      <option value="">（默认）</option>
      <option value="true"${def === true ? ' selected' : ''}>true</option>
      <option value="false"${def === false ? ' selected' : ''}>false</option>
    </select>`;
  }
  if (type === 'integer' || type === 'number') {
    return `<input class="input" data-param="${escapeHtml(name)}" data-type="number" type="number" step="any"
      value="${def !== undefined ? escapeHtml(String(def)) : ''}" placeholder="${escapeHtml(desc)}">`;
  }
  if (type === 'array' || type === 'object') {
    const prefill = def !== undefined ? JSON.stringify(def) : '';
    return `<textarea class="input tool-json-field" data-param="${escapeHtml(name)}" data-type="${type}" rows="2"
      placeholder="${type === 'array' ? 'JSON 数组，或每行一项' : 'JSON 对象'}">${escapeHtml(prefill)}</textarea>`;
  }
  return `<input class="input" data-param="${escapeHtml(name)}" data-type="string"
    value="${def !== undefined ? escapeHtml(String(def)) : ''}" placeholder="${escapeHtml(desc)}">`;
}

function collectArgs(root) {
  const args = {};
  for (const el of root.querySelectorAll('[data-param]')) {
    const name = el.dataset.param;
    const type = el.dataset.type;
    const v = el.value;
    if (!v.trim()) continue;
    if (type === 'number') {
      const n = Number(v);
      if (Number.isNaN(n)) throw new Error(`参数 ${name} 不是合法数字`);
      args[name] = n;
    } else if (type === 'boolean') {
      args[name] = v === 'true';
    } else if (type === 'array') {
      try {
        const parsed = JSON.parse(v);
        args[name] = Array.isArray(parsed) ? parsed : [parsed];
      } catch {
        args[name] = v.split('\n').map((s) => s.trim()).filter(Boolean);
      }
    } else if (type === 'object') {
      try { args[name] = JSON.parse(v); } catch { throw new Error(`参数 ${name} 不是合法的 JSON 对象`); }
    } else {
      args[name] = v;
    }
  }
  return args;
}

function applyArgsToForm(root, args) {
  for (const el of root.querySelectorAll('[data-param]')) {
    const name = el.dataset.param;
    if (!(name in args)) continue;
    const v = args[name];
    const type = el.dataset.type;
    if (type === 'array' || type === 'object') el.value = JSON.stringify(v);
    else el.value = String(v);
  }
}

function resultBlock(ok, headText, bodyText, ms) {
  return `<div class="tool-result ${ok ? 'ok' : 'err'}">
    <div class="tool-result-head">${ok ? icon('check') : icon('alert')} ${headText}${ms !== undefined ? ` <span class="muted small">· ${ms} ms</span>` : ''}</div>
    <pre>${escapeHtml(bodyText)}</pre>
  </div>`;
}

function openToolModal(t, focusTest = false) {
  const props = (t.parameters && t.parameters.properties) || {};
  const presetHtml = Object.entries(t.presets || {}).map(
    ([k, v]) => `<span class="badge ${v === 'deferred' ? 'orange' : 'blue'}">${escapeHtml(k)}:${v === 'deferred' ? '待发现' : '默认启用'}</span>`).join(' ');

  const testSection = t.testable ? `
    <div class="tool-test card">
      <div class="tool-test-head">
        <h4>${icon('terminal')} 测试执行</h4>
        <div class="seg" id="tool-test-mode">
          <button data-mode="form" class="active">表单</button>
          <button data-mode="json">JSON 源码</button>
        </div>
      </div>
      <div id="tool-test-form">
        ${Object.keys(props).length
          ? Object.entries(props).map(([n, p]) => `
            <div class="field">
              <label class="field-label mono">${escapeHtml(n)} <span class="muted small">${escapeHtml(paramTypeLabel(p))}</span></label>
              ${fieldHtml(n, p)}
            </div>`).join('')
          : '<p class="muted small">该工具没有参数，直接运行即可。</p>'}
      </div>
      <div id="tool-test-json" class="hidden">
        <textarea class="textarea mono" id="tool-json-src" rows="6" spellcheck="false" placeholder='{"param": "value"}'>{}</textarea>
      </div>
      <div class="tool-test-foot">
        <button class="btn primary" id="tool-run">${icon('send')} 运行测试</button>
        <span class="muted small">在 bot 进程内直接执行，结果仅显示在面板上</span>
      </div>
      <div id="tool-result"></div>
    </div>` : `
    <div class="notice info">${icon('info')}<div>该工具${escapeHtml(t.testable_reason || '依赖聊天上下文')}，无法在面板测试，只能在真实聊天中触发。</div></div>`;

  const modal = openModal({
    title: t.name,
    wide: true,
    bodyHtml: `
      <div class="tool-meta">
        <div>${sourceBadges(t)} <span class="muted small mono">${escapeHtml(t.source_detail || '')}</span></div>
        <div>${scopeBadges(t)} ${presetHtml || ''}</div>
      </div>
      <p class="tool-desc">${escapeHtml(t.description || '（无描述）')}</p>
      <h4 class="tool-sec-title">参数</h4>
      ${paramsTableHtml(t)}
      ${testSection}`,
    actions: [{ label: '关闭', class: 'ghost', onClick: ({ close }) => close() }],
  });

  const el = modal.el;
  if (!t.testable) return;

  let mode = 'form';
  const formBox = el.querySelector('#tool-test-form');
  const jsonBox = el.querySelector('#tool-test-json');
  const jsonSrc = el.querySelector('#tool-json-src');
  const resultBox = el.querySelector('#tool-result');
  const runBtn = el.querySelector('#tool-run');

  el.querySelector('#tool-test-mode').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-mode]');
    if (!btn) return;
    const next = btn.dataset.mode;
    if (next === mode) return;
    if (next === 'json') {
      try { jsonSrc.value = JSON.stringify(collectArgs(formBox), null, 2); }
      catch (err) { toast(err.message, 'error'); return; }
    } else {
      try {
        const parsed = jsonSrc.value.trim() ? JSON.parse(jsonSrc.value) : {};
        if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error();
        applyArgsToForm(formBox, parsed);
      } catch { toast('JSON 源码不是合法的对象，无法切回表单模式', 'error'); return; }
    }
    mode = next;
    el.querySelectorAll('#tool-test-mode button').forEach((b) => b.classList.toggle('active', b === btn));
    formBox.classList.toggle('hidden', mode !== 'form');
    jsonBox.classList.toggle('hidden', mode !== 'json');
  });

  runBtn.addEventListener('click', async () => {
    let args;
    try {
      args = mode === 'json'
        ? (jsonSrc.value.trim() ? JSON.parse(jsonSrc.value) : {})
        : collectArgs(formBox);
      if (typeof args !== 'object' || args === null || Array.isArray(args)) throw new Error('参数必须是 JSON 对象');
    } catch (err) {
      resultBox.innerHTML = resultBlock(false, '参数错误', err instanceof SyntaxError ? `JSON 语法错误：${err.message}` : err.message);
      return;
    }
    runBtn.classList.add('loading');
    runBtn.disabled = true;
    resultBox.innerHTML = '<div class="muted small" style="padding:10px 0">执行中，最长等待 60 秒…</div>';
    try {
      const res = await api.post('/tools/test', { name: t.name, arguments: args });
      resultBox.innerHTML = res.ok
        ? resultBlock(true, '执行成功', JSON.stringify(res.result ?? null, null, 2), res.duration_ms)
        : resultBlock(false, '执行失败（工具抛出异常）', res.error, res.duration_ms);
    } catch (err) {
      resultBox.innerHTML = resultBlock(false, '请求失败', err.message);
    } finally {
      runBtn.classList.remove('loading');
      runBtn.disabled = false;
    }
  });

  if (focusTest) el.querySelector('.tool-test')?.scrollIntoView({ block: 'nearest' });
}

export const toolsView = { title: 'LLM 工具', init };
