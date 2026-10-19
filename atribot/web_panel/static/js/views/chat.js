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


const HIDE_SETTINGS_KEY = 'atri_chat_settings_hidden';
const BOT_AVATAR_URL = 'https://q1.qlogo.cn/g?b=qq&nk=168238719&s=640';

const SUGGESTS = [
  '介绍一下你自己，你都能做些什么？',
  '用 Python 写一个快速排序并解释时间复杂度',
  '用表格对比 PostgreSQL 与 SQLite 的差异',
  '帮我检索一下最近有哪些值得关注的开源项目',
];

/* ---------- 模块级运行状态（destroy 时清理） ---------- */

let ws = null;
let wsOpen = false;
let wsRetry = 0;
let wsRetryTimer = null;
let destroyed = false;
let initialOpened = false;

let sectionEl = null;
let messagesEl = null;
let scrollBtn = null;
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
let settings = { supplier: '', model: '', persona: 'none', params: null, extra_json: '' };

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
  updateMeta();
}

function personaLabel() {
  if (settings.persona === 'custom') return '自定义人设';
  if (!settings.persona || settings.persona === 'none') return '无人设';
  return settings.persona;
}

function summaryText() {
  return `${settings.model || '未选择模型'} · ${personaLabel()} · 支持图片 / 音频 / 视频附件`;
}

/* 状态栏模型/人设标签 + 空状态摘要 */
function updateMeta() {
  const model = sectionEl?.querySelector('#chat-meta-model span');
  if (model) model.textContent = settings.model || '未选择模型';
  const persona = sectionEl?.querySelector('#chat-meta-persona span');
  if (persona) persona.textContent = personaLabel();
  const sub = sectionEl?.querySelector('#chat-empty-sub');
  if (sub) sub.textContent = summaryText();
}

function emptyHtml() {
  const cards = SUGGESTS.map((s) => `<button type="button" class="chat-suggest">${icon('sparkles')}<span>${escapeHtml(s)}</span></button>`).join('');
  return `
    <div class="chat-empty">
      <div class="chat-empty-logo" id="chat-empty-logo">A</div>
      <h2 class="chat-empty-title">今天想聊点什么？</h2>
      <p class="chat-empty-sub" id="chat-empty-sub">${escapeHtml(summaryText())}</p>
      <div class="chat-suggests">${cards}</div>
    </div>`;
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

/* 额外请求 JSON：空串视为未设置；需为 JSON 对象，否则 ok=false */
function parseExtraJson(raw) {
  const text = String(raw ?? '').trim();
  if (!text) return { ok: true, value: null, count: 0 };
  try {
    const value = JSON.parse(text);
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
      return { ok: false, error: '需要是 JSON 对象 { ... }' };
    }
    return { ok: true, value, count: Object.keys(value).length };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

function currentSettingsPayload() {
  const extra = parseExtraJson(settings.extra_json);
  return {
    supplier: settings.supplier,
    model: settings.model,
    persona_key: settings.persona || 'none',
    custom_persona: settings.persona === 'custom' ? customPersonaText() : '',
    params: settings.params,
    extra_params: extra.ok && extra.value ? extra.value : undefined,
  };
}

/* ---------- 轻量 Markdown + LaTeX 公式渲染（无外部依赖） ---------- */

function formulaImgHtml(latex, display) {
  const url = CODECOGS + encodeURIComponent(latex);
  return `<img class="chat-formula${display ? ' display' : ''}" src="${escapeHtml(url)}" alt="${escapeHtml(latex)}" data-latex="${escapeHtml(latex)}" loading="lazy">`;
}

/* 公式占位符：\x01 包裹索引，全文提取后按行解析 Markdown，最终在 inlineMd 里还原 */
const FORMULA_TOKEN = /\x01(\d+)\x01/g;
/* 单个字母/希腊字母命令/下标上标等也当公式，排除 $5 这类金额 */
const LATEX_LIKE = /^(?:\\[A-Za-z]+|[A-Za-z]\w{0,2}|[^\d\s][^$]*[\\^_{}=+\-*/<>|()][^$]*)$/;

/* 把非代码文本中的公式替换为占位符（支持跨行的 $$..$$ 与 \[..\]） */
function extractFormulas(text, formulas) {
  const stash = (latex, display) => {
    formulas.push({ latex, display });
    return display ? `\n\n\x01${formulas.length - 1}\x01\n\n` : `\x01${formulas.length - 1}\x01`;
  };
  return text
    .replace(/\$\$([\s\S]+?)\$\$/g, (_, c) => (c.trim() ? stash(c.trim(), true) : _))
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, c) => (c.trim() ? stash(c.trim(), true) : _))
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, c) => (c.trim() ? stash(c.trim(), false) : _))
    .replace(/\$([^$\n]+?)\$/g, (m, c) => {
      const body = c.trim();
      /* 首尾有空格的 `$ a $` 多半是金额文字，保持原样 */
      if (!body || body !== c || body.length > MAX_FORMULA_LEN) return m;
      return (MATH_HINT.test(body) || LATEX_LIKE.test(body)) ? stash(body, false) : m;
    });
}

/* ---------- 轻量代码高亮（无依赖，仅区分 关键字/字符串/注释/数字/布尔） ---------- */

const LANG_ALIAS = {
  py: 'py', python: 'py', python3: 'py',
  js: 'js', javascript: 'js', ts: 'js', typescript: 'js', jsx: 'js', tsx: 'js', java: 'js', c: 'js', cpp: 'js', 'c++': 'js', cs: 'js', 'c#': 'js', go: 'js', rust: 'js', rs: 'js',
  sh: 'sh', bash: 'sh', shell: 'sh', zsh: 'sh', powershell: 'sh', ps1: 'sh',
  sql: 'sql', json: 'json', jsonc: 'json', yaml: 'sh', yml: 'sh', toml: 'sh',
};

const makeSet = (s) => new Set(s.split(' '));
const LANG_KEYWORDS = {
  py: makeSet('and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case self cls'),
  js: makeSet('async await break case catch class const continue default delete do else export extends finally for from function if import in instanceof let new of return static super switch this throw try typeof var void while with yield interface type enum implements public private protected readonly package struct impl fn func def use mod pub mut int long float double char string bool'),
  sh: makeSet('if then else elif fi for while do done case esac function in return export local source echo cd ls cat grep sed awk sudo pip uv npm git docker'),
  sql: makeSet('select from where and or not insert into values update set delete create table alter drop index join left right inner outer on group by order limit offset as distinct having union all is in like between exists primary key foreign references default'),
  json: new Set(),
};
const LANG_BOOLS = makeSet('True False None true false null NULL nil');

const LANG_COMMENT = {
  py: '#[^\\n]*',
  sh: '#[^\\n]*',
  sql: '--[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/',
  js: '\\/\\/[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/',
  json: '(?!)',
};

function highlightCode(code, lang) {
  const key = LANG_ALIAS[String(lang || '').toLowerCase()];
  if (!key) return escapeHtml(code);
  const str = '"""[\\s\\S]*?"""|\'\'\'[\\s\\S]*?\'\'\'|"(?:\\\\.|[^"\\\\\\n])*"|\'(?:\\\\.|[^\'\\\\\\n])*\'|`(?:\\\\.|[^`\\\\])*`';
  const re = new RegExp(`(${LANG_COMMENT[key]})|(${str})|(\\b\\d+(?:\\.\\d+)?\\b)|([A-Za-z_][\\w]*)`, 'g');
  const keywords = LANG_KEYWORDS[key];
  let out = '';
  let last = 0;
  let m;
  while ((m = re.exec(code)) !== null) {
    out += escapeHtml(code.slice(last, m.index));
    last = m.index + m[0].length;
    const text = escapeHtml(m[0]);
    if (m[1] !== undefined) out += `<span class="tok-c">${text}</span>`;
    else if (m[2] !== undefined) out += `<span class="tok-s">${text}</span>`;
    else if (m[3] !== undefined) out += `<span class="tok-n">${text}</span>`;
    else if (LANG_BOOLS.has(m[4])) out += `<span class="tok-b">${text}</span>`;
    else if (keywords.has(key === 'sql' ? m[4].toLowerCase() : m[4])) out += `<span class="tok-k">${text}</span>`;
    else out += text;
  }
  return out + escapeHtml(code.slice(last));
}

function codeBlockHtml(code, lang) {
  return `<div class="chat-codeblock"><div class="chat-codeblock-head"><span class="chat-codeblock-lang">${escapeHtml(lang || 'text')}</span><button type="button" class="chat-codeblock-copy" aria-label="复制代码">${icon('copy')}<span>复制</span></button></div><pre class="chat-code"><code>${highlightCode(code, lang)}</code></pre></div>`;
}

function inlineMd(raw, formulas = []) {
  let html = escapeHtml(raw);
  /* 公式占位符先保护，避免公式内的 * _ ~ 被当成 Markdown 语法 */
  const stash = [];
  html = html.replace(FORMULA_TOKEN, (_, i) => `\x02${stash.push(formulas[Number(i)]) - 1}\x02`);
  html = html
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*\n][^*]*?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>')
    .replace(/~~([^~\n]+)~~/g, '<del>$1</del>')
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/(^|[\s(（])(https?:\/\/[^\s<)）]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  return html.replace(/\x02(\d+)\x02/g, (_, i) => {
    const f = stash[Number(i)];
    return f ? formulaImgHtml(f.latex, f.display) : '';
  });
}

/* 公式提取只作用于代码围栏之外的文本，代码块内的 $ 保持原样 */
function extractFormulasOutsideCode(text, formulas) {
  /* 奇数段是围栏代码块或行内代码，原样保留 */
  const segments = text.split(/(^```[^\n]*\n[\s\S]*?^```[ \t]*$|`[^`\n]+`)/m);
  return segments.map((seg, idx) => (idx % 2 === 1 ? seg : extractFormulas(seg, formulas))).join('');
}

function renderMarkdown(raw) {
  const formulas = [];
  const text = extractFormulasOutsideCode(String(raw ?? '').replace(/\x01|\x02/g, ''), formulas);
  const parts = [];
  const lines = text.split(/\r?\n/);
  let i = 0;
  const inline = (s) => inlineMd(s, formulas);

  const flushParagraph = (buf) => {
    if (buf.length) parts.push(`<p>${buf.map(inline).join('<br>')}</p>`);
  };

  let para = [];
  while (i < lines.length) {
    const line = lines[i];

    /* 围栏代码块 */
    const fence = line.match(/^```([\w+#.-]*)\s*$/);
    if (fence) {
      flushParagraph(para); para = [];
      const code = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) { code.push(lines[i]); i += 1; }
      i += 1;
      parts.push(codeBlockHtml(code.join('\n'), fence[1]));
      continue;
    }

    if (!line.trim()) { flushParagraph(para); para = []; i += 1; continue; }

    /* 标题 / 分割线 / 引用 / 列表 / 表格 */
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushParagraph(para); para = [];
      const level = h[1].length;
      parts.push(`<div class="chat-md-h chat-md-h${level}">${inline(h[2])}</div>`);
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
      parts.push(`<blockquote class="chat-md-quote">${quote.map(inline).join('<br>')}</blockquote>`);
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
      const li = (it) => {
        const task = it.match(/^\[([ xX])\]\s+(.*)$/);
        if (!task) return `<li>${inline(it)}</li>`;
        const checked = task[1] === ' ' ? '' : ' checked';
        return `<li class="chat-md-task"><input type="checkbox" disabled${checked}>${inline(task[2])}</li>`;
      };
      parts.push(`<${tag} class="chat-md-list">${items.map(li).join('')}</${tag}>`);
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
      parts.push(`<div class="chat-md-table-wrap"><table class="chat-md-table"><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
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
  return BOT_AVATAR_URL;
}

/* 机器人头像：直接使用 168238719 的 QQ 头像，加载失败时回退字母 A */
function makeBotAvatar() {
  const wrap = el('div', 'chat-avatar bot-avatar');
  const img = document.createElement('img');
  img.className = 'chat-avatar-img';
  img.alt = 'ATRI';
  img.referrerPolicy = 'no-referrer';
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
  if (!messagesEl) return;
  if (force || userAtBottom()) {
    messagesEl.scrollTop = messagesEl.scrollHeight;
    scrollBtn?.classList.remove('show', 'has-new');
  } else if (generating) {
    scrollBtn?.classList.add('has-new');
  }
}

/* ---------- 消息渲染 ---------- */

function attachmentHtml(file) {
  const url = `${file.url}?token=${encodeURIComponent(getToken())}`;
  const name = escapeHtml(file.name || file.id);
  /* 图片/文件点击后在小窗里预览（事件委托读 data-pv-*） */
  const pv = `data-pv-url="${escapeHtml(url)}" data-pv-name="${name}" data-pv-kind="${escapeHtml(file.kind)}" data-pv-size="${Number(file.size) || 0}"`;
  if (file.kind === 'image') {
    return `<a class="chat-attach-img-link" href="${escapeHtml(url)}" ${pv} title="点击预览：${name}"><img class="chat-attach-img" src="${escapeHtml(url)}" alt="${name}" loading="lazy"></a>`;
  }
  if (file.kind === 'audio') return `<audio class="chat-attach-audio" controls preload="none" src="${escapeHtml(url)}"></audio>`;
  if (file.kind === 'video') return `<video class="chat-attach-video" controls preload="metadata" src="${escapeHtml(url)}"></video>`;
  return `<a class="chat-attach-file" href="${escapeHtml(url)}" ${pv} title="点击预览：${name}">${icon('file')} ${name} <span class="muted small">(${Math.ceil((file.size || 0) / 1024)} KB)</span></a>`;
}

/* ---------- 附件预览小窗 ---------- */

const TEXT_EXTS = new Set('txt md markdown json jsonc csv tsv log ini cfg conf toml yaml yml xml html css js ts jsx tsx py java c cpp h hpp cs go rs sh bash ps1 sql env'.split(' '));
const PREVIEW_MAX_BYTES = 2 * 1024 * 1024;

function fmtSize(bytes) {
  const n = Number(bytes) || 0;
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(1)} MB`;
}

function triggerDownload(url, name) {
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function openFilePreview({ pvUrl: url, pvName: name, pvKind: kind, pvSize: size }) {
  const ext = (name.split('.').pop() || '').toLowerCase();
  const isImage = kind === 'image';
  const body = isImage
    ? `<div class="file-preview-img-wrap"><img class="file-preview-img" src="${escapeHtml(url)}" alt="${escapeHtml(name)}"></div>`
    : '<div class="file-preview-text"><div class="file-preview-loading"><span class="spinner-sm"></span> 加载中…</div></div>';
  const modal = openModal({
    title: `${name} · ${fmtSize(size)}`,
    wide: true,
    bodyHtml: body,
    actions: [
      { label: `${icon('download')} 下载`, class: 'primary', onClick: () => triggerDownload(url, name) },
      { label: '关闭', class: 'ghost', onClick: ({ close }) => close() },
    ],
  });
  if (isImage) return;

  modal.el.addEventListener('click', handleCopyButton);
  const box = modal.el.querySelector('.file-preview-text');
  const notice = (title, sub) => {
    box.innerHTML = `<div class="empty-state">${icon('file')}<div class="empty-state-title">${escapeHtml(title)}</div><div>${escapeHtml(sub)}</div></div>`;
  };
  if (!TEXT_EXTS.has(ext)) { notice('该类型暂不支持在线预览', '请点击下方「下载」保存到本地'); return; }
  if (Number(size) > PREVIEW_MAX_BYTES) { notice('文件过大，不支持预览', `超过 ${fmtSize(PREVIEW_MAX_BYTES)}，请下载查看`); return; }
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    if (!box.isConnected) return;
    box.innerHTML = (ext === 'md' || ext === 'markdown')
      ? `<div class="chat-content chat-md">${renderMarkdown(text)}</div>`
      : `<pre class="chat-code file-preview-code"><code>${highlightCode(text, ext)}</code></pre>`;
  } catch (e) {
    if (box.isConnected) notice('加载失败', e.message);
  }
}

/* 代码块/工具块的复制按钮；命中返回 true */
async function handleCopyButton(e) {
  const codeBtn = e.target.closest('.chat-codeblock-copy');
  const toolBtn = e.target.closest('.chat-tool-copy');
  const btn = codeBtn || toolBtn;
  if (!btn) return false;
  const source = codeBtn
    ? btn.closest('.chat-codeblock').querySelector('code')
    : btn.closest('.chat-tool-section').querySelector('pre');
  const ok = await copyText(source?.textContent || '');
  if (!ok) { toast('复制失败', 'error'); return true; }
  const label = btn.querySelector('span') || btn;
  const original = label.textContent;
  btn.classList.add('copied');
  label.textContent = '已复制';
  setTimeout(() => { btn.classList.remove('copied'); label.textContent = original; }, 1500);
  return true;
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
  if (text) {
    /* 复制该条用户消息原文（纯附件消息无文本，不显示该按钮） */
    const copyBtn = el('button', 'chat-msg-action', `${icon('copy')} 复制`);
    copyBtn.type = 'button';
    copyBtn.title = '复制此消息';
    copyBtn.addEventListener('click', async () => {
      const ok = await copyText(row.querySelector('.chat-text')?.textContent || '');
      toast(ok ? '已复制消息' : '复制失败', ok ? 'success' : 'error');
    });
    actions.appendChild(copyBtn);
  }
  const editBtn = el('button', 'chat-msg-action', `${icon('edit')} 编辑`);
  editBtn.type = 'button';
  editBtn.title = '编辑此消息并回退后续对话';
  editBtn.addEventListener('click', () => startEditMessage(row));
  actions.appendChild(editBtn);
  bubble.appendChild(actions);
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
  head.setAttribute('aria-expanded', String(!collapsed));
  head.addEventListener('click', () => {
    block.classList.toggle('collapsed');
    if (block.classList.contains('collapsed')) scrollToBottom();
  });
  /* 脚本里直接加/去 collapsed 的地方较多，aria 状态统一由观察器同步 */
  new MutationObserver(() => {
    head.setAttribute('aria-expanded', String(!block.classList.contains('collapsed')));
  }).observe(block, { attributes: true, attributeFilter: ['class'] });
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
    `<span class="chat-block-name mono">${icon('wrench')}${escapeHtml(toolName || toolCallId)}</span><span class="chat-tool-status running">运行中…</span><span class="chat-tool-time"></span>`,
    { collapsed: true, cls: 'tool' },
  );
  const copyBtn = `<button type="button" class="chat-tool-copy" aria-label="复制">${icon('copy')}复制</button>`;
  block.querySelector('.chat-block-body').innerHTML = `
    <div class="chat-tool-section"><div class="chat-tool-label"><span>参数</span>${copyBtn}</div><pre class="chat-tool-args mono">-</pre></div>
    <div class="chat-tool-section"><div class="chat-tool-label"><span>结果</span>${copyBtn}</div><pre class="chat-tool-result mono">…</pre></div>`;
  step.node.appendChild(block);
  tool = {
    block,
    startedAt: performance.now(),
    status: block.querySelector('.chat-tool-status'),
    time: block.querySelector('.chat-tool-time'),
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
  tool.block.classList.remove('is-ok', 'is-error');
  tool.block.classList.add(isError ? 'is-error' : 'is-ok');
  /* 历史重放的工具块没有真实耗时 */
  if (tool.time && !activeTurn?.replay) tool.time.textContent = `${((performance.now() - tool.startedAt) / 1000).toFixed(1)}s`;
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
    rs.body.scrollTop = rs.body.scrollHeight;
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
    /* 用户点「停止」后端会先广播这条 ERROR，不应当作错误展示 */
    if (event.exception_type === 'CancelledError') {
      activeTurn.bubble.insertBefore(el('div', 'chat-stopped', `${icon('stop')} 已手动停止生成`), activeTurn.status);
      finishTurn('stopped');
      return;
    }
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
  sendBtn.classList.toggle('danger', value);
  sendBtn.innerHTML = icon(value ? 'stop' : 'send');
  sendBtn.title = value ? '停止生成' : '发送（Enter）';
  sendBtn.setAttribute('aria-label', value ? '停止生成' : '发送');
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
      if (item.reasoning) {
        const rs = reasoningBlock(activeTurn, step);
        step.reasoningText = item.reasoning;
        rs.body.textContent = item.reasoning;
        rs.hint.textContent = ` · ${item.reasoning.length} 字`;
        rs.block.classList.add('collapsed');
      }
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
    messagesEl.innerHTML = emptyHtml();
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
  let thumbUrl = '';
  if (kind === 'image') {
    thumbUrl = URL.createObjectURL(file);
    chip.dataset.thumb = thumbUrl;
  }

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
      const iconMap = { image: 'image', audio: 'activity', video: 'layers', file: 'file' };
      chip.querySelector('.spinner-sm')?.remove();
      if (thumbUrl) {
        const thumb = el('img', 'chat-chip-thumb');
        thumb.src = thumbUrl;
        thumb.alt = '';
        chip.prepend(thumb);
      } else {
        chip.insertAdjacentHTML('afterbegin', icon(iconMap[kind] || 'file'));
      }
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
          <span class="chat-meta">
            <button type="button" class="chat-meta-chip" id="chat-meta-model" title="当前模型（点击打开设置）">${icon('bot')}<span></span></button>
            <button type="button" class="chat-meta-chip" id="chat-meta-persona" title="当前人设（点击打开设置）">${icon('sparkles')}<span></span></button>
          </span>
          <span class="spacer"></span>
          <button class="icon-btn chat-settings-toggle" id="chat-settings-toggle" title="会话设置" aria-label="会话设置">${icon('panelRight')}</button>
        </div>

        <div class="chat-messages-wrap">
          <div class="chat-messages" id="chat-messages" role="log" aria-live="polite">${emptyHtml()}</div>
          <button type="button" class="chat-scroll-bottom" id="chat-scroll-bottom" title="回到底部" aria-label="回到底部">${icon('arrowDown')}</button>
        </div>

        <div class="chat-drop-overlay">${icon('plus')} 松开以添加附件</div>

        <div class="chat-input-area">
          <div class="chat-attachments" id="chat-attachments"></div>
          <div class="chat-input-row">
            <button class="icon-btn" id="chat-attach-btn" title="添加附件（图片/音频/视频/文件）" aria-label="添加附件">${icon('paperclip')}</button>
            <textarea class="chat-textarea" id="chat-text" rows="1" placeholder="给 ATRI 发消息…" aria-label="消息输入"></textarea>
            <button class="chat-send" id="chat-send" title="发送（Enter）" aria-label="发送">${icon('send')}</button>
          </div>
          <div class="chat-input-hint">Enter 发送 · Shift+Enter 换行 · 支持拖拽或粘贴文件</div>
        </div>
      </div>

      <aside class="chat-settings" id="chat-settings">
        <div class="chat-settings-title">${icon('sliders')} 对话设置
          <button type="button" class="icon-btn chat-settings-close" id="chat-settings-close" title="收起设置" aria-label="收起设置">${icon('x')}</button>
        </div>

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
          <button class="btn sm ghost chat-wide-btn" id="chat-tools-btn">${icon('settings')} <span id="chat-tools-count"></span></button>
        </div>

        <div class="chat-settings-sep">请求参数</div>
        <div class="field-desc chat-settings-note">未调整时使用主配置 chat_parameter</div>
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
        <div class="field">
          <div class="field-label">额外请求 JSON <span class="chat-param-val" id="chat-extra-count"></span></div>
          <div class="field-desc">合并进模型请求体（如 top_k、enable_thinking）。与上方参数或主配置同名时以已有配置为准；model / messages / stream / tools 会被忽略</div>
          <textarea class="input mono chat-extra-json" id="chat-extra-json" rows="4" spellcheck="false" placeholder='{"top_k": 40}'></textarea>
          <div class="chat-extra-error" id="chat-extra-error"></div>
        </div>
        <button class="btn sm ghost chat-wide-btn" id="chat-params-reset">恢复默认参数</button>
      </aside>

      <div class="chat-settings-backdrop" id="chat-settings-backdrop"></div>
      <input type="file" id="chat-file-input" multiple hidden
             accept="image/*,audio/*,video/*,.txt,.md,.json,.csv,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.7z,.rar,.py,.js,.ts,.java,.c,.cpp,.html,.css,.xml,.yaml,.yml,.toml,.log">
    </div>`;

  messagesEl = section.querySelector('#chat-messages');
  scrollBtn = section.querySelector('#chat-scroll-bottom');
  const textEl = section.querySelector('#chat-text');
  mountEmptyLogo();

  /* 回到底部按钮：离底超过阈值才显示 */
  messagesEl.addEventListener('scroll', () => {
    const away = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight > 160;
    scrollBtn.classList.toggle('show', away);
    if (!away) scrollBtn.classList.remove('has-new');
  }, { passive: true });
  scrollBtn.addEventListener('click', () => {
    messagesEl.scrollTo({ top: messagesEl.scrollHeight, behavior: 'smooth' });
  });

  /* 代码块/工具块复制与空状态示例提问（事件委托，流式重绘不丢绑定） */
  messagesEl.addEventListener('click', async (e) => {
    const suggest = e.target.closest('.chat-suggest');
    if (suggest) {
      textEl.value = suggest.textContent.trim();
      textEl.dispatchEvent(new Event('input'));
      textEl.focus();
      return;
    }
    const preview = e.target.closest('[data-pv-url]');
    if (preview) {
      e.preventDefault();
      openFilePreview(preview.dataset);
      return;
    }
    await handleCopyButton(e);
  });

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
    updateMeta();
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

  const extraEl = section.querySelector('#chat-extra-json');
  const extraErr = section.querySelector('#chat-extra-error');
  const extraCount = section.querySelector('#chat-extra-count');
  const refreshExtra = () => {
    const r = parseExtraJson(extraEl.value);
    extraErr.textContent = r.ok ? '' : `JSON 无效：${r.error}`;
    extraEl.classList.toggle('invalid', !r.ok);
    extraCount.textContent = r.ok && r.count ? `${r.count} 项` : '';
    extraCount.hidden = !(r.ok && r.count);
  };
  extraEl.value = settings.extra_json || '';
  refreshExtra();
  extraEl.addEventListener('input', () => {
    settings.extra_json = extraEl.value;
    refreshExtra();
    saveSettings();
  });

  /* ---- 设置栏：移动端抽屉 / 桌面端折叠（记忆在 localStorage） ---- */
  const pageEl = section.querySelector('.chat-page');
  const isMobile = () => matchMedia('(max-width: 900px)').matches;
  pageEl.classList.toggle('settings-hidden', localStorage.getItem(HIDE_SETTINGS_KEY) === '1');
  const toggleSettings = () => {
    if (isMobile()) {
      pageEl.classList.toggle('chat-settings-open');
      return;
    }
    const hidden = pageEl.classList.toggle('settings-hidden');
    localStorage.setItem(HIDE_SETTINGS_KEY, hidden ? '1' : '0');
  };
  section.querySelector('#chat-settings-toggle').addEventListener('click', toggleSettings);
  section.querySelector('#chat-settings-close').addEventListener('click', () => {
    if (isMobile()) pageEl.classList.remove('chat-settings-open');
    else toggleSettings();
  });
  section.querySelector('#chat-meta-model').addEventListener('click', () => {
    if (isMobile() || pageEl.classList.contains('settings-hidden')) toggleSettings();
  });
  section.querySelector('#chat-meta-persona').addEventListener('click', () => {
    if (isMobile() || pageEl.classList.contains('settings-hidden')) toggleSettings();
  });
  updateMeta();
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

  /* 粘贴图片/文件直接上传 */
  textEl.addEventListener('paste', (e) => {
    const files = [...(e.clipboardData?.files || [])];
    if (!files.length) return;
    e.preventDefault();
    for (const file of files) {
      /* 剪贴板截图文件名统一为 image.png，以时间戳区分 */
      const named = file.name === 'image.png'
        ? new File([file], `paste-${Date.now()}.png`, { type: file.type })
        : file;
      uploadFile(named);
    }
  });

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
    const extra = parseExtraJson(settings.extra_json);
    if (!extra.ok) {
      toast(`额外请求 JSON 无效：${extra.error}`, 'error', 5000);
      pageEl.classList.add('chat-settings-open');
      pageEl.classList.remove('settings-hidden');
      return;
    }

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
  scrollBtn = null;
  activeTurn = null;
  pendingAttachments = [];
}

export const chatView = { title: 'AI 聊天', init, destroy };
