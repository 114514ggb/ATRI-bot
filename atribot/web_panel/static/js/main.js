/* 面板入口：登录 / 路由注册 / 顶栏与系统菜单 */

import { api, getToken, setSession, setToken, getSessionRemainingMs, onUnauthorized } from './api.js';
import { icon, initTheme, toggleTheme, confirmDialog, initSelectMenus, mountLogoImage, upgradeFavicon } from './ui.js';
import { registerRoute, startRouter } from './router.js';
import { stopAndWait } from './components/editor-kit.js';
import { STOP_SERVICE_CONFIRM } from './copy.js';

import { dashboardView } from './views/dashboard.js';
import { groupsView, usersView, messagesView, commandsView } from './views/data.js';
import { toolsView } from './views/tools.js';
import { memoryView } from './views/memory.js';
import { databaseView } from './views/database.js';
import { configView } from './views/config.js';
import { supplierView } from './views/supplier.js';
import { mcpView } from './views/mcp.js';
import { personasView } from './views/personas.js';
import { logsView } from './views/logs.js';
import { terminalView } from './views/terminal.js';
import { sandboxView } from './views/sandbox.js';
import { apiCallView } from './views/api-call.js';
import { chatView } from './views/chat.js';

/* ---------- 视图注册 ---------- */

registerRoute('dashboard', dashboardView);
registerRoute('chat', chatView);
registerRoute('logs', logsView);
registerRoute('terminal', terminalView);
registerRoute('sandbox', sandboxView);
registerRoute('groups', groupsView);
registerRoute('users', usersView);
registerRoute('messages', messagesView);
registerRoute('memory', memoryView);
registerRoute('database', databaseView);
registerRoute('commands', commandsView);
registerRoute('tools', toolsView);
registerRoute('config', configView);
registerRoute('supplier', supplierView);
registerRoute('mcp', mcpView);
registerRoute('personas', personasView);
registerRoute('api-call', apiCallView);

/* ---------- 登录流程 ---------- */

const loginOverlay = () => document.getElementById('login-overlay');
const app = () => document.getElementById('app');

function showLogin(message = null) {
  const overlay = loginOverlay();
  overlay.classList.remove('closing', 'hidden');
  app().classList.add('hidden');
  resetLoginBtn();
  stopLockCountdown();
  stopSessionTimer();
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

/* 登录按钮的成功态（校验通过后短暂展示再进入应用） */
function loginSuccessState() {
  const btn = document.getElementById('login-btn');
  btn.classList.remove('loading');
  btn.disabled = true;
  btn.innerHTML = `${icon('check')} 登录成功`;
  btn.style.background = 'var(--green)';
  btn.style.borderColor = 'var(--green)';
  btn.style.color = '#fff';
}

/* 退出登录/校验失败重新回到登录层时，还原按钮 */
function resetLoginBtn() {
  const btn = document.getElementById('login-btn');
  btn.disabled = false;
  btn.classList.remove('loading');
  btn.innerHTML = '登 录';
  btn.style.background = '';
  btn.style.borderColor = '';
  btn.style.color = '';
}

/* ---------- 登录锁定倒计时：文案每秒跳动，到 0 提示解锁 ---------- */

let _lockTimer = null;

function stopLockCountdown() {
  if (_lockTimer) { clearInterval(_lockTimer); _lockTimer = null; }
}

function startLockCountdown(seconds) {
  stopLockCountdown();
  const err = document.getElementById('login-error');
  err.classList.add('show');
  const tick = () => {
    if (seconds > 0) {
      err.textContent = `尝试次数过多，请 ${seconds} 秒后重试`;
      seconds -= 1;
    } else {
      stopLockCountdown();
      err.textContent = '锁定已解除，请重试';
    }
  };
  tick();
  _lockTimer = setInterval(tick, 1000);
}

/* ---------- 会话到期：到点自动退出登录（与后端会话有效期一致） ---------- */

let _expiryTimer = null;

function stopSessionTimer() {
  if (_expiryTimer) { clearTimeout(_expiryTimer); _expiryTimer = null; }
}

function scheduleSessionTimer() {
  stopSessionTimer();
  const remaining = getSessionRemainingMs();
  if (remaining === null) return;  // 无到期信息（旧存储等）：交给 401 兜底
  if (remaining <= 0) { expireSession(); return; }
  _expiryTimer = setTimeout(expireSession, remaining);
}

/* 会话到期：清除本地凭证并回到登录层 */
function expireSession() {
  stopSessionTimer();
  setToken('');
  showLogin('会话已过期，请重新登录');
}

/* 每个浏览器会话只在第一次进入时播完整欢迎揭幕，之后刷新只播轻量级联 */
const WELCOMED_KEY = 'atri_welcomed';

function showApp() {
  const overlay = loginOverlay();
  overlay.classList.add('closing');
  setTimeout(() => {
    overlay.classList.add('hidden');
    overlay.classList.remove('closing');
  }, 460);

  const appEl = app();
  appEl.classList.remove('hidden');

  scheduleSessionTimer();  // 到点自动退出登录

  const firstVisit = !sessionStorage.getItem(WELCOMED_KEY);
  if (firstVisit) sessionStorage.setItem(WELCOMED_KEY, '1');

  /* 骨架级联入场；路由同时启动，首屏数据在遮罩背后加载 */
  appEl.classList.add('first-enter');
  setTimeout(() => appEl.classList.remove('first-enter'), 1500);

  if (!document.getElementById('view-scroll').children.length || !document.querySelector('.view.active')) {
    startRouterOnce();
  }

  if (firstVisit) {
    const welcome = document.createElement('div');
    welcome.className = 'welcome-overlay';
    welcome.innerHTML = `
      <div class="welcome-logo">A</div>
      <h1 class="welcome-title">欢迎回来</h1>
      <p class="welcome-sub">ATRI 管理控制台</p>`;
    document.body.appendChild(welcome);
    mountLogoImage(welcome.querySelector('.welcome-logo'));

    setTimeout(() => {
      welcome.classList.add('iris-out');
      welcome.addEventListener('animationend', () => welcome.remove(), { once: true });
      /* 兜底：动画事件未触发时也要移除节点 */
      setTimeout(() => welcome.remove(), 800);
    }, 830);
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
  const fromLoginForm = !loginOverlay().classList.contains('hidden');
  btn.classList.add('loading');
  stopLockCountdown();
  try {
    await api.get('/status');
    if (fromLoginForm) {
      /* 手动登录：先给成功反馈，再进入欢迎编排 */
      loginSuccessState();
      setTimeout(showApp, 420);
    } else {
      /* 存储令牌自动进入：不加等待，直接进应用（轻量级联） */
      showApp();
    }
  } catch (e) {
    btn.classList.remove('loading');
    if (e.status === 429) {
      /* 锁定只拦错误令牌：探测/输入的令牌已确认无效，清除存储，
         避免之后每次刷新页面都自动重试、在锁过期后继续累积失败次数 */
      setToken('');
      showLogin();
      startLockCountdown(e.retryAfter || 60);
    } else if (e.status === 401) {
      setToken('');
      showLogin('会话已失效，请重新输入访问令牌');
    } else if (e.message.includes('令牌') || e.message.includes('会话')) {
      setToken('');
      showLogin('会话已失效，请重新输入访问令牌');
    } else {
      showLogin(`无法连接面板服务：${e.message}`);
    }
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
      await api.logout();  // 吊销服务端会话（失败不影响本地登出）
      setToken('');
      showLogin();
      return;
    }
    if (action === 'stop') {
      const ok = await confirmDialog({
        ...STOP_SERVICE_CONFIRM,
        confirmText: '停止',
        danger: true,
      });
      if (!ok) return;
      await stopAndWait();
    }
  });
}

/* ---------- 初始化 ---------- */

function bindChrome() {
  document.getElementById('login-btn').addEventListener('click', async () => {
    const token = document.getElementById('access-token').value.trim();
    if (!token) { showLogin('请输入访问令牌'); return; }
    const btn = document.getElementById('login-btn');
    btn.classList.add('loading');
    stopLockCountdown();
    try {
      const session = await api.login(token);  // 访问令牌 → 短期会话令牌
      setSession(session.session_token, session.expires_in);
      document.getElementById('access-token').value = '';  // 不在输入框里保留口令
      checkAuth();  // 用会话令牌探针进入应用（保留成功态与欢迎编排）
    } catch (e) {
      btn.classList.remove('loading');
      if (e.status === 429) {
        startLockCountdown(e.retryAfter || 60);
      } else if (e.status === 401) {
        showLogin(e.message || '访问令牌无效，请重新输入');  // 服务端会附剩余尝试次数
      } else {
        showLogin(`无法连接面板服务：${e.message}`);
      }
    }
  });
  document.getElementById('access-token').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') document.getElementById('login-btn').click();
  });

  document.getElementById('btn-theme').addEventListener('click', toggleTheme);

  document.getElementById('btn-sidebar-toggle').addEventListener('click', () => {
    app().classList.toggle('sidebar-collapsed');
  });

  /* 小屏抽屉：默认收起；遮罩点击 / 菜单跳转 / Esc 关闭；进入小屏视口时自动收起 */
  const mobileViewport = matchMedia('(max-width: 900px)');
  const collapseSidebar = () => app().classList.add('sidebar-collapsed');

  if (mobileViewport.matches) collapseSidebar();
  mobileViewport.addEventListener('change', (e) => { if (e.matches) collapseSidebar(); });

  document.getElementById('sidebar-backdrop').addEventListener('click', collapseSidebar);
  document.querySelectorAll('.sidebar-nav .nav-item').forEach((item) => {
    item.addEventListener('click', () => { if (mobileViewport.matches) collapseSidebar(); });
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && mobileViewport.matches) collapseSidebar();
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

  onUnauthorized(() => showLogin('会话已过期，请重新输入访问令牌'));
}

initTheme();
bindChrome();
initSelectMenus();

/* 品牌位：配置目录有 ATRI-bot 图则替换字母 A（失败保留兜底） */
mountLogoImage(document.querySelector('.login-logo'));
mountLogoImage(document.querySelector('.brand-badge'));
upgradeFavicon();

if (getToken()) {
  /* 已存会话令牌：先看是否已到期，未到期直接探针进入（不回填输入框，避免令牌出现在 DOM 里） */
  const remaining = getSessionRemainingMs();
  if (remaining !== null && remaining <= 0) {
    setToken('');
    showLogin('会话已过期，请重新登录');
  } else {
    checkAuth();
  }
} else {
  showLogin();
}
