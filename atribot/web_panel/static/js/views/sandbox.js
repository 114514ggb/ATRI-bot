/* 视图：容器管理（沙盒状态 / 启停 / 重启 + 沙盒内终端）
   页面完全由后端的 panel_* 扩展点驱动，切换沙盒实现无需改这里 */

import { api, sandboxWsUrl } from '../api.js';
import { icon, escapeHtml, confirmDialog, toast } from '../ui.js';
import { TERMINAL_HINT_SANDBOX } from '../copy.js';
import { createTerminal } from '../components/term-core.js';

let term = null;
let pollTimer = null;
let refreshing = false;

async function init(section) {
  term?.destroy();
  term = null;
  section.innerHTML = `
    <div class="logs-toolbar">
      <span style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600">
        <span class="dot yellow js-dot"></span><span class="js-state">加载中…</span>
      </span>
      <span class="sb-type js-type"></span>
      <span style="flex:1"></span>
      <button class="btn sm ghost js-refresh">${icon('refresh')} 刷新</button>
      <button class="btn sm ghost js-sync-tools" title="按当前配置重建沙盒并刷新工具描述">${icon('refresh')} 同步工具</button>
      <button class="btn sm ghost js-action" data-action="restart">${icon('refresh')} 重启</button>
      <button class="btn sm ghost js-action" data-action="stop">${icon('power')} 停止</button>
      <button class="btn sm primary js-action" data-action="start">${icon('activity')} 启动</button>
    </div>
    <div class="sb-status-card js-card" style="display:none"></div>
    <div class="sb-terminal-mount js-term-mount" style="display:none"></div>
    <div class="notice js-na" style="display:none"></div>`;

  const q = (sel) => section.querySelector(sel);

  q('.js-refresh').addEventListener('click', () => refresh(section));
  q('.js-sync-tools').addEventListener('click', (e) => syncTools(section, e.currentTarget));
  section.querySelectorAll('.js-action').forEach((btn) => {
    btn.addEventListener('click', () => doAction(section, btn.dataset.action, btn));
  });

  /* 先启动轮询再首次刷新：若 refresh 的 await 期间视图被销毁，interval 也必须已被
     pollTimer 记录，否则 destroy() 清不到，产生僵尸轮询 */
  pollTimer = setInterval(() => refresh(section, true), 10000);
  await refresh(section);
}

async function refresh(section, silent = false) {
  if (refreshing) return;
  refreshing = true;
  const q = (sel) => section.querySelector(sel);
  try {
    const st = await api.get('/sandbox/status');
    render(section, st);
  } catch (e) {
    if (!silent) toast(`获取沙盒状态失败：${e.message}`, 'error');
  } finally {
    refreshing = false;
  }
}

function render(section, st) {
  const q = (sel) => section.querySelector(sel);
  const running = !!st.running;
  const caps = st.capabilities || { start_stop: true, terminal: false };

  const dot = q('.js-dot');
  dot.classList.remove('green', 'red');
  dot.classList.add(running ? 'green' : 'red');
  q('.js-state').textContent = st.configured ? (running ? '运行中' : '已停止') : '未初始化';
  q('.js-type').textContent = `后端 ${st.display || st.type || '?'}`;
  q('.js-action[data-action="start"]').disabled = running;
  q('.js-action[data-action="stop"]').disabled = !running;
  q('.js-action[data-action="restart"]').disabled = !running;

  /* 状态行（后端自定义的有序键值对，原样渲染） */
  const rows = Array.isArray(st.rows) ? st.rows : [];
  if (st.configured && rows.length) {
    const card = q('.js-card');
    card.style.display = '';
    card.innerHTML = rows.map(([label, value]) => `
      <div class="sb-row">
        <span class="sb-label">${escapeHtml(label)}</span>
        <span class="sb-value">${escapeHtml(value ?? '')}</span>
      </div>`).join('');
  } else {
    q('.js-card').style.display = 'none';
  }

  if (!st.configured) {
    const na = q('.js-na');
    na.style.display = '';
    na.innerHTML = `${icon('info')}<div>沙盒尚未初始化：点击“启动”按当前配置（${escapeHtml(st.type || 'docker')}）立即创建。</div>`;
  } else {
    q('.js-na').style.display = 'none';
  }

  /* 终端：能力允许且运行中才挂载 */
  const mount = q('.js-term-mount');
  if (st.configured && caps.terminal && running) {
    mount.style.display = '';
    if (!term) {
      term = createTerminal(mount, {
        wsUrl: sandboxWsUrl(),
        historyKey: 'atri_sterm_history',
        allowComplete: false,
        banner: (info) => [
          `沙盒终端 · ${info.user}@${info.host} · ${info.platform || ''}`,
          TERMINAL_HINT_SANDBOX,
        ],
      });
    }
  } else {
    mount.style.display = 'none';
    term?.destroy();
    term = null;
    /* 终端不可用时的原因提示（后端不支持 / 沙盒未运行） */
    let reason = '';
    if (st.configured && caps.terminal === false) {
      reason = `当前沙盒后端（${escapeHtml(st.display || st.type || '')}）暂未提供终端能力。`;
    } else if (st.configured && !running) {
      reason = '沙盒已停止，启动后可连接终端。';
    }
    if (reason) {
      const na = q('.js-na');
      na.style.display = '';
      na.innerHTML = `${icon('info')}<div>${reason}</div>`;
    }
  }
}

async function doAction(section, action, btn) {
  if (action === 'stop') {
    const ok = await confirmDialog({
      title: '停止沙盒',
      message: '停止后 LLM 将无法执行代码/命令类工具，<b>直到再次启动</b>。确定继续吗？',
      confirmText: '停止',
      danger: true,
    });
    if (!ok) return;
  }
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.classList.add('loading');
  try {
    const res = await api.post(`/sandbox/${action}`);
    const label = { start: '沙盒已启动', stop: '沙盒已停止', restart: '沙盒已重启' }[action];
    if (res.status === 'already_running') toast('沙盒已在运行中', 'info');
    else if (res.status === 'already_stopped') toast('沙盒本就未在运行', 'info');
    else toast(label, 'success');
  } catch (e) {
    toast(`${e.message}`, 'error');
  } finally {
    btn.innerHTML = original;
    btn.classList.remove('loading');
    await refresh(section);
  }
}

async function syncTools(section, btn) {
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.classList.add('loading');
  try {
    const res = await api.post('/sandbox/refresh-tools');
    const changed = res.changed_tools || [];
    toast(
      changed.length
        ? `沙盒已按当前配置重建，刷新了 ${changed.length} 个工具：${changed.join(', ')}`
        : '沙盒已按当前配置重建，工具描述无变化',
      'success'
    );
  } catch (e) {
    toast(`${e.message}`, 'error');
  } finally {
    btn.innerHTML = original;
    btn.classList.remove('loading');
    await refresh(section);
  }
}

function destroy() {
  clearInterval(pollTimer);
  pollTimer = null;
  term?.destroy();
  term = null;
}

export const sandboxView = { title: '容器管理', init, destroy };
