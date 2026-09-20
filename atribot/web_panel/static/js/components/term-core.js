/* 终端核心组件：WS 会话 + 输入语法高亮 + 历史 + Tab 补全 + 输出渲染
   主机终端与沙盒终端共用，两者通过同一套 WS 协议（hello/exec/output/exit/kill）交互 */

import { escapeHtml, icon } from '../ui.js';

/* 输入行语法高亮的词法分组：字符串 / 变量 / 操作符 / 选项 / 路径 / 注释 / 裸词 */
const TOKEN_RX = /("(?:[^"\\]|\\.)*"?|'(?:[^'\\]|\\.)*'?)|(\$\{?[A-Za-z_]\w*\}?|%[^%\s]+%)|(\d*>>?&?\d*|\|\||&&|<|[|&;])|(-{1,2}[A-Za-z][\w-]*)|((?:[A-Za-z]:)?[^|&;<>\s"']*[/\\][^|&;<>\s"']*)|(#.*)|(\S+)/g;

const TOKEN_STOP = /[\s|&;<>"']/;

const BUILTIN_WIN = new Set('cd dir echo type copy del ren md rd move cls set ver where findstr more tasklist taskkill exit rem mklink robocopy attrib chcp color title call start pause shift for if goto pushd popd setlocal endlocal sc net reg schtasks curl tar'.split(' '));
const BUILTIN_UNIX = new Set('cd ls pwd echo cat grep rm cp mv mkdir rmdir touch chmod chown ps kill top df du tar curl wget ssh scp nano vim head tail wc find sed awk sort uniq man which env export source alias history clear exit sudo systemctl journalctl apt yum dnf pacman docker git python python3 pip pip3 node npm'.split(' '));

const HIST_MAX = 200;
const MAX_DOM_NODES = 1200;

/**
 * 在 mount 元素内创建一个终端实例
 * opts:
 *   - wsUrl: 终端 WebSocket 地址（token 已含在 query）
 *   - historyKey: 历史记录的 localStorage 键
 *   - banner(info): 首次 hello 时打印的问候行数组
 *   - allowComplete: 是否启用 Tab 补全（默认 true；后端不回应 complete 即为空）
 */
export function createTerminal(mount, opts = {}) {
  const historyKey = opts.historyKey || 'atri_term_history';
  const allowComplete = opts.allowComplete !== false;

  let ws = null;
  let running = true;
  let connected = false;
  let bannerShown = false;
  let reconnectDelay = 1000;
  let reconnectTimer = null;

  let busy = false;
  let isWin = false;
  let cwd = '';
  let home = '';
  let sep = '/';
  let user = '';
  let host = '';
  let known = new Set();
  let builtins = BUILTIN_UNIX;

  let history = [];
  let histIdx = -1;
  let histDraft = '';

  let outBlock = null; // 当前命令的输出块（文本节点持续追加，保证跨块行不断行）
  let pinned = true; // 滚动是否贴底（贴底时新输出自动滚动）
  let completeSeq = 0;
  let pendingComplete = null;
  let pingTimer = null;
  let pongDeadline = 0; // 未在此时刻前收到 pong 则强制重建连接
  let execWatchdog = null; // exec 后长时间无任何回音：连接大概率半死，强制重建
  let helloWatchdog = null; // open 后迟迟收不到 hello：握手卡死，强制重建
  let reconnectAttempts = 0; // 连续未成功握手的重连次数（收到 hello 归零）
  let diagShown = false; // 连续失败诊断提示是否已打印（本轮连接问题内只提示一次）

  mount.innerHTML = `
    <div class="term-toolbar">
      <span style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600">
        <span class="dot yellow js-conn-dot"></span><span class="js-conn-text">连接中…</span>
      </span>
      <span class="term-cwd js-cwd"></span>
      <span style="flex:1"></span>
      <label class="check-row" title="输出贴底时自动滚动"><input type="checkbox" class="js-autoscroll" checked>自动滚动</label>
      <button class="btn sm ghost js-kill" disabled>${icon('x')} 终止</button>
      <button class="btn sm ghost js-clear">${icon('trash')} 清屏</button>
    </div>
    <div class="term-box js-box">
      <div class="term-scroll js-scroll">
        <div class="js-out"></div>
        <div class="term-input-row">
          <span class="term-prompt js-prompt"></span>
          <div class="term-input-wrap">
            <div class="term-hl js-hl"></div>
            <input class="term-input js-input" autocomplete="off" autocapitalize="off"
                   autocorrect="off" spellcheck="false" aria-label="终端命令输入">
          </div>
        </div>
      </div>
    </div>`;

  const q = (sel) => mount.querySelector(sel);
  const input = q('.js-input');
  const out = q('.js-out');
  const scroll = q('.js-scroll');
  const hasSelection = () => String(window.getSelection ? window.getSelection() : '').length > 0;

  /* 未连接前禁用输入：避免"看起来能打字但命令不会执行"的困惑 */
  function setInputEnabled(on) {
    input.disabled = !on;
    input.placeholder = on ? '' : '正在连接终端服务…';
  }
  setInputEnabled(false);

  q('.js-autoscroll').addEventListener('change', (e) => { pinned = e.target.checked; });
  scroll.addEventListener('scroll', () => {
    pinned = scroll.scrollTop + scroll.clientHeight >= scroll.scrollHeight - 24;
    q('.js-autoscroll').checked = pinned;
  });
  const requestKill = () => {
    send({ type: 'kill' });
    q('.js-kill').innerHTML = `${icon('x')} 终止中…`;
  };
  q('.js-kill').addEventListener('click', () => {
    if (!busy) return;
    requestKill();
  });
  q('.js-clear').addEventListener('click', clearScreen);

  /* 点击终端任意空白处聚焦输入行（选中文本时除外） */
  q('.js-box').addEventListener('mouseup', (e) => {
    if (hasSelection()) return;
    if (e.target.closest('button')) return;
    input.focus();
  });

  input.addEventListener('input', refreshInput);
  input.addEventListener('keydown', onKeydown);
  input.addEventListener('keyup', syncScroll);
  input.addEventListener('focus', () => setTimeout(syncScroll, 0));

  loadHistory();
  connect();

  /* ---------- WebSocket ---------- */

  /* 状态圆点只增删颜色类，绝不整体覆写 className——元素上的 js-conn-dot
     钩子类一旦被覆写剥掉，之后所有 q('.js-conn-dot') 都会返回 null */
  function setDot(el, color) {
    if (!el) return;
    el.classList.remove('yellow', 'green', 'red');
    el.classList.add(color);
  }

  /* 连接生命周期事件日志：带时间戳写进终端输出，用户可直接看到发生了什么 */
  function logEvent(text) {
    appendNote(`[${new Date().toTimeString().slice(0, 8)}] ${text}`);
  }

  function connect() {
    if (!running) return;
    setDot(q('.js-conn-dot'), 'yellow');
    q('.js-conn-text').textContent = reconnectAttempts > 0 ? `第 ${reconnectAttempts + 1} 次尝试连接…` : '连接中…';
    setInputEnabled(false);
    clearHelloWatchdog();

    if (ws) {
      try { ws.onclose = null; ws.close(); } catch { /* ignore */ }
      ws = null;
    }

    let sock;
    try {
      sock = new WebSocket(opts.wsUrl);
    } catch {
      scheduleReconnect();
      return;
    }
    ws = sock;

    ws.onopen = () => {
      reconnectDelay = 1000;
      /* 握手看门狗：open 后 8s 仍未收到 hello 视为握手卡死，强制重建 */
      clearTimeout(helloWatchdog);
      helloWatchdog = setTimeout(() => {
        if (!running || connected || ws !== sock) return;
        try { sock.onclose = null; sock.close(); } catch { /* ignore */ }
        onSocketLost();
        reconnectAttempts += 1;
        maybeDiagnose();
        logEvent('握手超时（8 秒未收到 hello），正在重建连接');
        connect();
      }, 8000);
      /* 应用层保活：socket 一旦 open 即开始（不等 hello），pong 超时强制重建 */
      clearInterval(pingTimer);
      pongDeadline = 0;
      pingTimer = setInterval(() => {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        if (pongDeadline && Date.now() > pongDeadline) {
          try { ws.onclose = null; ws.close(); } catch { /* ignore */ }
          onSocketLost();
          reconnectAttempts += 1;
          maybeDiagnose();
          logEvent('保活超时（pong 未响应），正在重建连接');
          connect();
          return;
        }
        pongDeadline = Date.now() + 4000;
        send({ type: 'ping' });
      }, 5000);
    };

    ws.onmessage = (event) => {
      clearExecWatchdog();
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.type === 'pong') {
        pongDeadline = 0;
        return;
      }
      if (msg.type === 'hello') onHello(msg);
      else if (msg.type === 'output') appendOutput(msg.data || '');
      else if (msg.type === 'exit') onExit(msg);
      else if (msg.type === 'complete') onComplete(msg);
    };

    ws.onclose = (event) => {
      clearHelloWatchdog();
      onSocketLost();
      if (!running) return;
      reconnectAttempts += 1;
      const reason = event.code === 4401 ? '令牌无效'
        : event.code === 4429 ? '尝试次数过多已锁定，等待解锁'
          : event.code === 4450 ? '沙盒未初始化'
            : event.code === 4451 ? '当前沙盒后端不支持终端'
              : '将自动重试';
      setDot(q('.js-conn-dot'), 'red');
      q('.js-conn-text').textContent = `连接断开（${reason}）`;
      logEvent(`连接断开（${reason}，code=${event.code}）`);
      maybeDiagnose();
      if (event.code !== 4401 && event.code !== 4451) scheduleReconnect();
    };

    ws.onerror = () => { /* onclose 会跟进 */ };
  }

  function onSocketLost() {
    connected = false;
    busy = false;
    outBlock = null;
    updateToolbar();
  }

  function clearHelloWatchdog() {
    clearTimeout(helloWatchdog);
    helloWatchdog = null;
  }

  function maybeDiagnose() {
    if (diagShown || reconnectAttempts < 3) return;
    diagShown = true;
    logEvent('多次尝试仍无法建立终端连接：请确认 bot 已重启加载新代码、访问令牌正确，且浏览器到面板之间没有不支持 WebSocket 的代理');
    scrollBottom(true);
  }

  function scheduleReconnect() {
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 15000);
      connect();
    }, reconnectDelay);
    logEvent(`${Math.round(reconnectDelay / 1000)} 秒后重连`);
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }

  function clearExecWatchdog() {
    clearTimeout(execWatchdog);
    execWatchdog = null;
  }

  function armExecWatchdog() {
    execWatchdog = setTimeout(() => {
      if (!running || !busy) return;
      /* exec 发出后长时间无任何帧：连接多半已半死，强制重建等自愈 */
      try { ws.onclose = null; ws.close(); } catch { /* ignore */ }
      onSocketLost();
      reconnectAttempts += 1;
      maybeDiagnose();
      logEvent('命令无响应，连接疑似半死，正在重建');
      connect();
    }, 10000);
  }

  function onHello(msg) {
    connected = true;
    reconnectAttempts = 0;
    diagShown = false;
    clearHelloWatchdog();
    isWin = !!msg.isWindows;
    cwd = msg.cwd || '';
    home = msg.home || '';
    sep = msg.sep || (isWin ? '\\' : '/');
    user = msg.user || '?';
    host = msg.host || '';
    known = new Set(msg.commands || []);
    builtins = isWin ? BUILTIN_WIN : BUILTIN_UNIX;

    renderPrompt();
    updateToolbar();
    setInputEnabled(true);
    logEvent(bannerShown ? '连接成功' : '终端连接已建立');
    if (bannerShown) {
      appendNote('— 已重新连接 —');
    } else {
      bannerShown = true;
      const lines = opts.banner ? opts.banner(msg)
        : [`终端 · ${user}@${host} · ${msg.platform || ''}`, 'Tab 补全 · ↑↓ 历史 · Ctrl+C 终止 · Ctrl+L 清屏'];
      for (const line of lines) appendNote(line);
    }
    input.focus();
  }

  function onExit(msg) {
    busy = false;
    clearExecWatchdog();
    const ms = msg.ms || 0;
    const dur = ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
    const code = msg.code;
    const label = code === 0 ? '完成' : code < 0 ? `已终止（${code}）` : `退出码 ${code}`;
    appendMeta(`↳ ${label} · ${dur}`, code !== 0);
    if (typeof msg.cwd === 'string' && msg.cwd) {
      cwd = msg.cwd;
      renderPrompt();
    }
    updateToolbar();
    scrollBottom(true);
    input.focus();
  }

  /* ---------- 渲染 ---------- */

  function shortenCwd(p) {
    if (!home || !p) return p;
    const norm = (s) => (isWin ? s.toLowerCase().replace(/\//g, '\\') : s);
    const h = norm(home);
    const np = norm(p);
    if (np === h) return '~';
    if (np.startsWith(h + '\\')) return '~' + p.slice(home.length);
    return p;
  }

  function promptHtml() {
    const sym = isWin ? '>' : '$';
    return `<span class="tp-user">${escapeHtml(user)}@${escapeHtml(host)}</span>`
      + ` <span class="tp-path" title="${escapeHtml(cwd)}">${escapeHtml(shortenCwd(cwd))}</span>`
      + ` <span class="tp-sym">${sym}</span>`;
  }

  function renderPrompt() {
    q('.js-prompt').innerHTML = promptHtml();
  }

  function cmdClass(raw) {
    const fold = (s) => (isWin ? s.toLowerCase() : s);
    const lower = fold(raw);
    if (builtins.has(lower)) return 't-builtin';
    if (known.has(lower)) return 't-cmd';
    return 't-unknown';
  }

  function highlight(cmd) {
    if (!cmd) return '';
    if (!connected) return escapeHtml(cmd);
    let html = '';
    let last = 0;
    let atCmd = true; // 下一个裸词处于命令位（行首或操作符之后）
    TOKEN_RX.lastIndex = 0;
    let m;
    while ((m = TOKEN_RX.exec(cmd))) {
      const gap = cmd.slice(last, m.index);
      if (gap) html += escapeHtml(gap);
      last = m.index + m[0].length;
      const raw = m[0];
      let cls = '';
      if (m[1]) cls = 't-str';
      else if (m[2]) cls = 't-var';
      else if (m[3]) cls = 't-op';
      else if (m[4]) cls = 't-flag';
      else if (m[5]) cls = atCmd ? cmdClass(raw) : 't-path';
      else if (m[6]) cls = 't-comment';
      else if (m[7]) cls = atCmd ? cmdClass(raw) : '';
      html += cls ? `<span class="${cls}">${escapeHtml(raw)}</span>` : escapeHtml(raw);
      atCmd = !!m[3]; // 操作符（管道/逻辑/分号）之后回到命令位
    }
    html += escapeHtml(cmd.slice(last));
    return html;
  }

  function refreshInput() {
    q('.js-hl').innerHTML = highlight(input.value) + '\u200b'; /* 零宽字符保尾随空格宽度 */
    syncScroll();
  }

  function syncScroll() {
    q('.js-hl').scrollLeft = input.scrollLeft;
  }

  function appendLine(html) {
    const el = document.createElement('div');
    el.className = 'term-line';
    el.innerHTML = html;
    out.appendChild(el);
    trimNodes();
    scrollBottom();
  }

  function appendNote(text) {
    const el = document.createElement('div');
    el.className = 'term-line term-note';
    el.textContent = text;
    out.appendChild(el);
    trimNodes();
    scrollBottom();
  }

  function appendMeta(text, bad = false) {
    const el = document.createElement('div');
    el.className = `term-meta${bad ? ' bad' : ''}`;
    el.textContent = text;
    out.appendChild(el);
    trimNodes();
    scrollBottom();
  }

  function appendOutput(text) {
    if (!outBlock) {
      outBlock = document.createElement('div');
      outBlock.className = 'term-line term-output';
      out.appendChild(outBlock);
    }
    outBlock.appendChild(document.createTextNode(text));
    trimNodes();
    scrollBottom();
  }

  function trimNodes() {
    while (out.children.length > MAX_DOM_NODES) out.removeChild(out.firstChild);
  }

  function scrollBottom(force = false) {
    if (force || pinned) scroll.scrollTop = scroll.scrollHeight;
  }

  function clearScreen() {
    out.innerHTML = '';
    outBlock = null;
  }

  /* ---------- 输入与快捷键 ---------- */

  function onKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      exec(input.value);
    } else if (e.key === 'Tab') {
      e.preventDefault();
      if (allowComplete) onTab();
    } else if (e.key === 'ArrowUp' && !e.shiftKey) {
      e.preventDefault();
      histPrev();
    } else if (e.key === 'ArrowDown' && !e.shiftKey) {
      e.preventDefault();
      histNext();
    } else if (e.ctrlKey && (e.key === 'c' || e.key === 'C')) {
      /* 有选区时保留浏览器复制行为 */
      if (hasSelection()) return;
      e.preventDefault();
      if (busy) {
        requestKill();
      } else {
        echoCommand(input.value + '^C');
        input.value = '';
        refreshInput();
      }
    } else if (e.ctrlKey && (e.key === 'l' || e.key === 'L')) {
      e.preventDefault();
      clearScreen();
    } else if (e.ctrlKey && (e.key === 'u' || e.key === 'U')) {
      e.preventDefault();
      input.value = '';
      refreshInput();
    }
  }

  function exec(raw) {
    const cmd = raw.trim();
    if (!cmd) {
      echoCommand('');
      return;
    }
    if (!connected) {
      appendNote('[终端未连接，等待重连…]');
      scrollBottom(true);
      return;
    }
    if (busy) {
      appendNote('[已有命令在执行，请等待完成或按 Ctrl+C 终止]');
      scrollBottom(true);
      return;
    }

    const lower = cmd.toLowerCase();
    if (lower === 'cls' || lower === 'clear') {
      echoCommand(cmd);
      clearScreen();
      return;
    }
    if (lower === 'history') {
      echoCommand(cmd);
      const start = Math.max(0, history.length - 50);
      history.slice(start).forEach((h, i) => appendMeta(`${String(start + i + 1).padStart(4)}  ${h}`));
      scrollBottom(true);
      return;
    }

    echoCommand(cmd);
    pushHistory(cmd);
    histIdx = -1;
    histDraft = '';
    outBlock = null;
    busy = true;
    updateToolbar();
    send({ type: 'exec', cmd });
    armExecWatchdog();
    input.value = '';
    refreshInput();
  }

  function echoCommand(text) {
    appendLine(`${promptHtml()} ${highlight(text.replace(/\^C$/, ''))}<span class="tp-sym">${text.endsWith('^C') ? '^C' : ''}</span>`);
  }

  function updateToolbar() {
    const text = q('.js-conn-text');
    const cwdEl = q('.js-cwd');
    const killBtn = q('.js-kill');
    setDot(q('.js-conn-dot'), connected ? 'green' : 'red');
    if (connected) text.textContent = busy ? '执行中…' : '已连接';
    cwdEl.textContent = shortenCwd(cwd);
    cwdEl.title = cwd;
    killBtn.disabled = !busy;
    if (!busy) killBtn.innerHTML = `${icon('x')} 终止`;
  }

  /* ---------- 历史 ---------- */

  function loadHistory() {
    try {
      const raw = JSON.parse(localStorage.getItem(historyKey) || '[]');
      history = Array.isArray(raw) ? raw.filter((h) => typeof h === 'string').slice(-HIST_MAX) : [];
    } catch {
      history = [];
    }
  }

  function saveHistory() {
    try { localStorage.setItem(historyKey, JSON.stringify(history)); } catch { /* ignore */ }
  }

  function pushHistory(cmd) {
    history = history.filter((h) => h !== cmd);
    history.push(cmd);
    if (history.length > HIST_MAX) history = history.slice(-HIST_MAX);
    saveHistory();
  }

  function histPrev() {
    if (!history.length) return;
    if (histIdx === -1) {
      histDraft = input.value;
      histIdx = history.length - 1;
    } else if (histIdx > 0) {
      histIdx--;
    }
    input.value = history[histIdx] || '';
    moveCaretToEnd();
  }

  function histNext() {
    if (histIdx === -1) return;
    histIdx++;
    if (histIdx >= history.length) {
      histIdx = -1;
      input.value = histDraft;
    } else {
      input.value = history[histIdx];
    }
    moveCaretToEnd();
  }

  function moveCaretToEnd() {
    const pos = input.value.length;
    input.setSelectionRange(pos, pos);
    refreshInput();
  }

  /* ---------- Tab 补全 ---------- */

  function onTab() {
    if (busy || !connected) return;
    const caret = input.selectionStart ?? input.value.length;
    const tok = parseToken(input.value.slice(0, caret));
    const first = tok.isFirst && !tok.hasSep && !tok.quote && !tok.dir && !tok.body.startsWith('~');
    send({ type: 'complete', id: ++completeSeq, dir: tok.dir, frag: tok.frag, first });
    pendingComplete = { id: completeSeq, _tok: tok, first };
  }

  function parseToken(text) {
    let i = text.length;
    while (i > 0 && !TOKEN_STOP.test(text[i - 1])) i--;
    const rawStart = i;
    let quote = '';
    /* 紧贴 token 开头的引号视为引用前缀（如 echo "C:\Pro） */
    if (rawStart > 0 && (text[rawStart - 1] === '"' || text[rawStart - 1] === "'") && (rawStart - 1 === 0 || TOKEN_STOP.test(text[rawStart - 2]))) {
      quote = text[rawStart - 1];
    }
    const body = text.slice(rawStart);
    const isFirst = text.slice(0, rawStart).trim() === '';
    const hasSep = /[/\\]/.test(body);
    const m = body.match(/^(.*[/\\])?([^/\\]*)$/);
    return { bodyStart: rawStart, quote, body, isFirst, hasSep, dir: m[1] || '', frag: m[2] || '' };
  }

  function onComplete(msg) {
    if (!pendingComplete || msg.id !== pendingComplete.id) return;
    const tok = pendingComplete._tok;
    const asCmd = pendingComplete.first;
    pendingComplete = null;
    const items = msg.items || [];
    if (!items.length) return;
    if (asCmd) {
      /* 命令名补全：目录项也当作普通名字处理 */
      applyCompletion(tok, items.map((it) => ({ name: it.name, dir: false })), true);
    } else {
      applyCompletion(tok, items, false);
    }
  }

  function applyCompletion(tok, items, isCmd) {
    const caret = input.selectionStart ?? input.value.length;
    const names = items.map((it) => it.name);
    const eq = (a, b) => (isWin ? a.toLowerCase() === b.toLowerCase() : a === b);

    /* 计算公共前缀 */
    let prefix = names[0];
    for (const n of names.slice(1)) {
      let i = 0;
      while (i < prefix.length && i < n.length && eq(prefix[i], n[i])) i++;
      prefix = prefix.slice(0, i);
    }

    const single = items.length === 1;
    const fold = (s) => (isWin ? s.toLowerCase() : s);
    const extended = single || fold(prefix).length > fold(tok.frag).length;

    if (extended) {
      const completed = single ? names[0] : names[0].slice(0, prefix.length);
      const isDir = single ? items[0].dir : false;
      let body = tok.dir + completed;
      if (isCmd) {
        body += ' ';
      } else {
        if (single && isDir) body += sep;
        if (tok.quote) {
          body = tok.quote + body + (single && !isDir ? tok.quote : '');
        } else if (single && /[\s"]/.test(body)) {
          body = `"${body}"`;
        }
      }
      const before = input.value.slice(0, tok.bodyStart);
      const after = input.value.slice(caret);
      input.value = before + body + after;
      const pos = tok.bodyStart + body.length;
      input.setSelectionRange(pos, pos);
      refreshInput();
    } else {
      /* 无法继续延伸：把候选打印到输出区 */
      const shown = names.slice(0, 80).join('  ');
      appendMeta(names.length > 80 ? `${shown}\n… 共 ${names.length} 个候选` : shown);
      scrollBottom(true);
    }
  }

  /* ---------- 生命周期 ---------- */

  function destroy() {
    running = false;
    connected = false;
    clearTimeout(reconnectTimer);
    clearInterval(pingTimer);
    clearHelloWatchdog();
    clearExecWatchdog();
    if (ws) {
      /* 先解绑回调再关闭：防止 close 完成前的在途帧触发已销毁实例的 DOM 更新 */
      try { ws.onopen = null; ws.onmessage = null; ws.onclose = null; ws.onerror = null; ws.close(); } catch { /* ignore */ }
      ws = null;
    }
  }

  return { destroy, clearScreen, focus: () => input.focus() };
}
