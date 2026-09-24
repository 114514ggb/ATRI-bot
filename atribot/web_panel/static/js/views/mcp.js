/* 视图：MCP 配置（mcp_server.json 源码编辑） */

import { api } from '../api.js';
import { icon, toast, confirmDialog } from '../ui.js';
import { createJsonEditor } from '../components/json-editor.js';
import * as kit from '../components/editor-kit.js';

let original = null;
let editor = null;
let saveBar = null;

async function init(section) {
  section.innerHTML = `<div class="card">${'<div class="skeleton skeleton-card"></div>'.repeat(2)}</div>`;
  const res = await api.get('/mcp_config');
  original = res.valid ? JSON.parse(res.content) : {};

  section.innerHTML = `
    <div class="notice info">${icon('info')}<div>MCP 工具服务器配置（本地进程或远程服务条目），修改后需重启 bot 生效。</div></div>
    <div id="mcp-savebar"></div>
    <div id="mcp-editor"></div>`;

  editor = createJsonEditor(section.querySelector('#mcp-editor'), {
    content: res.content,
    onChange: () => {
      try { saveBar.setDirty(kit.diffObjects(original, JSON.parse(editor.getContent())).length > 0); }
      catch { saveBar.setDirty(true); }
    },
  });

  saveBar = kit.renderSaveBar(section.querySelector('#mcp-savebar'), {
    pathLabel: res.path,
    onModeChange: () => toast('MCP 配置为源码编辑模式', 'info'),
    onSave: save,
    onDownload: () => kit.downloadText('mcp_server.json', editor.getContent()),
    onRollback: async () => {
      const ok = await confirmDialog({ title: '回滚 MCP 配置', message: '将把备份（.bak）写回 MCP 配置文件。', danger: true, confirmText: '回滚' });
      if (!ok) return;
      try {
        await api.post('/config/rollback', { target: 'mcp' });
        toast('已回滚', 'success');
        original = null;
        await init(section);
      } catch (e) { toast(`回滚失败：${e.message}`, 'error', 5000); }
    },
  });
  saveBar.setMode('source');
  /* 隐藏表单模式按钮（MCP 只有源码模式） */
  section.querySelectorAll('[data-mode]').forEach((b) => b.remove());
}

async function save() {
  if (!editor.isValid()) { toast('JSON 语法错误，请先修正', 'error'); return; }
  const payload = JSON.parse(editor.getContent());
  const diffs = kit.diffObjects(original, payload);
  if (!diffs.length) { toast('当前没有需要保存的更改', 'info'); return; }
  if (!(await kit.showDiffModal(diffs))) return;

  try {
    await api.post('/mcp_config', { content: JSON.stringify(payload, null, 2) });
    original = kit.deepClone(payload);
    saveBar.setDirty(false);
    toast('MCP 配置已保存', 'success');
    await kit.needsRestartFlow('MCP 配置');
  } catch (e) { toast(`保存失败：${e.message}`, 'error', 5000); }
}

export const mcpView = { title: 'MCP 配置', init };
