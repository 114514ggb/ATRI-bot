/* 视图：人设管理（character_setting/*.txt 在线编辑） */

import { api } from '../api.js';
import { icon, toast, escapeHtml, confirmDialog, openModal } from '../ui.js';

let list = [];
let currentKey = null;
let currentContent = '';
let defaultRole = 'none';

async function init(section) {
  section.innerHTML = `
    <div class="notice info">${icon('info')}<div>保存人设会立即热刷新内存中的人设列表；但<b>已进行中的会话仍持有旧人设文本</b>，需要在群里用 <code>/chat reset</code> 重置上下文后才会完全生效。删除当前默认人设前需先切换默认。</div></div>
    <div class="persona-layout">
      <div>
        <div class="persona-list" id="persona-list">${'<div class="skeleton" style="height:56px;border-radius:12px;margin-bottom:8px"></div>'.repeat(4)}</div>
        <button class="btn sm" id="btn-new-persona" style="margin-top:12px">${icon('plus')} 新建人设</button>
      </div>
      <div class="card persona-editor" id="persona-editor">
        <p class="muted" style="margin:0">选择左侧人设开始编辑</p>
      </div>
    </div>`;

  section.querySelector('#btn-new-persona').addEventListener('click', promptCreate);
  await reload(section);
}

async function reload(section) {
  const listBox = section.querySelector('#persona-list');
  if (listBox) listBox.innerHTML = '<div class="skeleton" style="height:56px;border-radius:12px;margin-bottom:8px"></div>'.repeat(4);
  try {
    const res = await api.get('/personas');
    list = res.items || [];
    defaultRole = res.default || 'none';
  } catch (e) {
    if (listBox) listBox.innerHTML = `<div class="notice danger">${icon('alert')}<div>加载人设列表失败：${escapeHtml(e.message)}</div></div>`;
    toast(`加载人设列表失败：${e.message}`, 'error', 5000);
    return;
  }

  listBox.innerHTML =
    list
      .map(
        (p, i) => `<div class="persona-item ${p.key === currentKey ? 'active' : ''}" data-key="${escapeHtml(p.key)}" style="animation-delay:${Math.min(i * 45, 350)}ms">
          <span style="color:${p.is_default ? 'var(--orange)' : 'var(--text-caption)'}">${icon('star')}</span>
          <span class="p-name">${escapeHtml(p.key)}</span>
          <span class="p-meta">${p.is_default ? '默认' : `${(p.size / 1024).toFixed(1)}K`}</span>
        </div>`
      )
      .join('') || '<p class="muted small">人设目录为空</p>';

  listBox.querySelectorAll('.persona-item').forEach((el) => {
    el.addEventListener('click', () => openPersona(el.dataset.key));
  });

  if (!currentKey && list.length) openPersona(list[0].key);
  else if (currentKey && list.some((p) => p.key === currentKey)) openPersona(currentKey);
  else renderEditor(section);
}

let personaReqId = 0;

async function openPersona(key) {
  currentKey = key;
  const reqId = ++personaReqId;
  const section = document.getElementById('view-personas');
  const editorBox = section?.querySelector('#persona-editor');

  /* 立即高亮选中项并在编辑区画骨架，读取期间有明确反馈 */
  document.querySelectorAll('.persona-item').forEach((el) => el.classList.toggle('active', el.dataset.key === key));
  if (editorBox) {
    editorBox.innerHTML = `
      <div class="skeleton" style="height:24px;width:200px;border-radius:8px;margin-bottom:16px"></div>
      <div class="skeleton" style="height:300px;border-radius:12px"></div>`;
  }

  try {
    const res = await api.get(`/personas/${encodeURIComponent(key)}`);
    if (reqId !== personaReqId) return; /* 用户已点击其他人设，丢弃过期响应 */
    currentContent = res.content;
    renderEditor(section);
  } catch (e) {
    if (reqId !== personaReqId) return;
    if (editorBox) editorBox.innerHTML = `<div class="notice danger">${icon('alert')}<div>读取人设失败：${escapeHtml(e.message)}</div></div>`;
    toast(`读取人设失败：${e.message}`, 'error', 5000);
  }
}

function renderEditor(section) {
  const box = section.querySelector('#persona-editor');
  if (!currentKey) {
    box.innerHTML = '<p class="muted" style="margin:0">选择左侧人设开始编辑</p>';
    return;
  }
  const isDefault = defaultRole === currentKey;
  box.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap">
      <h3 style="margin:0;font-size:16px">${escapeHtml(currentKey)} ${isDefault ? '<span class="badge orange">当前默认</span>' : ''}</h3>
      <span style="flex:1"></span>
      ${!isDefault ? `<button class="btn sm ghost" id="btn-set-default">${icon('star')} 设为默认</button>` : ''}
      <button class="btn sm danger ghost" id="btn-del-persona" style="color:var(--red)">${icon('trash')} 删除</button>
      <button class="btn sm primary" id="btn-save-persona">${icon('save')} 保存</button>
    </div>
    <textarea id="persona-content" spellcheck="false">${escapeHtml(currentContent)}</textarea>`;

  box.querySelector('#btn-save-persona').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    const content = box.querySelector('#persona-content').value;
    btn.classList.add('loading');
    try {
      const res = await api.put(`/personas/${encodeURIComponent(currentKey)}`, { content });
      currentContent = content;
      btn.classList.remove('loading');
      toast(res.refreshed ? '已保存并热刷新人设列表' : '已保存（人设服务未运行，仅写入文件）', 'success');
    } catch (err) {
      btn.classList.remove('loading');
      toast(`保存失败：${err.message}`, 'error', 5000);
    }
  });

  box.querySelector('#btn-del-persona')?.addEventListener('click', async () => {
    if (!(await confirmDialog({ title: '删除人设', message: `确定删除人设 <b>${escapeHtml(currentKey)}</b> 吗？文件会先备份为 .bak。`, danger: true, confirmText: '删除' }))) return;
    try {
      await api.del(`/personas/${encodeURIComponent(currentKey)}`);
      toast('已删除', 'success');
      currentKey = null;
      reload(document.getElementById('view-personas'));
    } catch (e) { toast(`删除失败：${e.message}`, 'error', 5000); }
  });

  box.querySelector('#btn-set-default')?.addEventListener('click', async () => {
    if (!(await confirmDialog({
      title: '切换默认人设',
      message: `将默认人设切换为 <b>${escapeHtml(currentKey)}</b>？<br>新会话与重置后的会话将使用它，已有活跃会话不受影响。`,
      confirmText: '切换',
    }))) return;
    try {
      await api.post('/personas/default', { key: currentKey });
      toast(`默认人设已切换为 ${currentKey}`, 'success');
      reload(document.getElementById('view-personas'));
    } catch (e) { toast(`切换失败：${e.message}`, 'error', 5000); }
  });
}

function promptCreate() {
  openModal({
    title: '新建人设',
    bodyHtml: `<div class="field">
      <div class="field-label">人设名称</div>
      <input class="input" id="new-persona-key" placeholder="如 我的ATRI">
      <p class="field-desc">将创建 .txt 文件，可包含中文、字母、数字、空格与 -_.</p>
    </div>`,
    actions: [
      { label: '取消', class: 'ghost', onClick: ({ close }) => close() },
      {
        label: '创建并编辑',
        class: 'primary',
        onClick: async ({ close, el }) => {
          const key = el.querySelector('#new-persona-key').value.trim();
          if (!key) return;
          try {
            await api.post('/personas', { key, content: '' });
            close();
            currentKey = key;
            currentContent = '';
            toast('人设已创建', 'success');
            reload(document.getElementById('view-personas'));
          } catch (e) { toast(`创建失败：${e.message}`, 'error', 5000); }
        },
      },
    ],
  });
}

export const personasView = { title: '人设管理', init };
