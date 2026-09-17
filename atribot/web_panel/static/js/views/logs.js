/* 视图：实时日志（WebSocket 流 + 级别过滤 + 暂停 + 关键词） */

import { logsWsUrl } from '../api.js';
import { icon, escapeHtml } from '../ui.js';

const MAX_DOM_LINES = 500;
const LEVELS = ['INFO', 'WARNING', 'ERROR', 'DEBUG'];

let ws = null;
let reconnectDelay = 1000;
let reconnectTimer = null;
let paused = false;
let autoScroll = true;
let enabledLevels = new Set(LEVELS);
let keyword = '';
let lines = []; // 全量缓存（暂停/过滤时仍保留）
let lastSeq = 0; // 已渲染的最大序号，用于跨帧去重
let running = false;

async function init(section) {
  running = true;
  lines = [];
  lastSeq = 0;
  section.innerHTML = `
    <div class="logs-toolbar">
      <span style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600">
        <span class="dot yellow" id="log-conn-dot"></span><span id="log-conn-text">连接中…</span>
      </span>
      <span class="log-level-filters">
        ${LEVELS.map((l) => `<button class="level-btn on ${l}" data-level="${l}">${l}</button>`).join('')}
      </span>
      <input class="input" id="log-search" placeholder="过滤关键词…" style="width:190px">
      <span class="spacer" style="flex:1"></span>
      <label class="check-row"><input type="checkbox" id="log-autoscroll" checked>自动滚动</label>
      <button class="btn sm ghost" id="log-pause">${icon('activity')} 暂停</button>
      <button class="btn sm ghost" id="log-clear">${icon('trash')} 清屏</button>
    </div>
    <div class="logs-box">
      <div class="logs-paused-hint hidden" id="log-paused-hint">已暂停显示（日志仍在后台接收）</div>
      <div class="logs-stream" id="log-stream"></div>
    </div>`;

  const stream = section.querySelector('#log-stream');

  section.querySelectorAll('[data-level]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const level = btn.dataset.level;
      if (enabledLevels.has(level)) enabledLevels.delete(level);
      else enabledLevels.add(level);
      btn.classList.toggle('on');
      repaint(stream);
    });
  });

  section.querySelector('#log-search').addEventListener('input', (e) => {
    keyword = e.target.value.trim().toLowerCase();
    repaint(stream);
  });

  section.querySelector('#log-autoscroll').addEventListener('change', (e) => { autoScroll = e.target.checked; });

  section.querySelector('#log-pause').addEventListener('click', (e) => {
    paused = !paused;
    e.currentTarget.innerHTML = paused ? `${icon('activity')} 继续` : `${icon('activity')} 暂停`;
    section.querySelector('#log-paused-hint').classList.toggle('hidden', !paused);
  });

  section.querySelector('#log-clear').addEventListener('click', () => {
    lines = [];
    stream.innerHTML = '';
  });

  connect(section);
}

function connect(section) {
  if (!running) return;
  const dot = section.querySelector('#log-conn-dot');
  const text = section.querySelector('#log-conn-text');
  dot.className = 'dot yellow';
  text.textContent = '连接中…';

  // 重连前先关旧连接，避免两条 WS 同时推送造成重复渲染
  if (ws) {
    try { ws.onclose = null; ws.close(); } catch { /* ignore */ }
    ws = null;
  }

  try {
    ws = new WebSocket(logsWsUrl());
  } catch {
    scheduleReconnect(section);
    return;
  }

  ws.onopen = () => {
    reconnectDelay = 1000;
    dot.className = 'dot green';
    text.textContent = '已连接';
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'history') {
        // 历史快照：全量替换并重画，天然去重
        lines = msg.items || [];
        lastSeq = lines.length ? lines[lines.length - 1].seq : 0;
        const stream = section.querySelector('#log-stream');
        if (stream) repaint(stream);
      } else if (msg.type === 'logs') {
        const fresh = (msg.items || []).filter((it) => it.seq > lastSeq);
        if (!fresh.length) return;
        lastSeq = fresh[fresh.length - 1].seq;
        lines.push(...fresh);
        if (lines.length > 5000) lines = lines.slice(lines.length - 5000);
        if (!paused) renderIncrement(section, fresh);
      }
    } catch { /* 忽略坏帧 */ }
  };

  ws.onclose = (event) => {
    if (!running) return;
    dot.className = 'dot red';
    const reason = event.code === 4401 ? '令牌无效' : event.code === 4429 ? '尝试次数过多已锁定，等待解锁' : '将自动重试';
    text.textContent = `连接断开（${reason}）`;
    // 4429 锁定期间令牌可能本就正确，保留重连：锁定过期后可自动恢复
    if (event.code !== 4401) scheduleReconnect(section);
  };

  ws.onerror = () => { /* onclose 会跟进 */ };
}

function scheduleReconnect(section) {
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    reconnectDelay = Math.min(reconnectDelay * 2, 15000);
    connect(section);
  }, reconnectDelay);
}

function shouldShow(item) {
  // CRITICAL 跟随 ERROR 开关显示
  const levelOk = enabledLevels.has(item.level) || (item.level === 'CRITICAL' && enabledLevels.has('ERROR'));
  if (!levelOk) return false;
  if (keyword) {
    const hay = `${item.name} ${item.message}`.toLowerCase();
    if (!hay.includes(keyword)) return false;
  }
  return true;
}

function logLineEl(item) {
  const el = document.createElement('div');
  el.className = `log-line ${item.level}`;
  el.innerHTML = `<span class="lt">${escapeHtml(item.time)}</span>
    <span class="ll ${escapeHtml(item.level)}">${escapeHtml(item.level)}</span>
    <span class="ln" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span>
    <span class="lm">${escapeHtml(item.message)}</span>`;
  return el;
}

function renderIncrement(section, items) {
  const stream = section.querySelector('#log-stream');
  if (!stream) return;
  const frag = document.createDocumentFragment();
  for (const item of items) {
    if (!shouldShow(item)) continue;
    frag.appendChild(logLineEl(item));
  }
  stream.appendChild(frag);
  trimDom(stream);
  if (autoScroll) stream.scrollTop = stream.scrollHeight;
}

function trimDom(stream) {
  while (stream.children.length > MAX_DOM_LINES) stream.removeChild(stream.firstChild);
}

function repaint(stream) {
  stream.innerHTML = '';
  const recent = lines.slice(-MAX_DOM_LINES);
  const frag = document.createDocumentFragment();
  for (const item of recent) {
    if (!shouldShow(item)) continue;
    frag.appendChild(logLineEl(item));
  }
  stream.appendChild(frag);
  if (autoScroll) stream.scrollTop = stream.scrollHeight;
}

function destroy() {
  running = false;
  clearTimeout(reconnectTimer);
  if (ws) { try { ws.close(); } catch { /* ignore */ } ws = null; }
}

export const logsView = { title: '实时日志', init, destroy };
