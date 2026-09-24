/* 视图：仪表盘（统计卡片 + token 图表 + 系统状态 + 平台状态） */

import { api } from '../api.js';
import { icon, countUp, fmtTokens, escapeHtml, confirmDialog } from '../ui.js';
import { stopAndWait } from '../components/editor-kit.js';

const STAT_DEFS = [
  { key: 'groups', label: '群组总计', icon: 'group', tint: 'tint-blue' },
  { key: 'users', label: '用户总计', icon: 'users', tint: 'tint-teal' },
  { key: 'messages', label: '消息总数', icon: 'message', tint: 'tint-purple' },
  { key: 'memories', label: '记忆条数', icon: 'memory', tint: 'tint-orange' },
  { key: 'today_messages', label: '今日消息', icon: 'activity', tint: 'tint-green' },
  { key: 'today_tokens', label: '今日 Token', icon: 'coins', tint: 'tint-blue', fmt: fmtTokens },
  { key: 'active_contexts', label: '活跃会话', icon: 'clock', tint: 'tint-teal' },
];

function statusBool(v) {
  return `<span class="badge ${v ? 'green' : 'gray'}">${v ? '启用' : '未启用'}</span>`;
}

async function init(section) {
  section.innerHTML = `
    <div class="stat-cards">${STAT_DEFS.map(() => '<div class="skeleton" style="height:110px;border-radius:18px"></div>').join('')}</div>
    <div class="grid cols-2" style="align-items:start">
      <div class="card"><div class="skeleton" style="height:220px;border-radius:12px"></div></div>
      <div class="card"><div class="skeleton" style="height:220px;border-radius:12px"></div></div>
    </div>`;

  const [stats, status, tokenStats] = await Promise.all([
    api.get('/stats'),
    api.get('/status'),
    api.get('/stats/tokens?days=7').catch(() => ({ items: [] })),
  ]);

  /* 统计卡片（数字滚动动画） */
  const cards = STAT_DEFS.map((def, i) => {
    const value = stats[def.key] ?? 0;
    return `<div class="stat-card" style="animation-delay:${i * 60}ms">
      <div class="stat-icon ${def.tint}">${icon(def.icon)}</div>
      <div class="stat-value" data-count="${value}" data-fmt="${def.fmt ? 'compact' : 'plain'}">0</div>
      <div class="stat-label">${def.label}</div>
    </div>`;
  }).join('');

  /* 7 天 token 柱状图 */
  const chartHtml = renderChart(tokenStats.items || []);

  /* 系统状态 */
  const platforms = Object.entries(status.platforms || {})
    .map(
      ([name, p]) => `<div class="status-row">
        <span class="k"><span class="dot ${p.is_connected ? 'green' : p.is_started ? 'yellow' : 'red'}"></span>平台 · ${escapeHtml(name)}</span>
        <span class="v">${p.is_connected ? '已连接' : p.is_started ? '连接中' : '未连接'} · ${escapeHtml(String(p.type))}</span>
      </div>`
    )
    .join('') || '<div class="status-row"><span class="k">平台</span><span class="v muted">无</span></div>';

  section.innerHTML = `
    <div class="stat-cards">${cards}</div>
    <div class="grid cols-2" style="align-items:start">
      <div class="card hoverable" style="animation:fade-slide-in .45s var(--ease-out) .1s backwards">
        <h3 class="card-title">近 7 天 Token 用量</h3>
        <p class="card-sub">按天统计的模型调用消耗</p>
        ${chartHtml}
      </div>
      <div class="card" style="animation:fade-slide-in .45s var(--ease-out) .18s backwards">
        <h3 class="card-title">运行状态</h3>
        <p class="card-sub">服务与平台连接概况</p>
        <div class="status-rows">
          <div class="status-row"><span class="k">账号</span><span class="v">${escapeHtml(String(status.account_name || '-'))} (${escapeHtml(String(status.account_id || '-'))})</span></div>
          <div class="status-row"><span class="k">当前模型</span><span class="v">${escapeHtml(String(status.model || '-'))}</span></div>
          <div class="status-row"><span class="k">供应商</span><span class="v">${escapeHtml(String(status.supplier || '-'))}</span></div>
          <div class="status-row"><span class="k">运行时长</span><span class="v">${escapeHtml(String(status.uptime || '-'))}</span></div>
          <div class="status-row"><span class="k">连接方式</span><span class="v">${(status.connection_type || []).map((t) => `<span class="badge blue" style="margin-left:4px">${escapeHtml(t)}</span>`).join('') || '-'}</span></div>
          ${platforms}
          <div class="status-row"><span class="k">沙盒 / MCP / RAG</span>
            <span class="v">${statusBool(status.sandbox)} ${statusBool(status.mcp)} ${statusBool(status.rag)}</span></div>
        </div>
        <div style="display:flex;gap:10px;margin-top:16px">
          <button class="btn sm ghost" id="dash-stop">${icon('power')} 停止服务</button>
          <button class="btn sm ghost" id="dash-refresh">${icon('activity')} 刷新数据</button>
        </div>
      </div>
    </div>`;

  /* 数字滚动 */
  section.querySelectorAll('.stat-value').forEach((el) => {
    const target = Number(el.dataset.count);
    if (el.dataset.fmt === 'compact') countUp(el, target, { formatter: fmtTokens });
    else countUp(el, target);
  });

  section.querySelector('#dash-refresh').addEventListener('click', () => init(section));
  section.querySelector('#dash-stop').addEventListener('click', async () => {
    const ok = await confirmDialog({
      title: '停止服务',
      message: '停止后 bot 将完全下线（会先回收沙盒 / MCP / 数据库连接等资源），<b>需要手动重新启动</b>。确定继续吗？',
      confirmText: '停止', danger: true,
    });
    if (ok) await stopAndWait();
  });
}

function renderChart(items) {
  if (!items.length) {
    return `<div style="height:150px;display:flex;align-items:center;justify-content:center;color:var(--text-3);font-size:13px">暂无 token 消耗记录</div>`;
  }
  const max = Math.max(...items.map((i) => Number(i.total)), 1);
  return `<div class="bar-chart">${items
    .map((item, i) => {
      const total = Number(item.total);
      const h = Math.max(3, Math.round((total / max) * 100));
      return `<div class="bar-col">
        <div class="bar ${total === 0 ? 'zero' : ''}" style="height:${h}%;animation-delay:${i * 70}ms">
          <span class="bar-tip">${fmtTokens(total)} tokens</span>
        </div>
        <span class="bar-date">${escapeHtml(item.date)}</span>
      </div>`;
    })
    .join('')}</div>`;
}

export const dashboardView = { title: '仪表盘', init };
