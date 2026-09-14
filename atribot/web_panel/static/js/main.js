/* 面板入口：登录 / 路由注册 / 顶栏与系统菜单 */

import { api, getToken, setToken, onUnauthorized } from './api.js';
import { icon, toast, initTheme, toggleTheme, confirmDialog } from './ui.js';
import { registerRoute, startRouter } from './router.js';
import { restartAndWait } from './components/editor-kit.js';

import { dashboardView } from './views/dashboard.js';
import { groupsView, usersView, messagesView, commandsView } from './views/data.js';
import { memoryView } from './views/memory.js';
import { configView } from './views/config.js';
import { supplierView } from './views/supplier.js';
import { mcpView } from './views/mcp.js';
import { personasView } from './views/personas.js';
import { logsView } from './views/logs.js';
import { sendView } from './views/send.js';

/* ---------- 视图注册 ---------- */

registerRoute('dashboard', dashboardView);
registerRoute('logs', logsView);
registerRoute('groups', groupsView);
registerRoute('users', usersView);
registerRoute('messages', messagesView);
registerRoute('memory', memoryView);
registerRoute('commands', commandsView);
registerRoute('config', configView);
registerRoute('supplier', supplierView);
registerRoute('mcp', mcpView);
registerRoute('personas', personasView);
registerRoute('send', sendView);

/* ---------- 登录流程 ---------- */

const loginOverlay = () => document.getElementById('login-overlay');
const app = () => document.getElementById('app');

function showLogin(message = null) {
  const overlay = loginOverlay();
  overlay.classList.remove('closing', 'hidden');
  app().classList.add('hidden');
  const err = document.getElementById('login-error');
  if (message) {
    err.textContent = message;
    err.classList.add('show');
    overlay.querySelector('.login-card').classList.add('shake');
    setTimeout(() => overlay.querySelector('.login-card').classList.remove('shake'), 550);
  } else {
    err.classList.remove('show');
  }
}

function showApp() {
  const overlay = loginOverlay();
  overlay.classList.add('closing');
  setTimeout(() => {
    overlay.classList.add('hidden');
    overlay.classList.remove('closing');
  }, 460);
  app().classList.remove('hidden');
  if (!document.getElementById('view-scroll').children.length || !document.querySelector('.view.active')) {
    startRouterOnce();
  }
}

let routerStarted = false;
function startRouterOnce() {
  if (!routerStarted) {
    routerStarted = true;
    startRouter();
  }
}

async function checkAuth() {
  const btn = document.getElementById('login-btn');
  btn.classList.add('loading');
  try {
    await api.get('/status');
    btn.classList.remove('loading');
    showApp();
  } catch (e) {
    btn.classList.remove('loading');
    if (e.message.includes('令牌')) showLogin('访问令牌无效，请重新输入');
    else showLogin(`无法连接面板服务：${e.message}`);
  }
}

/* ---------- 系统菜单 ---------- */

function closeMenus() {
  document.querySelectorAll('.menu').forEach((m) => m.remove());
}

function openSystemMenu(anchor) {
  closeMenus();
  const menu = document.createElement('div');
  menu.className = 'menu';
  menu.innerHTML = `
    <button class="menu-item" data-sys="restart">${icon('refresh')} 重启服务</button>
    <button class="menu-item danger" data-sys="stop">${icon('power')} 停止服务</button>
    <div class="menu-sep"></div>
    <button class="menu-item" data-sys="logout">${icon('x')} 退出登录</button>`;
  anchor.appendChild(menu);

  menu.addEventListener('click', async (e) => {
    const item = e.target.closest('[data-sys]');
    if (!item) return;
    closeMenus();
    const action = item.dataset.sys;

    if (action === 'logout') {
      setToken('');
      showLogin();
      return;
    }
    if (action === 'restart') {
      const ok = await confirmDialog({ title: '重启服务', message: '重启会短暂中断 bot 服务，确定继续吗？', confirmText: '重启', danger: true });
      if (ok) await restartAndWait();
      return;
    }
    if (action === 'stop') {
      const ok = await confirmDialog({
        title: '停止服务',
        message: '停止后 bot 将完全下线，<b>需要手动重新启动</b>。确定继续吗？',
        confirmText: '停止',
        danger: true,
      });
      if (!ok) return;
      try { await api.post('/system/stop'); } catch { /* 进程退出导致中断 */ }
      toast('服务停止指令已发送', 'info');
    }
  });
}

/* ---------- 初始化 ---------- */

function bindChrome() {
  document.getElementById('login-btn').addEventListener('click', () => {
    const token = document.getElementById('access-token').value.trim();
    if (!token) { showLogin('请输入访问令牌'); return; }
    setToken(token);
    checkAuth();
  });
  document.getElementById('access-token').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') document.getElementById('login-btn').click();
  });

  document.getElementById('btn-theme').addEventListener('click', toggleTheme);

  document.getElementById('btn-sidebar-toggle').addEventListener('click', () => {
    app().classList.toggle('sidebar-collapsed');
  });

  const menuWrap = document.getElementById('system-menu-wrap');
  document.getElementById('btn-system').addEventListener('click', (e) => {
    e.stopPropagation();
    const open = menuWrap.querySelector('.menu');
    if (open) closeMenus();
    else openSystemMenu(menuWrap);
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.menu-wrap')) closeMenus();
  });

  onUnauthorized(() => showLogin('登录已过期，请重新输入令牌'));
}

initTheme();
bindChrome();

if (getToken()) {
  document.getElementById('access-token').value = getToken();
  checkAuth();
} else {
  showLogin();
}
