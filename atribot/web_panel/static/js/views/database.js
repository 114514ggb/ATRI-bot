/* 视图：数据库（连接状态 / 表结构浏览 / SQL 控制台） */

import { api } from '../api.js';
import { icon, toast, openModal, confirmDialog, escapeHtml } from '../ui.js';

const HISTORY_KEY = 'atri_db_sql_history';
const HISTORY_MAX = 20;
const READ_VERBS = new Set(['select', 'show', 'explain', 'values', 'table', 'with']);

/* 与后端一致的读语句判定：非读语句执行前要求确认 */
function isReadSql(sql) {
  const cleaned = sql.replace(/--[^\n]*/g, ' ').trim().replace(/;+\s*$/, '').trim();
  const first = (cleaned.split(/\s+/)[0] || '').toLowerCase();
  return READ_VERBS.has(first) || /\breturning\b/i.test(cleaned);
}

function fmtNum(n) {
  if (n === null || n === undefined || n === '') return '—';
  const num = Number(n);
  if (Number.isNaN(num)) return String(n);
  return num.toLocaleString();
}

/* "3 days, 04:12:33.123" → "3 天 04:12:33" */
function fmtUptime(s) {
  if (!s) return '—';
  return s.split('.')[0].replace(/,\s*/, ' ').replace(/days?/i, '天').replace(/(\d+)天/, '$1 天');
}

function loadHistory() {
  try {
    const h = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(h) ? h : [];
  } catch {
    return [];
  }
}

function pushHistory(sql) {
  const h = loadHistory().filter((x) => x !== sql);
  h.unshift(sql);
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(h.slice(0, HISTORY_MAX)));
  } catch { /* 存储满时静默丢弃 */ }
}

async function init(section) {
  section.innerHTML = `<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>`;
  const ctx = { runSql: null };
  await loadOverview(section, ctx);
}

async function loadOverview(section, ctx) {
  section.innerHTML = `<div class="skeleton skeleton-card"></div>`;
  let status;
  try {
    status = await api.get('/db/status');
  } catch (e) {
    section.innerHTML = `<div class="notice danger">${icon('alert')}<div>数据库状态加载失败：${escapeHtml(e.message)}</div></div>`;
    return;
  }

  if (!status.available) {
    section.innerHTML = `
      <div class="notice warn">${icon('alert')}<div>
        <b>数据库不可用</b>
        <div class="small mono" style="margin-top:6px">${escapeHtml(status.reason || '未知原因')}</div>
      </div></div>
      <button class="btn" id="db-retry" style="margin-top:14px">${icon('refresh')} 重试</button>`;
    section.querySelector('#db-retry').addEventListener('click', () => loadOverview(section, ctx));
    return;
  }

  let tables = [];
  try {
    tables = (await api.get('/db/tables')).tables || [];
  } catch (e) {
    toast(`表清单加载失败：${e.message}`, 'error');
  }
  renderPage(section, ctx, status, tables);
}

/* ---------- 主页面 ---------- */

function renderPage(section, ctx, status, tables) {
  const pool = status.pool;
  const verShort = (status.version || '').split(' on ')[0];
  const poolText = pool ? `${pool.size - pool.idle}/${pool.size}` : '—';

  section.innerHTML = `
    <div class="db-conn-line">
      <span class="badge green">已连接</span>
      <span class="mono small">${escapeHtml(`${status.host || '?'}:${status.port || '?'}`)} · ${escapeHtml(status.user || '?')}@${escapeHtml(status.db_name || '?')}</span>
      <span class="muted small" title="${escapeHtml(status.version || '')}">${escapeHtml(verShort)}</span>
      <span class="spacer"></span>
      <button class="btn sm ghost" id="db-refresh">${icon('refresh')} 刷新</button>
    </div>
    <div class="db-stats">
      <div class="stat-card"><span class="stat-num">${tables.length}</span><span class="stat-label">表</span></div>
      <div class="stat-card"><span class="stat-num text">${escapeHtml(status.db_size || '—')}</span><span class="stat-label">数据库大小</span></div>
      <div class="stat-card"><span class="stat-num">${fmtNum(status.connections)}</span><span class="stat-label">活跃连接</span></div>
      <div class="stat-card"><span class="stat-num text">${escapeHtml(poolText)}</span><span class="stat-label">连接池使用</span></div>
      <div class="stat-card"><span class="stat-num text">${escapeHtml(fmtUptime(status.uptime))}</span><span class="stat-label">服务器运行</span></div>
    </div>
    <div class="db-grid">
      <div class="db-col">
        <div class="db-section-title">${icon('layers')} 表 <span class="muted small">${tables.length}</span></div>
        <div class="card table-wrap db-tables-wrap">
          <table class="tbl">
            <thead><tr><th>表名</th><th style="width:90px">行数 (估)</th><th style="width:80px">大小</th><th style="width:52px">列</th></tr></thead>
            <tbody>
              ${tables.map((t) => `
                <tr class="db-table-row" data-table="${escapeHtml(t.table_name)}" title="${escapeHtml(t.comment || '点击查看表结构')}">
                  <td class="mono">${escapeHtml(t.table_name)}</td>
                  <td>${t.row_estimate > 0 ? fmtNum(t.row_estimate) : '—'}</td>
                  <td>${escapeHtml(t.size_pretty || '—')}</td>
                  <td>${fmtNum(t.column_count)}</td>
                </tr>`).join('') || '<tr><td colspan="4" class="muted">没有找到表</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
      <div class="db-col">
        <div class="db-section-title">${icon('terminal')} SQL 控制台 <span class="muted small">Ctrl+Enter 运行</span></div>
        <div class="card db-console">
          <div class="db-console-bar">
            <select class="select" id="db-history" style="max-width:260px"><option value="">历史记录</option></select>
            <button class="btn sm ghost" id="db-history-clear" title="清空历史">${icon('trash')}</button>
          </div>
          <textarea class="input db-sql mono" id="db-sql" rows="5" spellcheck="false"
            placeholder="SELECT * FROM users LIMIT 100;"></textarea>
          <div class="db-console-foot">
            <button class="btn primary" id="db-run">${icon('send')} 运行</button>
            <span class="muted small">写语句执行前会要求确认；超长文本与向量列会被截断，最多返回 500 行</span>
          </div>
          <div id="db-result"></div>
        </div>
      </div>
    </div>`;

  section.querySelector('#db-refresh').addEventListener('click', () => loadOverview(section, ctx));
  section.querySelectorAll('.db-table-row[data-table]').forEach((row) =>
    row.addEventListener('click', () => openTableModal(ctx, row.dataset.table)));

  bindConsole(section, ctx);
}

/* ---------- SQL 控制台 ---------- */

function bindConsole(section, ctx) {
  const sqlInput = section.querySelector('#db-sql');
  const runBtn = section.querySelector('#db-run');
  const resultBox = section.querySelector('#db-result');
  const historySel = section.querySelector('#db-history');
  let resultMode = 'table';
  let lastResult = null;

  /* ---------- 结果渲染 ---------- */

  function cellHtml(col, v, rIdx) {
    if (v === null || v === undefined) return '<span class="cell-null">NULL</span>';
    if (typeof v === 'boolean') return `<span class="badge ${v ? 'green' : 'gray'}">${v}</span>`;
    if (typeof v === 'number') return escapeHtml(String(v));
    const s = String(v);
    if (s.length > 140) {
      return `<span class="cell-long" data-r="${rIdx}" data-c="${escapeHtml(col)}" title="点击查看全文">${escapeHtml(s.slice(0, 140))} …</span>`;
    }
    return escapeHtml(s);
  }

  function renderResultBody() {
    const res = lastResult;
    /* 0 列结果（如裸 select;）：单独提示，避免空表格 / [{}] 让人误以为出错 */
    if (!res.columns.length) {
      resultBox.innerHTML = `
        <div class="db-result-bar">
          <span class="small muted">${res.row_count} 行 · 0 列 · ${res.duration_ms} ms</span>
        </div>
        <div class="muted small" style="padding:10px 2px">语句执行成功，返回了空的行和列</div>`;
      return;
    }
    if (resultMode === 'json') {
      resultBox.innerHTML = `
        <div class="db-result-bar">
          <span class="small muted">${res.row_count} 行 · ${res.duration_ms} ms${res.truncated ? ` · 仅显示前 ${res.rows.length} 行` : ''}</span>
          <span class="spacer"></span>
          <div class="seg" id="db-result-mode">
            <button data-mode="table">表格</button>
            <button data-mode="json" class="active">JSON</button>
          </div>
          <button class="btn sm ghost" id="db-copy-json" title="复制 JSON">${icon('copy')}</button>
        </div>
        <pre class="db-json mono">${escapeHtml(JSON.stringify(res.rows, null, 2))}</pre>`;
    } else {
      const rowsHtml = res.rows
        .map((row, r) => `<tr>${res.columns.map((c) => `<td>${cellHtml(c, row[c], r)}</td>`).join('')}</tr>`)
        .join('');
      resultBox.innerHTML = `
        <div class="db-result-bar">
          <span class="small muted">${res.row_count} 行 · ${res.duration_ms} ms${res.truncated ? ` · 仅显示前 ${res.rows.length} 行` : ''}</span>
          <span class="spacer"></span>
          <div class="seg" id="db-result-mode">
            <button data-mode="table" class="active">表格</button>
            <button data-mode="json">JSON</button>
          </div>
          <button class="btn sm ghost" id="db-copy-json" title="复制 JSON">${icon('copy')}</button>
        </div>
        ${res.rows.length
          ? `<div class="db-result-wrap"><table class="tbl db-result-table">
              <thead><tr>${res.columns.map((c) => `<th class="mono">${escapeHtml(c)}</th>`).join('')}</tr></thead>
              <tbody>${rowsHtml}</tbody>
            </table></div>`
          : '<div class="muted small" style="padding:10px 2px">语句执行成功，但没有返回行。</div>'}`;
    }

    resultBox.querySelector('#db-result-mode').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-mode]');
      if (!btn) return;
      resultMode = btn.dataset.mode;
      renderResultBody();
    });
    resultBox.querySelector('#db-copy-json').addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(JSON.stringify(res.rows, null, 2));
        toast('JSON 结果已复制');
      } catch {
        toast('复制失败：浏览器拒绝了剪贴板访问', 'error');
      }
    });
    resultBox.querySelectorAll('.cell-long').forEach((cell) =>
      cell.addEventListener('click', () => {
        const row = res.rows[Number(cell.dataset.r)];
        const v = row ? row[cell.dataset.c] : '';
        openModal({
          title: `字段值 · ${cell.dataset.c}`,
          wide: true,
          bodyHtml: `<pre class="db-cell-full mono">${escapeHtml(typeof v === 'object' && v !== null ? JSON.stringify(v, null, 2) : String(v))}</pre>`,
          actions: [{ label: '关闭', class: 'ghost', onClick: ({ close }) => close() }],
        });
      }));
  }

  function renderResult(res) {
    lastResult = null;
    if (!res.ok) {
      resultBox.innerHTML = `<div class="notice danger">${icon('alert')}<div><b>执行出错</b><pre class="db-error mono">${escapeHtml(res.error || '未知错误')}</pre></div></div>`;
      return;
    }
    if (res.kind === 'status') {
      resultBox.innerHTML = `<div class="notice info">${icon('check')}<div>执行成功 · <span class="mono">${escapeHtml(res.status || 'OK')}</span> · ${res.duration_ms} ms</div></div>`;
      return;
    }
    lastResult = res;
    renderResultBody();
  }

  /* ---------- 执行 ---------- */

  async function runSql(sqlText) {
    const sql = (sqlText !== undefined ? sqlText : sqlInput.value).trim();
    if (!sql) {
      toast('请输入 SQL 语句', 'info');
      return;
    }
    sqlInput.value = sql;

    if (!isReadSql(sql)) {
      const preview = escapeHtml(sql.length > 300 ? `${sql.slice(0, 300)}…` : sql);
      const ok = await confirmDialog({
        title: '执行写操作',
        message: `即将执行可能修改数据的语句：<pre class="db-confirm-sql mono">${preview}</pre>确定继续吗？`,
        confirmText: '执行',
        danger: true,
      });
      if (!ok) return;
    }

    runBtn.classList.add('loading');
    runBtn.disabled = true;
    resultBox.innerHTML = '<div class="muted small" style="padding:10px 2px">执行中，最长等待 30 秒…</div>';
    try {
      const res = await api.post('/db/query', { sql });
      renderResult(res);
      pushHistory(sql);
      renderHistory();
    } catch (e) {
      resultBox.innerHTML = `<div class="notice danger">${icon('alert')}<div>请求失败：<span class="mono small">${escapeHtml(e.message)}</span></div></div>`;
    } finally {
      runBtn.classList.remove('loading');
      runBtn.disabled = false;
    }
  }

  ctx.runSql = runSql;
  runBtn.addEventListener('click', () => runSql());
  sqlInput.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runSql();
    }
  });

  /* ---------- 历史 ---------- */

  function renderHistory() {
    const h = loadHistory();
    historySel.innerHTML = '<option value="">历史记录</option>' +
      h.map((s, i) => `<option value="${i}">${escapeHtml(s.replace(/\s+/g, ' ').slice(0, 80))}</option>`).join('');
  }

  historySel.addEventListener('change', () => {
    if (historySel.value === '') return;
    const item = loadHistory()[Number(historySel.value)];
    if (item) sqlInput.value = item;
    historySel.value = '';
  });

  section.querySelector('#db-history-clear').addEventListener('click', async () => {
    if (!loadHistory().length) return;
    const ok = await confirmDialog({ title: '清空历史', message: '确定清空全部 SQL 执行历史吗？', confirmText: '清空', danger: true });
    if (!ok) return;
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
    toast('历史已清空', 'info');
  });

  renderHistory();
}

/* ---------- 表结构弹窗 ---------- */

const CONSTRAINT_LABELS = { p: '主键', u: '唯一', c: 'CHECK', f: '外键', x: '排除', n: 'NOT NULL', t: '触发器' };

async function openTableModal(ctx, name) {
  const modal = openModal({
    title: `表 · ${name}`,
    wide: true,
    bodyHtml: '<div class="skeleton skeleton-card"></div>',
    actions: [
      {
        label: '查看数据',
        class: 'primary',
        onClick: ({ close }) => {
          close();
          if (ctx.runSql) ctx.runSql(`SELECT * FROM "${name}" LIMIT 100;`);
        },
      },
      { label: '关闭', class: 'ghost', onClick: ({ close }) => close() },
    ],
  });

  let data;
  try {
    data = await api.get(`/db/table?name=${encodeURIComponent(name)}`);
  } catch (e) {
    modal.el.querySelector('.modal-body').innerHTML =
      `<div class="notice danger">${icon('alert')}<div>表结构加载失败：${escapeHtml(e.message)}</div></div>`;
    return;
  }

  const colRows = data.columns.map((c) => `
    <tr>
      <td class="mono">${escapeHtml(c.column_name)}</td>
      <td class="mono">${escapeHtml(c.udt_name)}${c.character_maximum_length ? `(${c.character_maximum_length})` : ''}</td>
      <td>${c.is_nullable === 'YES' ? '<span class="muted">可空</span>' : '<span class="badge orange">非空</span>'}</td>
      <td class="mono db-default-cell">${escapeHtml(c.column_default || '—')}</td>
    </tr>`).join('');

  const idxItems = data.indexes.length
    ? data.indexes.map((i) => `<div class="db-def-item mono">${escapeHtml(i.indexdef)}</div>`).join('')
    : '<p class="muted small">无索引</p>';

  const conItems = data.constraints.length
    ? data.constraints.map((c) => `
        <div class="db-def-item">
          <span class="badge gray">${CONSTRAINT_LABELS[c.type] || c.type}</span>
          <span class="mono small">${escapeHtml(c.name)}</span>
          <span class="mono small muted">${escapeHtml(c.def)}</span>
        </div>`).join('')
    : '<p class="muted small">无约束</p>';

  modal.el.querySelector('.modal-body').innerHTML = `
    <div class="db-modal-head">
      <span class="badge blue">${fmtNum(data.row_count)} 行</span>
      <span class="badge gray">${data.columns.length} 列</span>
      <span class="badge gray">${data.indexes.length} 索引</span>
    </div>
    <h4 class="db-sub-title">列</h4>
    <div class="table-wrap"><table class="tbl">
      <thead><tr><th>列名</th><th>类型</th><th style="width:70px">可空</th><th>默认值</th></tr></thead>
      <tbody>${colRows}</tbody>
    </table></div>
    <h4 class="db-sub-title">索引</h4>
    ${idxItems}
    <h4 class="db-sub-title">约束</h4>
    ${conItems}`;
}

export const databaseView = { title: '数据库', init };
