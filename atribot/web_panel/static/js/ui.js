/* 通用 UI 工具：图标 / toast / 模态 / 确认框 / 分页 / 主题 / 骨架屏 / 动画 */

/* ---------- 内联 SVG 图标（stroke 风格） ---------- */

const ICONS = {
  gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  memory: '<path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7z"/><path d="M9 21h6"/>',
  terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  cloud: '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9z"/>',
  plug: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8z"/>',
  send: '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>',
  power: '<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>',
  refresh: '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>',
  check: '<polyline points="20 6 9 17 4 12"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  edit: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/>',
  up: '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
  down: '<path d="m19 12-7 7-7-7"/><path d="M12 5v14"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  bot: '<rect width="16" height="12" x="4" y="8" rx="2"/><path d="M12 8V4"/><circle cx="12" cy="3" r="1"/><circle cx="9" cy="14" r="1"/><circle cx="15" cy="14" r="1"/>',
  sliders: '<line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="1" x2="7" y1="14" y2="14"/><line x1="9" x2="15" y1="8" y2="8"/><line x1="17" x2="23" y1="16" y2="16"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
  menu: '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
  rollback: '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>',
  save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
  group: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  coins: '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
};

export function icon(name) {
  const body = ICONS[name] || ICONS.info;
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

/* ---------- HTML 转义 ---------- */

export function escapeHtml(unsafe) {
  if (unsafe === null || unsafe === undefined) return '';
  return String(unsafe)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/* ---------- Toast ---------- */

export function toast(message, type = 'success', duration = 3200) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const iconName = { success: 'check', error: 'alert', info: 'info' }[type] || 'info';
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `${icon(iconName)}<span>${escapeHtml(message)}</span>`;
  container.appendChild(el);

  setTimeout(() => {
    el.classList.add('out');
    setTimeout(() => el.remove(), 320);
  }, duration);
  return el;
}

/* ---------- 模态框 ---------- */

function closeModal(root) {
  const overlay = root.querySelector('.modal-overlay');
  if (!overlay) return;
  overlay.classList.add('closing');
  setTimeout(() => overlay.remove(), 210);
}

/**
 * 打开模态框
 * @returns {{ close: () => void, el: HTMLElement }}
 */
export function openModal({ title, bodyHtml, actions = [], wide = false, onClose }) {
  const root = document.getElementById('modal-root');
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';

  const btns = actions
    .map(
      (a, i) =>
        `<button class="btn ${a.class || ''}" data-action="${i}">${a.label}</button>`
    )
    .join('');

  overlay.innerHTML = `
    <div class="modal ${wide ? 'wide' : ''}">
      <div class="modal-head"><h3>${escapeHtml(title)}</h3>
        <button class="icon-btn" data-close>${icon('x')}</button></div>
      <div class="modal-body">${bodyHtml}</div>
      ${actions.length ? `<div class="modal-foot">${btns}</div>` : ''}
    </div>`;

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      close();
      return;
    }
    const closeBtn = e.target.closest('[data-close]');
    if (closeBtn) {
      close();
      return;
    }
    const btn = e.target.closest('[data-action]');
    if (btn) {
      const action = actions[Number(btn.dataset.action)];
      if (action.onClick) action.onClick({ close, el: overlay, btn });
    }
  });

  function close() {
    closeModal(root);
    if (onClose) onClose();
  }

  root.appendChild(overlay);
  return { close, el: overlay };
}

/**
 * 确认对话框
 * @returns {Promise<boolean>}
 */
export function confirmDialog({ title, message, confirmText = '确认', cancelText = '取消', danger = false }) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (val) => {
      if (!settled) {
        settled = true;
        resolve(val);
      }
    };

    openModal({
      title,
      bodyHtml: `<p style="margin:0 0 6px">${message}</p>`,
      actions: [
        { label: cancelText, class: 'ghost', onClick: ({ close }) => { finish(false); close(); } },
        {
          label: confirmText,
          class: danger ? 'danger' : 'primary',
          onClick: ({ close }) => {
            finish(true);
            close();
          },
        },
      ],
      onClose: () => finish(false),
    });
  });
}

/* ---------- 骨架屏 ---------- */

export function skeletonRows(n = 6, className = 'skeleton-row') {
  return Array.from({ length: n }, () => `<div class="skeleton ${className}"></div>`).join('');
}

/* ---------- 全局加载反馈：顶部进度条 / 慢加载胶囊 ---------- */

const loadbarState = { el: null, timer: null, hideTimer: null, active: 0 };

function loadbarEl() {
  if (!loadbarState.el || !loadbarState.el.isConnected) {
    const el = document.createElement('div');
    el.className = 'loadbar';
    document.body.appendChild(el);
    loadbarState.el = el;
  }
  return loadbarState.el;
}

/** 请求开始时调用（与 loadbarEnd 严格配对）；并发请求只在首尾驱动进度条 */
export function loadbarBegin() {
  loadbarState.active += 1;
  if (loadbarState.active > 1) return;
  clearTimeout(loadbarState.hideTimer);
  clearInterval(loadbarState.timer);
  const el = loadbarEl();
  el.style.opacity = '1';
  el.style.width = '0%';
  requestAnimationFrame(() => { el.style.width = '14%'; });
  /* 等待期间缓慢推进并封顶 85%，完成感留给真实结束 */
  loadbarState.timer = setInterval(() => {
    const cur = parseFloat(el.style.width) || 0;
    if (cur < 85) el.style.width = `${Math.min(cur + Math.max(0.6, (85 - cur) * 0.1), 85)}%`;
  }, 260);
}

export function loadbarEnd() {
  loadbarState.active = Math.max(0, loadbarState.active - 1);
  if (loadbarState.active > 0) return;
  clearInterval(loadbarState.timer);
  const el = loadbarState.el;
  if (!el) return;
  el.style.width = '100%';
  loadbarState.hideTimer = setTimeout(() => {
    el.style.opacity = '0';
    setTimeout(() => { if (!loadbarState.active) el.style.width = '0%'; }, 320);
  }, 160);
}

let loadingPillEl = null;
let loadingPillTimer = null;

/** 延迟 delayMs 后浮出"加载中"胶囊；快于延迟的加载不出现，避免闪烁 */
export function showLoadingPill(text = '加载中…', delayMs = 600) {
  clearTimeout(loadingPillTimer);
  hideLoadingPill();
  loadingPillTimer = setTimeout(() => {
    loadingPillEl?.remove();
    loadingPillEl = document.createElement('div');
    loadingPillEl.className = 'loading-pill';
    loadingPillEl.innerHTML = `<span class="spinner-sm"></span><span>${escapeHtml(text)}</span>`;
    document.body.appendChild(loadingPillEl);
  }, delayMs);
}

export function hideLoadingPill() {
  clearTimeout(loadingPillTimer);
  loadingPillTimer = null;
  if (loadingPillEl) {
    const el = loadingPillEl;
    loadingPillEl = null;
    el.classList.add('out');
    setTimeout(() => el.remove(), 260);
  }
}

/* ---------- 分页组件 ---------- */

/**
 * 渲染分页控件到容器
 * @param {HTMLElement} container 目标容器（需已有 .pagination 或单独 div）
 * @param {{page:number,total:number,limit:number}} state
 * @param {(page:number,limit:number)=>void} onChange
 */
export function renderPagination(container, { page, total, limit }, onChange) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const current = Math.min(Math.max(1, page), totalPages);

  const window_ = [];
  const add = (p) => { if (p >= 1 && p <= totalPages && !window_.includes(p)) window_.push(p); };
  add(1); add(totalPages);
  for (let p = current - 2; p <= current + 2; p++) add(p);
  window_.sort((a, b) => a - b);

  let btns = '';
  let prev = 0;
  for (const p of window_) {
    if (p - prev > 1) btns += '<span class="muted" style="padding:0 2px">…</span>';
    btns += `<button class="page-btn ${p === current ? 'active' : ''}" data-page="${p}">${p}</button>`;
    prev = p;
  }

  container.innerHTML = `
    <span class="page-info">共 ${total.toLocaleString()} 条 · ${totalPages} 页</span>
    <div class="page-btns">
      <button class="page-btn" data-page="${current - 1}" ${current <= 1 ? 'disabled' : ''}>‹</button>
      ${btns}
      <button class="page-btn" data-page="${current + 1}" ${current >= totalPages ? 'disabled' : ''}>›</button>
      <span class="page-info">跳至</span>
      <input class="page-jump" type="number" min="1" max="${totalPages}" value="${current}">
      <span class="page-info">页</span>
      <select class="page-size">
        ${[10, 20, 50, 100].map((n) => `<option value="${n}" ${n === limit ? 'selected' : ''}>${n} 条/页</option>`).join('')}
      </select>
    </div>`;

  container.querySelectorAll('[data-page]').forEach((btn) => {
    btn.addEventListener('click', () => onChange(Number(btn.dataset.page), limit));
  });
  const jump = container.querySelector('.page-jump');
  jump.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const p = Math.min(Math.max(1, Number(jump.value) || 1), totalPages);
      onChange(p, limit);
    }
  });
  container.querySelector('.page-size').addEventListener('change', (e) => onChange(1, Number(e.target.value)));
}

/* ---------- 数字滚动动画 ---------- */

export function countUp(el, target, { duration = 750, formatter = null } = {}) {
  const start = performance.now();
  const from = 0;
  const fmt = formatter || ((v) => Math.round(v).toLocaleString());

  function frame(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = fmt(from + (target - from) * eased);
    if (t < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

/* ---------- 主题 ---------- */

const THEME_KEY = 'atri_theme';

export function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const theme = saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  applyTheme(theme);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
}

/* 主题切换：以按钮为圆心的圆形揭示（View Transitions + clip-path）
   节奏先慢后快：前半程缓缓扩散，尾段加速铺满（900ms）
   不支持的浏览器退化为原来的直接切换（body 的颜色 transition 提供柔和过渡） */
export function toggleTheme() {
  const root = document.documentElement;
  const next = (root.getAttribute('data-theme') || 'light') === 'dark' ? 'light' : 'dark';

  if (!document.startViewTransition) {
    applyTheme(next);
    return;
  }

  /* 圆心取主题按钮中心（键盘触发也有落点），半径覆盖到最远的屏幕角落 */
  const btn = document.getElementById('btn-theme');
  const rect = btn ? btn.getBoundingClientRect() : { left: innerWidth / 2 - 18, top: 18, width: 36, height: 36 };
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;
  const endRadius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));

  /* 快照前冻结所有颜色过渡，否则新主题快照会拍到还在过渡中的旧颜色 */
  root.classList.add('theme-switching');
  const vt = document.startViewTransition(() => applyTheme(next));
  vt.finished.finally(() => root.classList.remove('theme-switching'));

  vt.ready
    .then(() => {
      root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${endRadius}px at ${x}px ${y}px)`] },
        { duration: 900, easing: 'cubic-bezier(0.6, 0.05, 0.95, 0.5)', pseudoElement: '::view-transition-new(root)' }
      );
    })
    .catch(() => { /* 过渡被跳过时主题已同步切换，无需处理 */ });
}

/* ---------- 自定义下拉菜单：接管全部原生 <select> 的弹出层 ----------
   原生 select 原地保留，继续充当触发器与数据源（值、input/change 事件、
   动态重建选项全部沿用原生行为），仅在 mousedown 时拦截浏览器默认弹层，
   改为渲染与面板风格一致的自定义菜单。菜单每次打开都从 select 当前的
   options 重建，因此动态刷新选项的页面（配置级联、SQL 历史、分页）无需
   任何适配。 */

let ddMenuEl = null; /* 当前弹层元素 */
let ddOwner = null;  /* 打开弹层的 select */
let ddIndex = -1;    /* 键盘高亮项在 options 中的下标 */

function closeSelectMenu() {
  if (!ddMenuEl) return;
  const el = ddMenuEl;
  ddMenuEl = null;
  ddOwner?.classList.remove('dd-open');
  ddOwner?.removeAttribute('aria-expanded');
  ddOwner = null;
  ddIndex = -1;
  el.classList.add('closing');
  setTimeout(() => el.remove(), 140);
}

function ddPick(index) {
  const sel = ddOwner;
  if (!sel) return;
  closeSelectMenu();
  sel.focus();
  if (sel.selectedIndex === index) return;
  sel.selectedIndex = index;
  sel.dispatchEvent(new Event('input', { bubbles: true }));
  sel.dispatchEvent(new Event('change', { bubbles: true }));
}

function ddMoveHighlight(key) {
  const sel = ddOwner;
  const menu = ddMenuEl;
  if (!sel || !menu) return;
  const opts = [...sel.options];
  const enabled = opts.map((_, i) => i).filter((i) => !opts[i].disabled);
  if (!enabled.length) return;
  if (key === 'Home') ddIndex = enabled[0];
  else if (key === 'End') ddIndex = enabled[enabled.length - 1];
  else {
    const pos = enabled.indexOf(ddIndex);
    const dir = key === 'ArrowDown' ? 1 : -1;
    ddIndex = enabled[Math.max(0, Math.min(enabled.length - 1, pos < 0 ? 0 : pos + dir))];
  }
  menu.querySelectorAll('.dd-item').forEach((el) =>
    el.classList.toggle('active', Number(el.dataset.i) === ddIndex));
  menu.querySelector(`.dd-item[data-i="${ddIndex}"]`)?.scrollIntoView({ block: 'nearest' });
}

function openSelectMenu(sel) {
  closeSelectMenu();
  const opts = [...sel.options];
  if (!opts.length) return;

  const menu = document.createElement('div');
  menu.className = 'dd-menu';
  menu.setAttribute('role', 'listbox');
  menu.innerHTML = opts.map((o, i) => `
    <button type="button" tabindex="-1" role="option" data-i="${i}"
      class="dd-item${o.selected ? ' selected' : ''}${o.disabled ? ' disabled' : ''}"
      title="${escapeHtml(o.textContent)}">
      <span class="dd-label">${escapeHtml(o.textContent)}</span>${icon('check')}
    </button>`).join('');

  const rect = sel.getBoundingClientRect();
  menu.style.minWidth = `${Math.round(rect.width)}px`;
  document.body.appendChild(menu);

  /* 定位：默认在触发器下方展开；下方空间不足且上方更宽裕时翻到上方 */
  const mRect = menu.getBoundingClientRect();
  const gap = 6;
  const roomBelow = innerHeight - rect.bottom;
  const openUp = mRect.height + gap > roomBelow && rect.top > roomBelow;
  const top = openUp ? rect.top - mRect.height - gap : rect.bottom + gap;
  menu.style.top = `${Math.max(gap, Math.min(top, innerHeight - mRect.height - gap))}px`;
  menu.style.left = `${Math.max(gap, Math.min(rect.left, innerWidth - mRect.width - gap))}px`;

  menu.addEventListener('click', (e) => {
    const item = e.target.closest('.dd-item');
    if (item && !item.classList.contains('disabled')) ddPick(Number(item.dataset.i));
  });

  ddMenuEl = menu;
  ddOwner = sel;
  ddIndex = sel.selectedIndex;
  sel.classList.add('dd-open');
  sel.setAttribute('aria-expanded', 'true');
  menu.querySelector('.dd-item.selected')?.scrollIntoView({ block: 'nearest' });
}

export function initSelectMenus() {
  document.addEventListener('mousedown', (e) => {
    /* 菜单内部的按下交给菜单自身的 click 处理 */
    if (ddMenuEl && ddMenuEl.contains(e.target)) return;
    const sel = e.target.closest('select');
    if (!sel || sel.disabled || sel.multiple || sel.size > 1) return;
    e.preventDefault(); /* 阻止浏览器展开原生弹层 */
    if (ddOwner === sel) closeSelectMenu(); /* 再点一次触发器 = 收起 */
    else openSelectMenu(sel);
    sel.focus();
  });

  document.addEventListener('keydown', (e) => {
    if (ddMenuEl) {
      if (e.key === 'Escape' || e.key === 'Tab') { closeSelectMenu(); return; }
      if (['Enter', ' ', 'ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) {
        e.preventDefault();
        if ((e.key === 'Enter' || e.key === ' ') && ddIndex >= 0) ddPick(ddIndex);
        else ddMoveHighlight(e.key);
      }
      return;
    }
    const sel = e.target;
    if (sel instanceof HTMLSelectElement && !sel.disabled && !sel.multiple && sel.size <= 1 &&
        ['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(e.key)) {
      e.preventDefault();
      openSelectMenu(sel);
      sel.focus();
    }
  });

  /* 页面滚动会让弹层脱离触发器，直接收起（弹层自身内部滚动除外） */
  window.addEventListener('scroll', (e) => {
    if (ddMenuEl && !ddMenuEl.contains(e.target)) closeSelectMenu();
  }, { capture: true, passive: true });

  window.addEventListener('resize', closeSelectMenu);
  document.addEventListener('blur', (e) => {
    /* 焦点移入弹层内部（点选 dd-item 时按钮会抢走焦点）不算离开，收起会让 click 落空、选项永远点不中 */
    if (ddMenuEl && e.target === ddOwner && !(e.relatedTarget && ddMenuEl.contains(e.relatedTarget))) closeSelectMenu();
  }, true);
}

/* ---------- 输入建议弹层（autocomplete）：文本框的 themed 建议列表 ----------
   复用 .dd-menu 样式，不接管输入框本身。getItems(query) 返回 [{ value, label, desc }]；
   选中后写回 input 并派发 input 事件，由页面自身的 input 监听做后续联动
   （如键名命中已知参数时升级值控件）。 */

const sgBound = new WeakSet();

export function attachSuggest(input, getItems) {
  if (sgBound.has(input)) return;
  sgBound.add(input);

  let menu = null;
  let items = [];
  let idx = -1;

  const close = () => {
    if (!menu) return;
    const el = menu;
    menu = null;
    items = [];
    idx = -1;
    el.classList.add('closing');
    setTimeout(() => el.remove(), 140);
  };

  const highlight = () => {
    if (!menu) return;
    menu.querySelectorAll('.dd-item').forEach((el) => el.classList.toggle('active', Number(el.dataset.i) === idx));
    menu.querySelector(`.dd-item[data-i="${idx}"]`)?.scrollIntoView({ block: 'nearest' });
  };

  const refresh = () => {
    /* 整行被重渲染（input 已脱离文档）时不再弹建议，避免孤儿弹层 */
    if (!input.isConnected) { close(); return; }
    items = getItems(input.value) || [];
    if (!items.length) { close(); return; }
    if (!menu) {
      menu = document.createElement('div');
      menu.className = 'dd-menu sg-menu';
      menu.setAttribute('role', 'listbox');
      /* 按下不转移焦点：input 保持焦点，blur 关闭逻辑不会误触发，click 也不会落空 */
      menu.addEventListener('mousedown', (e) => e.preventDefault());
      menu.addEventListener('click', (e) => {
        const item = e.target.closest('.dd-item');
        if (item) pick(Number(item.dataset.i));
      });
      document.body.appendChild(menu);
    }
    menu.innerHTML = items.map((it, i) => `
      <button type="button" tabindex="-1" role="option" data-i="${i}" class="dd-item" title="${escapeHtml(it.label)}">
        <span class="dd-label">${escapeHtml(it.label)}</span>
        ${it.desc ? `<span class="dd-desc">${escapeHtml(it.desc)}</span>` : ''}
      </button>`).join('');

    const rect = input.getBoundingClientRect();
    menu.style.minWidth = `${Math.round(rect.width)}px`;
    const mRect = menu.getBoundingClientRect();
    const gap = 6;
    const roomBelow = innerHeight - rect.bottom;
    const openUp = mRect.height + gap > roomBelow && rect.top > roomBelow;
    const top = openUp ? rect.top - mRect.height - gap : rect.bottom + gap;
    menu.style.top = `${Math.max(gap, Math.min(top, innerHeight - mRect.height - gap))}px`;
    menu.style.left = `${Math.max(gap, Math.min(rect.left, innerWidth - mRect.width - gap))}px`;
    idx = -1;
  };

  const pick = (i) => {
    const it = items[i];
    if (!it) return;
    input.value = it.value;
    close();
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
  };

  /* 延迟一拍刷新：input 事件可能触发整行重渲染（键名命中已知参数），重渲染后本 input 已脱离文档 */
  input.addEventListener('input', () => setTimeout(refresh, 0));
  input.addEventListener('focus', refresh);
  input.addEventListener('blur', (e) => {
    if (menu && !(e.relatedTarget && menu.contains(e.relatedTarget))) close();
  });
  input.addEventListener('keydown', (e) => {
    if (menu && (e.key === 'Escape' || e.key === 'Tab')) { close(); return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!menu) refresh();
      if (!menu || !items.length) return;
      idx = idx < 0 ? (e.key === 'ArrowDown' ? 0 : items.length - 1)
        : Math.max(0, Math.min(items.length - 1, idx + (e.key === 'ArrowDown' ? 1 : -1)));
      highlight();
    } else if (e.key === 'Enter' && menu) {
      e.preventDefault();
      if (idx >= 0) pick(idx);
      else close();
    }
  });
  window.addEventListener('scroll', () => { if (menu) close(); }, { capture: true, passive: true });
  window.addEventListener('resize', close);

  /* focusin 时才绑定的情况：焦点已在本输入框上，补一次刷新把建议弹出来 */
  if (document.activeElement === input) refresh();
}

/* ---------- 防抖 ---------- */

export function debounce(fn, ms = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/* ---------- 文本截断格式化 ---------- */

export function fmtTokens(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}
