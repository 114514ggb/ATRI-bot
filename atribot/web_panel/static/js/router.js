/* hash 路由：#/view-name 注册与切换 */

import { icon, escapeHtml, showLoadingPill, hideLoadingPill } from './ui.js';

const routes = new Map();
let currentView = null;
let currentSection = null;

export function registerRoute(name, { title, init, destroy }) {
  routes.set(name, { title, init, destroy });
}

function setActiveNav(name) {
  document.querySelectorAll('.nav-item').forEach((el) => {
    el.classList.toggle('active', el.dataset.view === name);
  });
}

async function showView(name) {
  if (!routes.has(name)) name = 'dashboard';
  const route = routes.get(name);
  if (!route) return;

  /* 离开旧视图 */
  if (currentSection && currentView !== name) {
    if (currentView && routes.get(currentView)?.destroy) {
      try { routes.get(currentView).destroy(); } catch (e) { console.warn('视图销毁失败', e); }
    }
    currentSection.classList.add('leaving');
    await new Promise((r) => setTimeout(r, 150));
    currentSection.classList.remove('active', 'leaving');
  }

  currentView = name;
  const sectionId = `view-${currentView}`;

  let section = document.getElementById(sectionId);
  if (!section) {
    section = document.createElement('section');
    section.className = 'view';
    section.id = sectionId;
    document.getElementById('view-scroll').appendChild(section);
  }

  document.getElementById('view-title').textContent = route.title;
  setActiveNav(currentView);
  location.hash = `#/${currentView}`;

  /* 重新触发进入动画 */
  section.classList.remove('active');
  void section.offsetWidth; /* 重排以重启动画 */
  section.classList.add('active');

  currentSection = section;
  document.getElementById('view-scroll').scrollTop = 0;

  /* 初始化超过 600ms 仍未完成时浮出"加载中"胶囊，避免慢加载像卡死 */
  showLoadingPill();
  try {
    await route.init(section);
  } catch (e) {
    console.error(`视图 ${currentView} 初始化失败`, e);
    section.innerHTML = `<div class="notice danger">${icon('alert')}<div>加载失败：${escapeHtml(e.message)}</div></div>`;
  } finally {
    hideLoadingPill();
  }
}

export function navigate(name) {
  if (location.hash === `#/${name}`) {
    showView(name); /* 允许重复点击刷新 */
  } else {
    location.hash = `#/${name}`;
  }
}

export function startRouter() {
  window.addEventListener('hashchange', () => {
    const name = (location.hash || '#/dashboard').replace(/^#\//, '') || 'dashboard';
    showView(name);
  });

  document.querySelectorAll('.nav-item').forEach((el) => {
    el.addEventListener('click', () => navigate(el.dataset.view));
  });

  const initial = (location.hash || '#/dashboard').replace(/^#\//, '') || 'dashboard';
  showView(initial);
}
