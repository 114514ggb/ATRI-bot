/* 配置编辑器共享套件：保存栏 / diff 模态 / 保存后重启流程 / 深度工具 */

import { api } from '../api.js';
import { icon, toast, openModal, confirmDialog, escapeHtml } from '../ui.js';

/* ---------- 深度工具 ---------- */

export function deepClone(obj) {
  return structuredClone ? structuredClone(obj) : JSON.parse(JSON.stringify(obj));
}

export function getPath(obj, path) {
  return path.split('.').reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
}

export function setPath(obj, path, value) {
  const keys = path.split('.');
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (typeof cur[keys[i]] !== 'object' || cur[keys[i]] === null) cur[keys[i]] = {};
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
}

export function unsetPath(obj, path) {
  const keys = path.split('.');
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (typeof cur[keys[i]] !== 'object' || cur[keys[i]] === null) return;
    cur = cur[keys[i]];
  }
  delete cur[keys[keys.length - 1]];
}

export function fmtVal(v) {
  if (v === undefined) return '(不存在)';
  const s = JSON.stringify(v);
  return s === undefined ? String(v) : s.length > 80 ? s.slice(0, 80) + '…' : s;
}

/** 递归 diff，返回 [{path, old, new}]（数组按整体比较） */
export function diffObjects(a, b, path = '', out = []) {
  const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

  if (isObj(a) && isObj(b)) {
    const keys = new Set([...Object.keys(a || {}), ...Object.keys(b || {})]);
    for (const key of keys) {
      diffObjects(a?.[key], b?.[key], path ? `${path}.${key}` : key, out);
    }
    return out;
  }

  const ja = JSON.stringify(a);
  const jb = JSON.stringify(b);
  if (ja !== jb) out.push({ path: path || '(root)', old: a, new: b });
  return out;
}

/* ---------- diff 确认模态 ---------- */

export function showDiffModal(diffs) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (v) => { if (!settled) { settled = true; resolve(v); } };

    const items = diffs.slice(0, 80).map((d, i) => {
      const added = d.old === undefined;
      const removed = d.new === undefined;
      return `
        <div class="diff-item" style="animation-delay:${Math.min(i * 25, 400)}ms">
          <span class="path">${escapeHtml(d.path)}</span>
          ${added
            ? `<span class="vals"><span class="new">+ ${escapeHtml(fmtVal(d.new))}</span></span>`
            : removed
              ? `<span class="vals"><span class="old">- ${escapeHtml(fmtVal(d.old))}</span></span>`
              : `<span class="vals"><span class="old">- ${escapeHtml(fmtVal(d.old))}</span><span class="new">+ ${escapeHtml(fmtVal(d.new))}</span></span>`}
        </div>`;
    }).join('');

    openModal({
      title: `确认保存 · 共 ${diffs.length} 处更改`,
      wide: true,
      bodyHtml: `
        <p style="margin:0 0 12px;color:var(--text-3)">以下字段将被写入配置文件（保存前会自动生成 .bak 备份）：</p>
        <div class="diff-list">${items}</div>
        ${diffs.length > 80 ? `<p class="small" style="color:var(--text-3)">…仅显示前 80 条，共 ${diffs.length} 处</p>` : ''}`,
      actions: [
        { label: '取消', class: 'ghost', onClick: ({ close }) => { finish(false); close(); } },
        { label: `${icon('save')} 保存`, class: 'primary', onClick: ({ close }) => { finish(true); close(); } },
      ],
      onClose: () => finish(false),
    });
  });
}

/* ---------- 保存后流程 ---------- */

/** 保存成功后的「需要重启」询问，返回是否触发了重启 */
export async function needsRestartFlow(thing = '配置') {
  const ok = await confirmDialog({
    title: '需要重启生效',
    message: `${thing}已写入文件。大部分配置在服务启动时加载，<b>需要重启 bot 进程</b>才能生效。<br>是否立即重启？`,
    confirmText: '立即重启',
    cancelText: '稍后手动重启',
    danger: true,
  });
  if (!ok) return false;
  await restartAndWait();
  return true;
}

export async function restartAndWait() {
  try {
    await api.post('/system/restart');
  } catch { /* 进程可能立即退出导致请求中断，忽略 */ }

  const mask = document.createElement('div');
  mask.className = 'fullscreen-mask';
  mask.innerHTML = `
    <div class="spinner"></div>
    <div class="mask-title">正在重启…</div>
    <div class="mask-sub">等待服务恢复（如果长时间未恢复，请手动检查 bot 进程）</div>`;
  document.body.appendChild(mask);

  const started = Date.now();
  const poll = async () => {
    try {
      await api.get('/status');
      mask.remove();
      toast('服务已恢复运行', 'success');
    } catch {
      if (Date.now() - started > 120000) {
        mask.remove();
        toast('等待恢复超时，请手动检查 bot 状态', 'error', 6000);
        return;
      }
      setTimeout(poll, 2000);
    }
  };
  setTimeout(poll, 2500);
}

/* ---------- 保存操作栏 ---------- */

/**
 * 渲染顶部保存栏
 * @returns {{ setDirty:(b:boolean)=>void, setMode:(m:string)=>void }}
 */
export function renderSaveBar(root, { pathLabel, onModeChange, onDiff, onSave, onRollback, onDownload, onFormat }) {
  root.className = 'save-bar';
  root.innerHTML = `
    <div class="seg" role="tablist">
      <button data-mode="form" class="active">表单模式</button>
      <button data-mode="source">源码模式</button>
    </div>
    <span class="dirty-badge clean" data-dirty></span>
    <span class="path-label" title="${escapeHtml(pathLabel)}">${escapeHtml(pathLabel)}</span>
    ${onFormat ? `<button class="btn sm ghost" data-op="format">${icon('sliders')} 格式化</button>` : ''}
    ${onDownload ? `<button class="btn sm ghost" data-op="download">${icon('download')} 下载</button>` : ''}
    ${onRollback ? `<button class="btn sm ghost" data-op="rollback">${icon('rollback')} 回滚备份</button>` : ''}
    ${onDiff ? `<button class="btn sm" data-op="diff">${icon('search')} 查看更改</button>` : ''}
    <button class="btn primary" data-op="save">${icon('save')} 保存</button>`;

  const dirtyBadge = root.querySelector('[data-dirty]');

  root.querySelectorAll('[data-mode]').forEach((btn) => {
    btn.addEventListener('click', () => {
      root.querySelectorAll('[data-mode]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      onModeChange(btn.dataset.mode);
    });
  });

  const ops = { format: onFormat, download: onDownload, rollback: onRollback, diff: onDiff, save: onSave };
  root.querySelectorAll('[data-op]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const fn = ops[btn.dataset.op];
      if (fn) fn();
    });
  });

  return {
    setDirty(dirty) {
      dirtyBadge.className = `dirty-badge ${dirty ? '' : 'clean'}`;
      dirtyBadge.innerHTML = dirty ? `${icon('alert')} 有未保存的更改` : `${icon('check')} 无更改`;
    },
    setMode(mode) {
      root.querySelectorAll('[data-mode]').forEach((b) => b.classList.toggle('active', b.dataset.mode === mode));
    },
  };
}

/** 触发浏览器下载文本文件 */
export function downloadText(filename, text) {
  const blob = new Blob([text], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
