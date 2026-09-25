/* 视图：AI 聊天（SubAgentRunner 驱动的多会话流式聊天）
   分级展示：每步 = 思考过程(折叠) + 工具调用块(参数/结果) + 正文(Markdown+公式图片) */

import { api, getToken, wsUrl } from '../api.js';
import { icon, toast, escapeHtml, openModal, confirmDialog, fmtTokens, helpFold } from '../ui.js';
import { TOOL_SEARCH_BRIEF, TOOL_SEARCH_RULES, TOOL_SEARCH_HELP_LABEL } from '../copy.js';
import {
  bindChipInteractions,
  readChips,
  renderToolPresetModule,
  validatePresetPairing,
} from '../components/tool-preset-editor.js';

const SETTINGS_KEY = 'atri_chat_settings_v1';
const LAST_SESSION_KEY = 'atri_chat_last_session';
const CODECOGS = 'https://latex.codecogs.com/png.image?\\dpi{150}&space;';
const MATH_HINT = /[\\^_{}=+<>|]/;
const MAX_FORMULA_LEN = 300;

/* ---------- 模块级运行状态（destroy 时清理） ---------- */

let ws = null;
let wsOpen = false;
let wsRetry = 0;
let wsRetryTimer = null;
let destroyed = false;
let initialOpened = false;

let sectionEl = null;
let messagesEl = null;
let activeTurn = null;
let generating = false;
let currentSession = null;
let lastNonce = '';
let lastUserMeta = null;
/* 最近一条用户消息的定位信息（um_index + 原文），供助手回合的重试按钮回退引用 */

let info = { defaults: {}, webui_preset: {}, limits: {} };
let suppliers = [];
let personas = [];
let sessions = [];
let settings = { supplier: '', model: '', persona: 'none', params: null };

/* ---------- 设置持久化 ---------- */

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
    settings = { ...settings, ...saved };
  } catch { /* 忽略损坏的本地设置 */ }
  /* 旧版本的「本轮自定义工具」旁路已废弃：工具集唯一来源是 config.json 的 webui 预设 */
  delete settings.tools;
}

function saveSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  if (settings.persona === 'custom') {
    const box = sectionEl?.querySelector('#chat-custom-persona');
    if (box) localStorage.setItem(`${SETTINGS_KEY}_custom`, box.value);
  }
  updateToolsCount();
}

function customPersonaText() {
  const box = sectionEl?.querySelector('#chat-custom-persona');
  return box ? box.value.trim() : '';
}

/* 请求参数默认值取自主配置 chat_parameter */
function defaultParams() {
  const cp = info.defaults?.chat_parameter || {};
  return {
    temperature: Number(cp.temperature ?? 0.6),
    top_p: Number(cp.top_p ?? 0.9),
    max_tokens: Number(cp.max_tokens ?? 65536),
    tool_choice: cp.tool_choice || 'auto',
  };
}

function currentSettingsPayload() {
  return {
    supplier: settings.supplier,
    model: settings.model,
    persona_key: settings.persona || 'none',
    custom_persona: settings.persona === 'custom' ? customPersonaText() : '',
    params: settings.params,
  };
}

/* ---------- 轻量 Markdown + LaTeX 公式渲染（无外部依赖） ---------- */

function formulaImgHtml(latex, display) {
  const url = CODECOGS + encodeURIComponent(latex);
  return `<img class="chat-formula${display ? ' display' : ''}" src="${escapeHtml(url)}" alt="${escapeHtml(latex)}" data-latex="${escapeHtml(latex)}" loading="lazy">`;
}

/* 把非代码文本中的公式替换为占位符，占位符在行内格式化后还原为公式图片 */
function extractFormulas(text) {
  const formulas = [];
  const stash = (latex, display) => {
    formulas.push(formulaImgHtml(latex, display));
    return `\x00${formulas.length - 1}\x00`;
  };
  let out = text
    .replace(/\$\$(.+?)\$\$/gs, (_, c) => stash(c.trim(), true))
    .replace(/\\\[(.+?)\\\]/gs, (_, c) => stash(c.trim(), true))
    .replace(/\\\((.+?)\\\)/gs, (_, c) => stash(c.trim(), false))
    .replace(/\$([^$\n]+?)\$/g, (m, c) =>
      c.trim() && c.length <= MAX_FORMULA_LEN && MATH_HINT.test(c) ? stash(c.trim(), false) : m);
  return { out, formulas };
}

function inlineMd(raw) {
  const { out, formulas } = extractFormulas(raw);
  let html = escapeHtml(out);
  html = html
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*\n][^*]*?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>')
    .replace(/~~([^~\n]+)~~/g, '<del>$1</del>')
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/\x00(\d+)\x00/g, (_, i) => formulas[Number(i)] ?? '');
  return html;
}

function renderMarkdown(raw) {
  const text = String(raw ?? '');
  const parts = [];
  const lines = text.split(/\r?\n/);
  let i = 0;

  const flushParagraph = (buf) => {
    if (buf.length) parts.push(`<p>${buf.map(inlineMd).join('<br>')}</p>`);
  };

  let para = [];
  while (i < lines.length) {
    const line = lines[i];

    /* 围栏代码块 */
    const fence = line.match(/^```(\w*)\s*$/);
    if (fence) {
      flushParagraph(para); para = [];
      const code = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) { code.push(lines[i]); i += 1; }
      i += 1;
      parts.push(`<pre class="chat-code"><code>${escapeHtml(code.join('\n'))}</code></pre>`);
      continue;
    }

    if (!line.trim()) { flushParagraph(para); para = []; i += 1; continue; }

    /* 标题 / 分割线 / 引用 / 列表 / 表格 */
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushParagraph(para); para = [];
      const level = h[1].length;
      parts.push(`<div class="chat-md-h chat-md-h${level}">${inlineMd(h[2])}</div>`);
      i += 1; continue;
    }
    if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(line)) {
      flushParagraph(para); para = [];
      parts.push('<hr class="chat-md-hr">');
      i += 1; continue;
    }
    if (/^\s*>/.test(line)) {
      flushParagraph(para); para = [];
      const quote = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*>\s?/, '')); i += 1;
      }
      parts.push(`<blockquote class="chat-md-quote">${quote.map(inlineMd).join('<br>')}</blockquote>`);
      continue;
    }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      flushParagraph(para); para = [];
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items = [];
      while (i < lines.length && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*+]|\d+[.)])\s+/, '')); i += 1;
      }
      const tag = ordered ? 'ol' : 'ul';
      parts.push(`<${tag} class="chat-md-list">${items.map((it) => `<li>${inlineMd(it)}</li>`).join('')}</${tag}>`);
      continue;
    }
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      flushParagraph(para); para = [];
      const head = line.split('|').slice(1, -1).map((c) => c.trim());
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        rows.push(lines[i].split('|').slice(1, -1).map((c) => c.trim())); i += 1;
      }
      parts.push(`<table class="chat-md-table"><thead><tr>${head.map((c) => `<th>${inlineMd(c)}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${inlineMd(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`);
      continue;
    }

    para.push(line);
    i += 1;
  }
  flushParagraph(para);
  return parts.join('') || '<p class="muted">(空回复)</p>';
}

/* ---------- 基础 DOM 工具 ---------- */

function el(tag, cls, html = '') {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (html) node.innerHTML = html;
  return node;
}

/* ---------- 头像与时间戳 ---------- */

function avatarUrl() {
  return `/admin/api/chat/avatar?token=${encodeURIComponent(getToken() || '')}`;
}

/* 机器人头像：配置目录下的 ATRI-bot 图，加载失败（未配令牌/无图）回退字母 A */
function makeBotAvatar() {
  const wrap = el('div', 'chat-avatar bot-avatar');
  const img = document.createElement('img');
  img.className = 'chat-avatar-img';
  img.alt = 'ATRI';
  img.addEventListener('error', () => { img.remove(); wrap.textContent = 'A'; });
  img.src = avatarUrl();
  wrap.appendChild(img);
  return wrap;
}

/* 空状态立绘：加载成功后替换容器内的字母 A */
function mountEmptyLogo() {
  const holder = sectionEl?.querySelector('#chat-empty-logo');
  if (!holder || holder.querySelector('img')) return;
  const img = document.createElement('img');
  img.alt = 'ATRI';
  img.addEventListener('load', () => { holder.textContent = ''; holder.appendChild(img); });
  img.addEventListener('error', () => { /* 保留字母 A 兜底 */ });
  img.src = avatarUrl();
}

function pad2(n) { return String(n).padStart(2, '0'); }

/* 秒级时间戳 → 当天 HH:MM，跨天 MM-DD HH:MM；未知(0)返回空串 */
function fmtTs(ts) {
  if (!Number.isFinite(ts) || ts <= 0) return '';
  const d = new Date(ts * 1000);
  const hm = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  const now = new Date();
  if (d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()) return hm;
  return `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${hm}`;
}

/* 消息时间戳徽标（放 hover 操作行），title 给完整时间；未知时间不显示 */
function timeBadge(ts) {
  const short = fmtTs(ts);
  if (!short) return null;
  const d = new Date(ts * 1000);
  const span = el('span', 'chat-time', short);
  span.title = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  return span;
}

function userAtBottom() {
  const box = messagesEl;
  return box.scrollHeight - box.scrollTop - box.clientHeight < 90;
}

function scrollToBottom(force = false) {
  if (force || userAtBottom()) messagesEl.scrollTop = messagesEl.scrollHeight;
}

/* ---------- 消息渲染 ---------- */

function attachmentHtml(file) {
  const url = `${file.url}?token=${encodeURIComponent(getToken())}`;
  const name = escapeHtml(file.name || file.id);
  if (file.kind === 'image') {
    return `<a class="chat-attach-img-link" href="${url}" target="_blank" rel="noopener" title="查看/下载原图：${name}"><img class="chat-attach-img" src="${url}" alt="${name}" loading="lazy"></a>`;
  }
  if (file.kind === 'audio') return `<audio class="chat-attach-audio" controls preload="none" src="${url}"></audio>`;
  if (file.kind === 'video') return `<video class="chat-attach-video" controls preload="metadata" src="${url}"></video>`;
  return `<a class="chat-attach-file" href="${url}" download="${name}" title="下载：${name}">${icon('file')} ${name} <span class="muted small">(${Math.ceil((file.size || 0) / 1024)} KB)</span></a>`;
}

/* 工具投递的附件卡片：进当前助手回合，无活跃回合时兜底开一个并立即收尾 */
function appendDeliveredFiles(files) {
  const append = (turn) => {
    for (const file of files || []) {
      turn.bubble.insertBefore(el('div', 'chat-attach', attachmentHtml(file)), turn.status);
    }
  };
  if (activeTurn && !activeTurn.done) { append(activeTurn); }
  else { beginAssistantTurn(lastUserMeta || {}); setGenerating(true); append(activeTurn); finishTurn('completed'); }
  scrollToBottom();
}

/* 合并转发文本（如 run_python_code 回传的代码与输出）：折叠块 */
function appendMergeText(source, message) {
  const append = (turn) => {
    const block = makeCollapsible(`<span class="chat-block-name">${escapeHtml(source || '合并消息')}</span>`, { collapsed: false, cls: 'merge' });
    const pre = el('pre', 'chat-tool-result mono');
    pre.textContent = String(message || '');
    block.querySelector('.chat-block-body').appendChild(pre);
    turn.bubble.insertBefore(block, turn.status);
  };
  if (activeTurn && !activeTurn.done) { append(activeTurn); }
  else { beginAssistantTurn(lastUserMeta || {}); setGenerating(true); append(activeTurn); finishTurn('completed'); }
  scrollToBottom();
}

/* 独立文本气泡（send_private_msg / 音乐卡片之类的附注） */
function appendAssistantNote(text) {
  messagesEl.querySelector('.chat-empty')?.remove();
  const row = el('div', 'chat-msg assistant');
  const bubble = el('div', 'chat-bubble chat-assistant-bubble');
  bubble.appendChild(el('div', 'chat-content chat-md', renderMarkdown(String(text || ''))));
  row.appendChild(makeBotAvatar());
  row.appendChild(bubble);
  const now = new Date();
  row.title = `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())} ${pad2(now.getHours())}:${pad2(now.getMinutes())}`;
  messagesEl.appendChild(row);
  scrollToBottom();
}

function appendUserMessage(text, files = [], nonce = '', ts = 0) {
  messagesEl.querySelector('.chat-empty')?.remove();
  const row = el('div', 'chat-msg user');
  const bubble = el('div', 'chat-bubble');
  if (text) bubble.appendChild(el('div', 'chat-text', escapeHtml(text)));
  for (const file of files) bubble.appendChild(el('div', 'chat-attach', attachmentHtml(file)));
  const actions = el('div', 'chat-msg-actions');
  const badge = timeBadge(ts);
  if (badge) actions.appendChild(badge);
  const editBtn = el('button', 'chat-msg-action', `${icon('edit')} 编辑`);
  editBtn.type = 'button';
  editBtn.title = '编辑此消息并回退后续对话';
  editBtn.addEventListener('click', () => startEditMessage(row));
  actions.appendChild(editBtn);
  bubble.appendChild(actions);
  row.appendChild(el('div', 'chat-avatar user-avatar', '我'));
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
}

/* 内联编辑用户消息：保存并重发 / 仅回退 / 取消 */
function startEditMessage(row) {
  if (generating) { toast('请等待生成完成后再编辑', 'error'); return; }
  if (row.querySelector('.chat-edit-box')) return;
  const umIndex = [...messagesEl.querySelectorAll('.chat-msg.user')].indexOf(row);
  if (umIndex < 0) return;
  const bubble = row.querySelector('.chat-bubble');
  const original = bubble.querySelector('.chat-text')?.textContent || '';
  for (const child of [...bubble.children]) child.style.display = 'none';

  const box = el('div', 'chat-edit-box');
  box.innerHTML = `
    <textarea class="input mono" rows="3"></textarea>
    <div class="chat-edit-actions">
      <button type="button" class="btn sm primary" data-act="resend">${icon('refresh')} 保存并重发</button>
      <button type="button" class="btn sm ghost" data-act="revert">${icon('rollback')} 仅回退</button>
      <button type="button" class="btn sm ghost" data-act="cancel">取消</button>
    </div>`;
  const ta = box.querySelector('textarea');
  ta.value = original;
  bubble.prepend(box);
  ta.focus();
  ta.style.height = 'auto';
  ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;

  const close = () => {
    box.remove();
    for (const child of [...bubble.children]) child.style.display = '';
  };

  box.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const act = btn.dataset.act;
    if (act === 'cancel') { close(); return; }
    const ok = sendWs({
      type: 'edit',
      session: currentSession,
      um_index: umIndex,
      text: ta.value.trim(),
      resend: act === 'resend',
      settings: currentSettingsPayload(),
    });
    if (!ok) return;
    /* 成功后服务端会广播 history 整体重绘；重发路径的事件流随后到达 */
    close();
    if (act === 'resend') {
      beginAssistantTurn();
      setGenerating(true);
    }
  });
}

/* 工具/思考折叠块 */
function makeCollapsible(titleHtml, { collapsed = true, cls = '' } = {}) {
  const block = el('div', `chat-block ${cls}`);
  block.innerHTML = `
    <button type="button" class="chat-block-head">
      <span class="chat-block-chevron">${icon('down')}</span>
      <span class="chat-block-title">${titleHtml}</span>
    </button>
    <div class="chat-block-body"></div>`;
  const head = block.querySelector('.chat-block-head');
  head.addEventListener('click', () => {
    block.classList.toggle('collapsed');
    if (block.classList.contains('collapsed')) scrollToBottom();
  });
  if (collapsed) block.classList.add('collapsed');
  return block;
}

function beginAssistantTurn(meta = {}) {
  messagesEl.querySelector('.chat-empty')?.remove();
  const row = el('div', 'chat-msg assistant');
  const bubble = el('div', 'chat-bubble chat-assistant-bubble');
  const avatar = makeBotAvatar();
  /* 生成中呼吸光圈（历史重放不算） */
  if (!meta.replay) avatar.classList.add('speaking');
  row.appendChild(avatar);
  row.appendChild(bubble);
  const status = el('div', 'chat-turn-status', '<span class="spinner-sm"></span> 生成中…');
  bubble.appendChild(status);
  messagesEl.appendChild(row);
  scrollToBottom(true);

  activeTurn = {
    root: row,
    bubble,
    avatar,
    status,
    steps: new Map(),
    /* 工具块按 tool_call_id 全回合键控：流式 START 与其 RESULT/STEP_SUMMARY
       分属相邻两个 step_index（runner 步计数器在流结束后自增），按步骤分组会重复建块 */
    tools: new Map(),
    reasonings: [],
    done: false,
    /* 回合元信息：计时 + 重试定位（umIndex 指向本轮用户消息，重试 = edit 同文重发） */
    startedAt: performance.now(),
    firstTokenAt: null,
    stopping: false,
    timer: null,
    finishInfo: null,
    actionsRow: null,
    umIndex: meta.umIndex ?? null,
    userText: meta.userText ?? '',
    historyText: meta.historyText || '',
    replay: Boolean(meta.replay),
    /* 回合时间戳（秒）：历史条目带真实时间；live 回合在 finishTurn 用本地时钟 */
    ts: Number(meta.ts) || 0,
    finishTs: 0,
  };
  activeTurn.timer = setInterval(() => {
    if (activeTurn.done || activeTurn.stopping) return;
    const secs = ((performance.now() - activeTurn.startedAt) / 1000).toFixed(1);
    activeTurn.status.innerHTML = `<span class="spinner-sm"></span> 生成中 ${secs}s`;
  }, 200);
}

function stepOf(turn, stepIndex) {
  let step = turn.steps.get(stepIndex);
  if (step) return step;
  const node = el('div', 'chat-step');
  let sep = null;
  if (turn.steps.size > 0) {
    sep = el('div', 'chat-step-sep', `第 ${stepIndex + 1} 步`);
    node.appendChild(sep);
  }
  turn.bubble.insertBefore(node, turn.status);
  step = { node, sep, created: performance.now(), reasoning: null, reasoningText: '', content: null, contentRaw: '', meta: null, renderPending: false };
  turn.steps.set(stepIndex, step);
  return step;
}

function reasoningBlock(turn, step) {
  if (step.reasoning) return step.reasoning;
  const block = makeCollapsible('<span class="chat-block-name">思考过程</span><span class="chat-reasoning-hint"></span>', { collapsed: false, cls: 'reasoning' });
  step.node.appendChild(block);
  step.reasoning = {
    block,
    body: block.querySelector('.chat-block-body'),
    hint: block.querySelector('.chat-reasoning-hint'),
  };
  turn.reasonings.push(step.reasoning);
  return step.reasoning;
}

function contentBlock(step) {
  if (step.content) return step.content;
  const node = el('div', 'chat-content chat-md');
  step.node.appendChild(node);
  step.content = node;
  return step.content;
}

function scheduleContentRender(step) {
  if (step.renderPending) return;
  step.renderPending = true;
  requestAnimationFrame(() => {
    step.renderPending = false;
    const node = contentBlock(step);
    if (node.isConnected) {
      node.innerHTML = renderMarkdown(step.contentRaw);
      scrollToBottom();
    }
  });
}

function flushContentRender(turn) {
  /* 收尾时对全部步骤做最终渲染，防 rAF 被打断（如标签页切走）丢正文 */
  for (const step of turn.steps.values()) {
    if (step.contentRaw && !step.renderPending) {
      contentBlock(step).innerHTML = renderMarkdown(step.contentRaw);
    }
  }
}

function toolBlock(turn, step, toolCallId, toolName) {
  let tool = turn.tools.get(toolCallId);
  if (tool) return tool;
  const block = makeCollapsible(
    `<span class="chat-block-name mono">${escapeHtml(toolName || toolCallId)}</span><span class="chat-tool-status running">运行中…</span>`,
    { collapsed: true, cls: 'tool' },
  );
  block.querySelector('.chat-block-body').innerHTML = `
    <div class="chat-tool-section"><div class="chat-tool-label">参数</div><pre class="chat-tool-args mono">-</pre></div>
    <div class="chat-tool-section"><div class="chat-tool-label">结果</div><pre class="chat-tool-result mono">…</pre></div>`;
  step.node.appendChild(block);
  tool = {
    block,
    status: block.querySelector('.chat-tool-status'),
    args: block.querySelector('.chat-tool-args'),
    result: block.querySelector('.chat-tool-result'),
  };
  turn.tools.set(toolCallId, tool);
  scrollToBottom();
  return tool;
}

function setToolResult(tool, result, isError) {
  tool.status.textContent = isError ? '出错' : '完成';
  tool.status.classList.remove('running');
  tool.status.classList.add(isError ? 'error' : 'ok');
  const text = String(result ?? '');
  tool.result.textContent = text.length > 4000 ? `${text.slice(0, 4000)}…(已截断)` : text;
  tool.result.classList.toggle('chat-tool-error', Boolean(isError));
  scrollToBottom();
}

function prettyArgs(args) {
  if (args === undefined || args === null || args === '') return '';
  if (typeof args === 'string') {
    try { return JSON.stringify(JSON.parse(args), null, 2); } catch { return args; }
  }
  try { return JSON.stringify(args, null, 2); } catch { return String(args); }
}

/* ---------- Agent 事件驱动 ---------- */

function handleAgentEvent(event) {
  if (!activeTurn || activeTurn.done) return;
  const type = event.event_type;
  const stepIndex = event.step_index ?? 0;
  const step = stepOf(activeTurn, stepIndex);

  if (type === 'REASONING_DELTA' || type === 'TEXT_DELTA') {
    if (activeTurn.firstTokenAt == null) activeTurn.firstTokenAt = performance.now();
  }

  if (type === 'REASONING_DELTA') {
    const rs = reasoningBlock(activeTurn, step);
    step.reasoningText += event.delta || '';
    rs.body.textContent = step.reasoningText;
    rs.hint.textContent = ` · ${step.reasoningText.length} 字`;
    rs.body.parentElement.scrollTop = rs.body.parentElement.scrollHeight;
    scrollToBottom();
  } else if (type === 'TEXT_DELTA') {
    /* 思考块在正文开始输出后折叠（与工具调用到达时一致） */
    if (step.reasoning && !step.reasoning.block.classList.contains('collapsed')) {
      step.reasoning.block.classList.add('collapsed');
    }
    step.contentRaw += event.delta || '';
    scheduleContentRender(step);
  } else if (type === 'TOOL_CALL_START') {
    /* 思考块在首个工具调用/正文出现后折叠 */
    if (step.reasoning && !step.reasoning.block.classList.contains('collapsed')) {
      step.reasoning.block.classList.add('collapsed');
    }
    toolBlock(activeTurn, step, event.tool_call_id || event.tool_name, event.tool_name);
  } else if (type === 'TOOL_CALL_RESULT') {
    const tool = toolBlock(activeTurn, step, event.tool_call_id || event.tool_name, event.tool_name);
    setToolResult(tool, event.result, event.is_error);
  } else if (type === 'STEP_SUMMARY') {
    /* 用完整参数补齐流式期间为空的工具参数 */
    for (const tc of event.tool_calls || []) {
      const id = tc.id || tc.name;
      const tool = activeTurn.tools.get(id);
      if (tool) {
        tool.args.textContent = prettyArgs(tc.arguments);
        if (tc.result !== undefined && tool.status.classList.contains('running')) {
          setToolResult(tool, tc.result, tc.is_error);
        }
      }
    }
    if (step.sep && step.created) {
      const secs = ((performance.now() - step.created) / 1000).toFixed(1);
      step.sep.textContent = `第 ${stepIndex + 1} 步 · ${secs}s`;
    }
    for (const rs of activeTurn.reasonings) rs.block.classList.add('collapsed');
    const usage = event.usage;
    if (usage && usage.total_tokens) {
      step.meta = el('div', 'chat-step-meta', `${fmtTokens(usage.total_tokens)} tokens`);
      step.node.appendChild(step.meta);
    }
  } else if (type === 'RUN_SUMMARY') {
    finishTurn(event.finish_reason || 'completed', event.total_usage);
  } else if (type === 'ERROR') {
    activeTurn.bubble.appendChild(el('div', 'chat-error', `${icon('alert')} ${escapeHtml(event.error_message || '未知错误')}`));
    finishTurn('error');
  }
}

function turnPlainText(turn) {
  const live = [...turn.steps.values()].map((s) => s.contentRaw || '').join('').trim();
  return live || turn.historyText || '';
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    /* 非 secure context 兜底 */
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      ta.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

/* 助手回合收尾操作行：时间戳 + 复制全文 / 回退到本轮用户消息重试（复用 edit 重发通道） */
function appendTurnActions(turn) {
  if (turn.actionsRow) return;
  const actions = el('div', 'chat-msg-actions');

  const badge = timeBadge(turn.finishTs);
  if (badge) actions.appendChild(badge);

  const copyBtn = el('button', 'chat-msg-action', `${icon('copy')} 复制`);
  copyBtn.type = 'button';
  copyBtn.title = '复制本回合回复全文';
  copyBtn.addEventListener('click', async () => {
    const text = turnPlainText(turn);
    if (!text) { toast('本回合没有可复制的文本', 'error'); return; }
    const ok = await copyText(text);
    toast(ok ? '已复制回复全文' : '复制失败', ok ? 'success' : 'error');
  });
  actions.appendChild(copyBtn);

  if (turn.umIndex != null) {
    const retryBtn = el('button', 'chat-msg-action', `${icon('refresh')} 重试`);
    retryBtn.type = 'button';
    retryBtn.title = '回退到本轮用户消息并重新生成';
    retryBtn.addEventListener('click', () => {
      if (generating) { toast('请等待生成完成后再重试', 'error'); return; }
      if (!sendWs({
        type: 'edit',
        session: currentSession,
        um_index: turn.umIndex,
        text: turn.userText,
        resend: true,
        settings: currentSettingsPayload(),
      })) return;
      /* 同文重发：服务端截断后广播 history 重绘，随后事件流开启新回合 */
    });
    actions.appendChild(retryBtn);
  }

  turn.bubble.appendChild(actions);
  turn.actionsRow = actions;
}

function renderTurnStatus(turn) {
  const info = turn.finishInfo || {};
  const label = {
    completed: '完成',
    max_turns: '达到最大步数',
    error: '出错终止',
    stopped: '已停止',
  }[info.reason] || info.reason || '完成';
  const parts = [];
  if (info.firstTokenMs != null) parts.push(`首字 ${(info.firstTokenMs / 1000).toFixed(1)}s`);
  if (info.duration != null) parts.push(`${Number(info.duration).toFixed(1)}s`);
  if (info.usage && info.usage.total_tokens) parts.push(`${fmtTokens(info.usage.total_tokens)} tokens`);
  turn.status.innerHTML = `${icon('check')} ${escapeHtml(label)}${parts.length ? ` · ${parts.join(' · ')}` : ''}`;
  turn.status.classList.add('done');
}

function finishTurn(reason, usage, duration, ts) {
  if (!activeTurn) return;
  activeTurn.done = true;
  if (activeTurn.timer) clearInterval(activeTurn.timer);
  activeTurn.avatar?.classList.remove('speaking');
  flushContentRender(activeTurn);
  /* 历史重放没有真实回合计时（如进程重启后从库恢复），不显示耗时 */
  const elapsed = duration != null ? duration
    : (activeTurn.replay ? null : (performance.now() - activeTurn.startedAt) / 1000);
  /* 完成时间：显式 ts（done 广播/历史条目）> 回合起始 ts > live 用本地时钟；历史无 ts 则不显示 */
  activeTurn.finishTs = Number(ts) || activeTurn.ts || (activeTurn.replay ? 0 : Date.now() / 1000);
  activeTurn.finishInfo = {
    reason: reason || 'completed',
    usage,
    duration: elapsed,
    firstTokenMs: activeTurn.firstTokenAt != null ? activeTurn.firstTokenAt - activeTurn.startedAt : null,
  };
  renderTurnStatus(activeTurn);
  appendTurnActions(activeTurn);
  setGenerating(false);
  scrollToBottom();
}

function setGenerating(value) {
  generating = value;
  const sendBtn = sectionEl?.querySelector('#chat-send');
  if (!sendBtn) return;
  if (value) {
    sendBtn.classList.add('danger');
    sendBtn.innerHTML = `${icon('x')} 停止`;
  } else {
    sendBtn.classList.remove('danger');
    sendBtn.innerHTML = `${icon('send')} 发送`;
  }
}

/* ---------- 历史恢复渲染 ---------- */

function renderHistory(items) {
  messagesEl.innerHTML = '';
  activeTurn = null;
  lastUserMeta = null;
  let userCount = 0;
  let prevUserText = '';
  for (const item of items || []) {
    if (item.type === 'user') {
      appendUserMessage(item.text || '', item.files || [], item.nonce || '', Number(item.ts) || 0);
      userCount += 1;
      prevUserText = item.text || '';
    } else if (item.type === 'assistant') {
      beginAssistantTurn({
        umIndex: userCount > 0 ? userCount - 1 : null,
        userText: prevUserText,
        historyText: item.text || '',
        replay: true,
        ts: Number(item.ts) || 0,
      });
      const step = stepOf(activeTurn, 0);
      for (const tc of item.tools || []) {
        const tool = toolBlock(activeTurn, step, tc.name, tc.name);
        const pretty = prettyArgs(tc.arguments);
        if (pretty && pretty !== '{}') tool.args.textContent = pretty;
        setToolResult(tool, tc.result, tc.is_error);
      }
      if (item.text) {
        step.contentRaw = item.text;
        contentBlock(step).innerHTML = renderMarkdown(item.text);
      }
      for (const file of item.files || []) {
        activeTurn.bubble.insertBefore(el('div', 'chat-attach', attachmentHtml(file)), activeTurn.status);
      }
      finishTurn(item.finish_reason || 'completed', item.usage, item.duration, Number(item.ts) || 0);
      activeTurn = null;
    }
  }
  if (userCount > 0) {
    lastUserMeta = { umIndex: userCount - 1, userText: prevUserText };
  }
  if (!messagesEl.children.length) {
    messagesEl.innerHTML = `
      <div class="chat-empty">
        <div class="chat-empty-logo" id="chat-empty-logo">A</div>
        <p>开始新对话吧</p>
        <p class="muted small">支持图片 / 音频 / 视频附件</p>
      </div>`;
    mountEmptyLogo();
  }
  scrollToBottom(true);
}

/* ---------- WebSocket 客户端 ---------- */

async function connectWs() {
  if (destroyed) return;
  try { ws?.close(); } catch { /* 旧连接关闭失败不影响重连 */ }

  let url;
  try {
    url = await wsUrl('/ws/chat');
  } catch {
    const delay = Math.min(15000, 1000 * Math.pow(1.6, wsRetry++));
    wsRetryTimer = setTimeout(connectWs, delay);
    return;
  }
  ws = new WebSocket(url);

  ws.addEventListener('open', () => {
    wsOpen = true;
    wsRetry = 0;
    setConnState(true);
    if (initialOpened && currentSession !== null) {
      /* 断线重连后重新同步当前会话（含可能错过的生成结果） */
      sendWs({ type: 'load', session: currentSession });
    }
    maybeOpenInitial();
  });

  ws.addEventListener('message', (e) => {
    let data;
    try { data = JSON.parse(e.data); } catch { return; }
    handleWsMessage(data);
  });

  ws.addEventListener('close', (e) => {
    wsOpen = false;
    setConnState(false);
    if (destroyed) return;
    if (e.code === 4401) { toast('聊天连接鉴权失败，请重新登录', 'error'); return; }
    if (e.code === 4429) { toast('尝试次数过多，聊天连接被锁定', 'error'); return; }
    const delay = Math.min(15000, 1000 * Math.pow(1.6, wsRetry++));
    wsRetryTimer = setTimeout(connectWs, delay);
  });

  ws.addEventListener('error', () => { /* close 会跟着触发，重连逻辑在那里 */ });
}

function sendWs(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
    return true;
  }
  /* 连接已断开（而非正在建立）：立即抢救重连，不等退避计时 */
  if (!ws || ws.readyState === WebSocket.CLOSED) {
    connectWs();
  }
  toast('聊天服务未连接，稍后重试', 'error');
  return false;
}

function handleWsMessage(data) {
  switch (data.type) {
    case 'ready':
      break;
    case 'session':
      currentSession = data.id;
      localStorage.setItem(LAST_SESSION_KEY, String(data.id));
      refreshSessions();
      break;
    case 'history':
      currentSession = data.session;
      localStorage.setItem(LAST_SESSION_KEY, String(data.session));
      renderHistory(data.items);
      if (data.running) {
        beginAssistantTurn(lastUserMeta || {});
        setGenerating(true);
      } else {
        setGenerating(false);
      }
      refreshSessions();
      break;
    case 'user_message':
      if (data.nonce && data.nonce === lastNonce) break;
      appendUserMessage(data.text || '', data.files || [], data.nonce || '', Number(data.ts) || 0);
      lastUserMeta = {
        umIndex: [...messagesEl.querySelectorAll('.chat-msg.user')].length - 1,
        userText: data.text || '',
      };
      break;
    case 'attachment':
      appendDeliveredFiles([data.file]);
      break;
    case 'merge_text':
      appendMergeText(data.source, data.message);
      break;
    case 'assistant_note':
      appendAssistantNote(data.text || '');
      break;
    case 'event':
      if (!activeTurn || activeTurn.done) beginAssistantTurn(lastUserMeta || {});
      setGenerating(true);
      handleAgentEvent(data.event);
      break;
    case 'done':
      if (activeTurn && activeTurn.done) {
        /* RUN_SUMMARY 已收尾，补记服务端统计的回合耗时 */
        if (data.duration != null && activeTurn.finishInfo) {
          activeTurn.finishInfo.duration = data.duration;
          renderTurnStatus(activeTurn);
        }
      } else {
        finishTurn(data.finish_reason || 'completed', null, data.duration, Number(data.ts) || 0);
      }
      setGenerating(false);
      refreshSessions();
      break;
    case 'busy':
      toast('该会话正在生成中，请先停止或等待完成', 'error');
      /* 编辑重发的乐观 UI 在被拒时复位 */
      if (!activeTurn || activeTurn.done) setGenerating(false);
      break;
    case 'stopping':
      if (activeTurn) {
        activeTurn.stopping = true;
        activeTurn.status.innerHTML = '<span class="spinner-sm"></span> 停止中…';
      }
      break;
    case 'deleted':
      toast(`聊天${data.session} 已删除`, 'info');
      if (data.session === currentSession) {
        currentSession = null;
        resetTurnUi();
        switchAfterDelete(data.session);
      } else {
        refreshSessions();
      }
      break;
    case 'error':
      toast(data.message || '未知错误', 'error');
      break;
    case 'pong':
      break;
    default:
      break;
  }
}

/* ---------- 会话管理（列表渲染在左侧栏 #chat-session-nav） ---------- */

async function refreshSessions() {
  try {
    const res = await api.get('/chat/sessions');
    sessions = res.items || [];
    renderSessionNav();
  } catch { /* 会话列表刷新失败不阻塞聊天 */ }
}

function renderSessionNav() {
  const nav = document.getElementById('chat-session-nav');
  if (!nav) return;
  const known = new Set(sessions.map((s) => s.id));
  if (currentSession !== null && !known.has(currentSession)) {
    sessions = [...sessions, { id: currentSession, title: '' }].sort((a, b) => a.id - b.id);
  }
  const rows = sessions.map((s) => `
    <div class="nav-sub-item ${s.id === currentSession ? 'active' : ''}" data-session="${s.id}" title="会话${s.id}${s.title ? '：' + s.title : ''}">
      ${s.running ? '<span class="spinner-sm"></span>' : ''}
      <span class="nav-sub-name">聊天${s.id}</span>
      <span class="nav-sub-title">${escapeHtml(s.title || '')}</span>
      <button class="nav-sub-del" data-del="${s.id}" title="删除该会话及其历史">${icon('trash')}</button>
    </div>`).join('');
  nav.innerHTML = `
    <div class="nav-sub-item nav-sub-new" id="chat-nav-new">${icon('plus')} 新会话</div>
    ${rows}`;

  /* 状态栏标题：当前会话 + 首条消息摘要 */
  const label = sectionEl?.querySelector('#chat-current');
  if (label) {
    const s = sessions.find((x) => x.id === currentSession);
    label.textContent = currentSession === null
      ? '正在连接…'
      : `聊天${currentSession}${s?.title ? ` · ${s.title}` : ''}`;
  }
}

/* 侧栏列表点击（元素常驻侧栏，只绑一次） */
function bindSessionNav() {
  const nav = document.getElementById('chat-session-nav');
  if (!nav || nav.dataset.bound) return;
  nav.dataset.bound = '1';
  nav.addEventListener('click', async (e) => {
    const del = e.target.closest('[data-del]');
    if (del) {
      e.stopPropagation();
      await deleteSession(Number(del.dataset.del));
      return;
    }
    if (e.target.closest('#chat-nav-new')) {
      createSession();
      collapseMobileSidebar();
      return;
    }
    const item = e.target.closest('[data-session]');
    if (item) {
      loadSession(Number(item.dataset.session));
      collapseMobileSidebar();
    }
  });
}

function collapseMobileSidebar() {
  if (matchMedia('(max-width: 900px)').matches) {
    document.getElementById('app')?.classList.add('sidebar-collapsed');
  }
}

function loadSession(id) {
  if (!sendWs({ type: 'load', session: id })) return;
  currentSession = id;
  renderSessionNav();
}

function createSession() {
  sendWs({ type: 'create' });
}

async function deleteSession(target) {
  if (target === null || target === undefined) return;
  const ok = await confirmDialog({
    title: '删除会话',
    message: `将删除会话 <b>聊天${target}</b> 的全部聊天历史（含数据库记录）。确定继续吗？`,
    confirmText: '删除',
    danger: true,
  });
  if (!ok) return;
  try {
    await api.del(`/chat/sessions/${target}`);
  } catch (e) {
    toast(`删除失败：${e.message}`, 'error');
    return;
  }
  /* deleted 广播通常已先行处理导航；WS 断线收不到时在此兜底 */
  if (currentSession === target) {
    currentSession = null;
    resetTurnUi();
    await switchAfterDelete(target);
  } else {
    await refreshSessions();
  }
}

async function switchAfterDelete(deletedId) {
  /* 切到最近的剩余会话（优先 id≥被删 id 的最小者，否则最大的），
     仅当没有剩余会话时才新建——避免立即新建拿到刚释放的最小 id，
     看起来像"删除没生效、同编号复活" */
  await refreshSessions();
  const remaining = sessions.map((s) => s.id).sort((a, b) => a - b);
  if (!remaining.length) {
    createSession();
    return;
  }
  const next = remaining.find((id) => id >= deletedId) ?? remaining[remaining.length - 1];
  loadSession(next);
}

function resetTurnUi() {
  messagesEl.innerHTML = '';
  activeTurn = null;
  setGenerating(false);
}

function maybeOpenInitial() {
  if (initialOpened || !wsOpen || !sectionEl) return;
  const bootstrapped = suppliers.length > 0;
  if (!bootstrapped) return;
  initialOpened = true;
  openInitialSession(false);
}

function openInitialSession(afterDelete) {
  const last = Number(localStorage.getItem(LAST_SESSION_KEY) || '0');
  const exists = sessions.some((s) => s.id === last);
  if (!afterDelete && exists) loadSession(last);
  else createSession();
}

/* ---------- 工具预设弹窗（编辑 config.json 的 webui 预设，与配置页「工具预设」同界面同数据） ---------- */

/* 默认预设名兜底（正常情况下由 /chat/info 的 webui_preset.name 提供） */
const FALLBACK_PRESET = 'webui';

function presetName() {
  return info.webui_preset?.name || FALLBACK_PRESET;
}

async function refreshChatInfo() {
  const res = await api.get('/chat/info');
  info = { ...info, ...res };
}

/* 弹窗内当前编辑值 → 预设取值（空 deferred 时按白名单列表保存，避免产生歧义配置） */
function presetValueFromInfo() {
  const preset = info.webui_preset || {};
  if (!preset.exists) return null; /* 缺失 → 渲染成空白名单，保存即创建 */
  const def = preset.default || [];
  const deferred = preset.deferred || [];
  return deferred.length ? { default: def, deferred } : def;
}

/* 从弹窗 DOM 读回 默认组 / 待发现组（模块可能是白名单或双列表两种形态） */
function readPresetDraft(root) {
  const name = presetName();
  const defEl = root.querySelector(`[data-path="__tools.${name}.default"]`);
  if (!defEl) return { def: readChips(root.querySelector(`[data-path="__tools.${name}"]`)), deferred: [] };
  return {
    def: readChips(defEl),
    deferred: readChips(root.querySelector(`[data-path="__tools.${name}.deferred"]`)),
  };
}

async function openToolsModal() {
  try {
    await refreshChatInfo();
  } catch (e) {
    toast(`获取工具预设失败：${e.message}`, 'error', 5000);
    return;
  }

  const name = presetName();
  const modal = openModal({
    title: `工具预设 · ${name}（AI 聊天页）`,
    wide: true,
    bodyHtml: `
      <div class="notice info">${icon('info')}<div>编辑的是 <code>tool_presets.${escapeHtml(name)}</code>，与配置页「工具预设」共用同一份数据。${TOOL_SEARCH_BRIEF}${helpFold(TOOL_SEARCH_HELP_LABEL, TOOL_SEARCH_RULES)}</div></div>
      ${renderToolPresetModule(name, presetValueFromInfo(), { withToggle: false, nullAsEmpty: true })}
      <p class="field-desc">保存后立即写入配置文件并热重载，无需重启。</p>`,
    actions: [
      { label: '取消', class: 'ghost', onClick: ({ close }) => close() },
      {
        label: '保存',
        class: 'primary',
        onClick: async ({ close, el }) => {
          const { def, deferred } = readPresetDraft(el);
          const errors = validatePresetPairing(name, deferred.length ? { default: def, deferred } : def);
          if (errors.length) {
            toast(errors[0], 'error', 8000);
            return;
          }
          if (!def.length && !deferred.length) {
            toast('工具列表为空：请至少勾选一个工具，或改用配置页的「限制工具」开关', 'error', 6000);
            return;
          }
          try {
            await api.post('/chat/tools', { tools: def, deferred });
            await refreshChatInfo();
            updateToolsCount();
            toast(`已保存：默认 ${def.length} 个 · 待发现 ${deferred.length} 个`, 'success');
            close();
          } catch (e) {
            toast(`保存失败：${e.message}`, 'error', 5000);
          }
        },
      },
    ],
  });

  /* chips 回车添加 / 删除 / 「从列表选择」全部复用共享组件（与配置页行为一致） */
  bindChipInteractions(modal.el);
}

/* ---------- 附件上传 ---------- */

function kindOf(name, mime = '') {
  const ext = (name.split('.').pop() || '').toLowerCase();
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'avif'].includes(ext)) return 'image';
  if (['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'opus', 'silk', 'amr'].includes(ext)) return 'audio';
  if (['mp4', 'webm', 'mov', 'avi', 'mkv', 'flv', 'm4v'].includes(ext)) return 'video';
  if (mime.startsWith('image/')) return 'image';
  if (mime.startsWith('audio/')) return 'audio';
  if (mime.startsWith('video/')) return 'video';
  return 'file';
}

async function uploadFile(file) {
  const kind = kindOf(file.name, file.type);
  const limit = (info.limits || {})[kind] ?? (info.limits || {}).file ?? 0;
  if (limit && file.size > limit) {
    toast(`「${file.name}」超过 ${Math.round(limit / 1048576)}MB 大小限制`, 'error');
    return;
  }
  const chip = el('div', 'chat-chip uploading');
  chip.innerHTML = `<span class="spinner-sm"></span><span class="mono">${escapeHtml(file.name)}</span><button class="chat-chip-x" title="移除">${icon('x')}</button>`;
  sectionEl.querySelector('#chat-attachments').appendChild(chip);
  const entry = { chip, brief: null };
  pendingAttachments.push(entry);

  chip.querySelector('.chat-chip-x').addEventListener('click', () => {
    entry.removed = true;
    chip.remove();
  });

  try {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/admin/api/chat/upload', {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
      body: fd,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    entry.brief = data.file;
    if (!entry.removed) {
      chip.classList.remove('uploading');
      const iconMap = { image: 'eye', audio: 'activity', video: 'layers', file: 'file' };
      chip.querySelector('.spinner-sm')?.remove();
      chip.insertAdjacentHTML('afterbegin', icon(iconMap[kind] || 'file'));
    }
  } catch (e) {
    entry.removed = true;
    chip.classList.add('error');
    chip.querySelector('.spinner-sm')?.remove();
    chip.insertAdjacentHTML('afterbegin', icon('alert'));
    toast(`上传失败：${e.message}`, 'error', 5000);
  }
}

/* ---------- 设置面板控件（供应商/模型/人设/工具/参数） ---------- */

function populateSuppliers() {
  const sel = sectionEl.querySelector('#chat-supplier');
  sel.innerHTML = suppliers.map((s) => `<option value="${escapeHtml(s.name)}" ${s.name === settings.supplier ? 'selected' : ''}>${escapeHtml(s.name)}</option>`).join('');
  if (!settings.supplier && suppliers.length) {
    settings.supplier = info.defaults?.supplier && suppliers.some((s) => s.name === info.defaults.supplier)
      ? info.defaults.supplier : suppliers[0].name;
    sel.value = settings.supplier;
  }
  populateModels();
}

function populateModels() {
  const sel = sectionEl.querySelector('#chat-model');
  const sup = suppliers.find((s) => s.name === settings.supplier);
  const models = sup ? Object.keys(sup.models || {}) : [];
  const badge = (m) => {
    const caps = sup.models[m] || {};
    let out = '';
    if (caps.visual_sense) out += ' 🖼️';
    if (caps.audio_sense) out += ' 🎧';
    if (caps.video_sense) out += ' 🎬';
    return out;
  };
  sel.innerHTML = models.map((m) => `<option value="${escapeHtml(m)}" ${m === settings.model ? 'selected' : ''}>${escapeHtml(m)}${badge(m)}</option>`).join('');
  if (!models.includes(settings.model)) {
    settings.model = info.defaults?.model && models.includes(info.defaults.model)
      ? info.defaults.model : (models[0] || '');
    sel.value = settings.model;
  }
}

function populatePersonas() {
  const sel = sectionEl.querySelector('#chat-persona');
  const def = info.defaults?.persona || 'none';
  if (!settings.persona || (settings.persona !== 'custom' && settings.persona !== 'none' && !personas.some((p) => p.key === settings.persona))) {
    settings.persona = def;
  }
  sel.innerHTML = `
    <option value="none" ${settings.persona === 'none' ? 'selected' : ''}>无人设</option>
    ${personas.map((p) => `<option value="${escapeHtml(p.key)}" ${settings.persona === p.key ? 'selected' : ''}>${escapeHtml(p.key)}${p.is_default ? '（默认）' : ''}</option>`).join('')}
    <option value="custom" ${settings.persona === 'custom' ? 'selected' : ''}>自定义人设…</option>`;
  toggleCustomPersonaBox();
}

function toggleCustomPersonaBox() {
  const box = sectionEl.querySelector('#chat-custom-persona-wrap');
  box.classList.toggle('hidden', settings.persona !== 'custom');
}

function updateToolsCount() {
  const badge = sectionEl?.querySelector('#chat-tools-count');
  if (!badge) return;
  const preset = info.webui_preset || {};
  if (!preset.exists) {
    badge.textContent = '工具预设未配置（点击设置）';
    return;
  }
  badge.textContent = `预设 ${presetName()}：默认 ${preset.default?.length ?? 0} 个 · 待发现 ${preset.deferred?.length ?? 0} 个`;
}

function initParamsUI() {
  const p = settings.params;
  const temperature = sectionEl.querySelector('#chat-param-temperature');
  const topP = sectionEl.querySelector('#chat-param-top_p');
  const maxTokens = sectionEl.querySelector('#chat-param-max_tokens');
  const toolChoice = sectionEl.querySelector('#chat-param-tool_choice');
  temperature.value = p.temperature;
  sectionEl.querySelector('#chat-val-temperature').textContent = p.temperature;
  topP.value = p.top_p;
  sectionEl.querySelector('#chat-val-top_p').textContent = p.top_p;
  maxTokens.value = p.max_tokens;
  toolChoice.value = p.tool_choice;

  temperature.addEventListener('input', (e) => {
    settings.params.temperature = Number(e.target.value);
    sectionEl.querySelector('#chat-val-temperature').textContent = e.target.value;
    saveSettings();
  });
  topP.addEventListener('input', (e) => {
    settings.params.top_p = Number(e.target.value);
    sectionEl.querySelector('#chat-val-top_p').textContent = e.target.value;
    saveSettings();
  });
  maxTokens.addEventListener('change', (e) => {
    const v = Math.max(1, Math.min(200000, parseInt(e.target.value, 10) || 0));
    e.target.value = v;
    settings.params.max_tokens = v;
    saveSettings();
  });
  toolChoice.addEventListener('change', (e) => {
    settings.params.tool_choice = e.target.value;
    saveSettings();
  });
  sectionEl.querySelector('#chat-params-reset').addEventListener('click', () => {
    settings.params = defaultParams();
    saveSettings();
    initParamsUI();
    toast('请求参数已恢复为默认值', 'success');
  });
}

function setConnState(ok) {
  const dot = sectionEl?.querySelector('#chat-conn-dot');
  if (dot) dot.className = `dot ${ok ? 'green' : 'red'}`;
  if (!ok) {
    const label = sectionEl?.querySelector('#chat-current');
    if (label && currentSession === null) label.textContent = '正在连接…';
  }
}

/* ---------- 视图入口 ---------- */

let pendingAttachments = [];

async function init(section) {
  sectionEl = section;
  /* 路由每次离开视图都会 destroy()（置 destroyed 关闭 WS），
     再次进入必须重置，否则 connectWs 短路、永远报"聊天服务未连接" */
  destroyed = false;
  clearTimeout(wsRetryTimer);
  wsRetry = 0;
  loadSettings();
  initialOpened = false;
  generating = false;
  currentSession = null;
  activeTurn = null;
  pendingAttachments = [];

  section.innerHTML = `
    <div class="chat-page">
      <div class="chat-main">
        <div class="chat-statusbar">
          <span class="chat-conn" title="聊天服务连接状态"><span class="dot red" id="chat-conn-dot"></span></span>
          <span class="chat-current" id="chat-current">正在连接…</span>
          <span class="spacer"></span>
          <button class="icon-btn chat-settings-toggle" id="chat-settings-toggle" title="会话设置">${icon('sliders')}</button>
        </div>

        <div class="chat-messages" id="chat-messages">
          <div class="chat-empty">
            <div class="chat-empty-logo" id="chat-empty-logo">A</div>
            <p>连接聊天服务后即可开始对话</p>
            <p class="muted small">支持图片 / 音频 / 视频附件</p>
          </div>
        </div>

        <div class="chat-drop-overlay">${icon('plus')} 松开以添加附件</div>

        <div class="chat-input-area">
          <div class="chat-attachments" id="chat-attachments"></div>
          <div class="chat-input-row">
            <button class="icon-btn" id="chat-attach-btn" title="添加附件（图片/音频/视频/文件）">${icon('file')}</button>
            <textarea class="chat-textarea" id="chat-text" rows="1" placeholder="输入消息，Enter 发送，Shift+Enter 换行；可直接拖入文件"></textarea>
            <button class="btn primary" id="chat-send">${icon('send')} 发送</button>
          </div>
        </div>
      </div>

      <aside class="chat-settings" id="chat-settings">
        <div class="chat-settings-title">${icon('sliders')} 对话设置</div>

        <div class="field">
          <div class="field-label">供应商</div>
          <div class="field-desc">选择模型 API 服务商</div>
          <select class="select" id="chat-supplier"></select>
        </div>
        <div class="field">
          <div class="field-label">模型</div>
          <div class="field-desc">🖼️ 图片 🎧 音频 🎬 视频为模型多模态能力标记</div>
          <select class="select" id="chat-model"></select>
        </div>
        <div class="field">
          <div class="field-label">人设</div>
          <div class="field-desc">对话的系统提示词，可选预设或自定义</div>
          <select class="select" id="chat-persona"></select>
        </div>
        <div class="field hidden" id="chat-custom-persona-wrap">
          <div class="field-label">自定义人设</div>
          <div class="field-desc">直接输入人设全文（仅保存在本浏览器）</div>
          <textarea class="input mono" id="chat-custom-persona" rows="4" placeholder="输入自定义人设文本…"></textarea>
        </div>
        <div class="field">
          <div class="field-label">工具</div>
          <div class="field-desc">默认工具直接可用，待发现工具由 tool_search 按需启用</div>
          <button class="btn sm ghost" id="chat-tools-btn" style="width:100%">${icon('settings')} <span id="chat-tools-count"></span></button>
        </div>

        <div class="chat-settings-sep">请求参数</div>
        <div class="field-desc" style="margin:0 0 6px">未调整时使用主配置 chat_parameter</div>
        <div class="field">
          <div class="field-label">温度 temperature <span class="chat-param-val" id="chat-val-temperature"></span></div>
          <div class="field-desc">值越高回答越发散</div>
          <input type="range" class="chat-range" id="chat-param-temperature" min="0" max="2" step="0.1">
        </div>
        <div class="field">
          <div class="field-label">核采样 top_p <span class="chat-param-val" id="chat-val-top_p"></span></div>
          <div class="field-desc">采样概率累积上限，与温度二选一调节</div>
          <input type="range" class="chat-range" id="chat-param-top_p" min="0" max="1" step="0.05">
        </div>
        <div class="field">
          <div class="field-label">最大输出 max_tokens</div>
          <div class="field-desc">单次回复的长度上限</div>
          <input type="number" class="input" id="chat-param-max_tokens" min="1" max="200000" step="256">
        </div>
        <div class="field">
          <div class="field-label">工具选择 tool_choice</div>
          <div class="field-desc">是否强制模型调用工具</div>
          <select class="select" id="chat-param-tool_choice">
            <option value="auto">auto · 自动决定</option>
            <option value="none">none · 禁用工具</option>
            <option value="required">required · 强制调用</option>
          </select>
        </div>
        <button class="btn sm ghost" id="chat-params-reset" style="width:100%">恢复默认参数</button>
      </aside>

      <div class="chat-settings-backdrop" id="chat-settings-backdrop"></div>
      <input type="file" id="chat-file-input" multiple hidden
             accept="image/*,audio/*,video/*,.txt,.md,.json,.csv,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.7z,.rar,.py,.js,.ts,.java,.c,.cpp,.html,.css,.xml,.yaml,.yml,.toml,.log">
    </div>`;

  messagesEl = section.querySelector('#chat-messages');
  const textEl = section.querySelector('#chat-text');
  mountEmptyLogo();

  /* 公式图片加载失败时降级为原始 LaTeX 文本 */
  messagesEl.addEventListener('error', (e) => {
    const img = e.target;
    if (img instanceof HTMLImageElement && img.classList.contains('chat-formula')) {
      const code = document.createElement('code');
      code.textContent = img.dataset.latex || img.alt || '';
      img.replaceWith(code);
    }
  }, true);

  /* ---- 引导数据 ---- */
  const [infoRes, supplierRes, personaRes] = await Promise.allSettled([
    api.get('/chat/info'),
    api.get('/supplier_config'),
    api.get('/personas'),
  ]);
  if (infoRes.status === 'fulfilled') info = { ...info, ...infoRes.value };
  if (supplierRes.status === 'fulfilled') suppliers = supplierRes.value.suppliers || [];
  if (personaRes.status === 'fulfilled') personas = personaRes.value.items || [];
  if (infoRes.status === 'rejected') toast(`聊天服务信息加载失败：${infoRes.value.reason?.message || infoRes.value.reason}`, 'error', 5000);

  populateSuppliers();
  populatePersonas();
  settings.params = { ...defaultParams(), ...(settings.params || {}) };
  initParamsUI();
  updateToolsCount();
  const customBox = section.querySelector('#chat-custom-persona');
  customBox.value = localStorage.getItem(`${SETTINGS_KEY}_custom`) || '';

  section.querySelector('#chat-supplier').addEventListener('change', (e) => {
    settings.supplier = e.target.value;
    saveSettings();
    populateModels();
  });
  section.querySelector('#chat-model').addEventListener('change', (e) => {
    settings.model = e.target.value;
    saveSettings();
  });
  section.querySelector('#chat-persona').addEventListener('change', (e) => {
    settings.persona = e.target.value;
    saveSettings();
    toggleCustomPersonaBox();
  });
  customBox.addEventListener('change', saveSettings);
  section.querySelector('#chat-tools-btn').addEventListener('click', openToolsModal);

  /* ---- 移动端设置抽屉 ---- */
  const pageEl = section.querySelector('.chat-page');
  section.querySelector('#chat-settings-toggle').addEventListener('click', () => {
    pageEl.classList.toggle('chat-settings-open');
  });
  section.querySelector('#chat-settings-backdrop').addEventListener('click', () => {
    pageEl.classList.remove('chat-settings-open');
  });

  /* ---- 侧栏会话列表 + 连接 ---- */
  bindSessionNav();
  await refreshSessions();
  connectWs();
  maybeOpenInitial();

  /* ---- 输入与发送 ---- */
  const sendBtn = section.querySelector('#chat-send');
  const autoGrow = () => {
    textEl.style.height = 'auto';
    textEl.style.height = `${Math.min(textEl.scrollHeight, 160)}px`;
  };
  textEl.addEventListener('input', autoGrow);

  textEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendBtn.click();
    }
  });

  sendBtn.addEventListener('click', () => {
    if (generating) {
      sendWs({ type: 'stop', session: currentSession });
      return;
    }
    doSend();
  });

  function doSend() {
    const text = textEl.value.trim();
    const ready = pendingAttachments.filter((a) => a.brief && !a.removed);
    const uploading = pendingAttachments.filter((a) => !a.brief && !a.removed);
    if (uploading.length) { toast('附件还在上传中，请稍候', 'error'); return; }
    if (!text && !ready.length) return;
    if (!settings.supplier || !settings.model) {
      toast('请先在右侧设置面板选择供应商和模型', 'error');
      pageEl.classList.add('chat-settings-open');
      return;
    }
    if (!wsOpen) { toast('聊天服务未连接', 'error'); return; }

    const files = ready.map((a) => a.brief);
    const nonce = Math.random().toString(36).slice(2);
    lastNonce = nonce;
    appendUserMessage(text, files, nonce, Date.now() / 1000);
    lastUserMeta = {
      umIndex: [...messagesEl.querySelectorAll('.chat-msg.user')].length - 1,
      userText: text,
    };
    beginAssistantTurn(lastUserMeta);
    setGenerating(true);

    const ok = sendWs({
      type: 'send',
      session: currentSession,
      text,
      files: files.map((f) => f.id),
      settings: currentSettingsPayload(),
      nonce,
    });
    if (!ok) {
      finishTurn('error');
      activeTurn?.bubble.appendChild(el('div', 'chat-error', `${icon('alert')} 发送失败：服务未连接`));
    }

    textEl.value = '';
    autoGrow();
    for (const a of pendingAttachments) a.chip?.remove();
    pendingAttachments = [];
  }

  /* ---- 附件：按钮选择 + 拖拽 ---- */
  const fileInput = section.querySelector('#chat-file-input');
  section.querySelector('#chat-attach-btn').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    for (const file of fileInput.files) uploadFile(file);
    fileInput.value = '';
  });

  const overlay = section.querySelector('.chat-drop-overlay');
  let dragDepth = 0;
  section.addEventListener('dragover', (e) => e.preventDefault());
  section.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragDepth += 1;
    overlay.classList.add('show');
  });
  section.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) overlay.classList.remove('show');
  });
  section.addEventListener('drop', (e) => {
    e.preventDefault();
    dragDepth = 0;
    overlay.classList.remove('show');
    for (const file of e.dataTransfer?.files || []) uploadFile(file);
  });
}

function destroy() {
  destroyed = true;
  clearTimeout(wsRetryTimer);
  try { ws?.close(); } catch { /* 忽略关闭异常 */ }
  ws = null;
  sectionEl = null;
  messagesEl = null;
  activeTurn = null;
  pendingAttachments = [];
}

export const chatView = { title: 'AI 聊天', init, destroy };
