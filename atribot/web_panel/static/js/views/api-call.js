/* 视图：调用接口（选择适配器，调用任意端点 action + JSON 参数，查看原始返回） */

import { api } from '../api.js';
import { icon, toast, escapeHtml } from '../ui.js';
import { createJsonEditor } from '../components/json-editor.js';

/* 常用接口模板：点击填入接口名与参数骨架 */
const TEMPLATES = [
  { label: '登录信息', action: 'get_login_info', params: {} },
  { label: '群列表', action: 'get_group_list', params: {} },
  { label: '好友列表', action: 'get_friend_list', params: {} },
  { label: '群成员列表', action: 'get_group_member_list', params: { group_id: 123456789 } },
  { label: '发群消息', action: 'send_group_msg', params: { group_id: 123456789, message: 'Hello!' } },
  { label: '发私聊消息', action: 'send_private_msg', params: { user_id: 10001, message: 'Hello!' } },
  { label: '获取消息', action: 'get_msg', params: { message_id: 123456 } },
  { label: '撤回消息', action: 'delete_msg', params: { message_id: 123456 } },
  { label: '群禁言', action: 'set_group_ban', params: { group_id: 123456789, user_id: 10001, duration: 60 } },
];

async function init(section) {
  section.innerHTML = `
    <style>
      #call-params-editor .json-editor-inner { min-height: 240px; max-height: 46vh; }
      .call-tpl-row { display: flex; flex-wrap: wrap; gap: 8px; }
    </style>
    <div class="grid cols-2" style="align-items:start">
      <div class="card">
        <h3 class="card-title">调用接口</h3>
        <p class="card-sub">通过所选适配器调用任意端点，message 字段支持 CQ 码</p>
        <div class="field">
          <div class="field-label">适配器</div>
          <select class="select" id="call-platform"><option value="" disabled selected>加载平台列表…</option></select>
        </div>
        <div class="field">
          <div class="field-label">接口名（action）</div>
          <input class="input mono" id="call-action" placeholder="如 get_group_list" list="call-action-list">
          <datalist id="call-action-list">
            ${TEMPLATES.map((t) => `<option value="${escapeHtml(t.action)}"></option>`).join('')}
          </datalist>
        </div>
        <div class="field">
          <div class="field-label">常用模板</div>
          <div class="call-tpl-row">
            ${TEMPLATES.map((t, i) =>
              `<button class="btn sm ghost mono" data-tpl="${i}" title="${escapeHtml(t.label)}">${escapeHtml(t.action)}</button>`).join('')}
          </div>
        </div>
        <div class="field">
          <div class="field-label">参数（JSON）</div>
          <div id="call-params-editor"></div>
        </div>
        <button class="btn primary" id="btn-call">${icon('send')} 执行</button>
      </div>
      <div class="card">
        <h3 class="card-title">返回结果</h3>
        <div class="filter-bar" style="margin-bottom:10px">
          <span class="muted small" id="call-result-info">API 原始返回内容</span>
          <span class="spacer"></span>
          <button class="btn sm ghost hidden" id="btn-copy-result">${icon('copy')} 复制</button>
        </div>
        <pre class="mono" id="call-result" style="background:var(--bg-code);border-radius:12px;padding:16px;font-size:12.5px;line-height:1.6;white-space:pre-wrap;word-break:break-all;color:var(--text-3);min-height:200px;margin:0">尚无调用记录</pre>
      </div>
    </div>`;

  const platformSel = section.querySelector('#call-platform');
  const actionInput = section.querySelector('#call-action');
  const resultBox = section.querySelector('#call-result');
  const resultInfo = section.querySelector('#call-result-info');
  const copyBtn = section.querySelector('#btn-copy-result');
  const runBtn = section.querySelector('#btn-call');
  const editor = createJsonEditor(section.querySelector('#call-params-editor'), { content: '{}' });

  /* 平台列表（适配器必选，始终显示） */
  let hasPlatform = false;
  try {
    const res = await api.get('/platforms');
    const items = res.items || [];
    platformSel.querySelector('option[disabled]')?.remove();
    for (const p of items) {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = `${p.name}（${p.type}）${p.is_connected ? '' : ' · 未连接'}`;
      platformSel.appendChild(opt);
    }
    if (items.length) {
      const preferred = items.find((p) => p.is_connected) || items[0];
      platformSel.value = preferred.name;
      hasPlatform = true;
    } else {
      platformSel.innerHTML = '<option value="" disabled selected>没有可用适配器</option>';
    }
  } catch (e) {
    platformSel.innerHTML = '<option value="" disabled selected>平台列表加载失败</option>';
    resultInfo.textContent = `平台列表加载失败：${e.message}`;
  }
  if (!hasPlatform) runBtn.disabled = true;

  /* 模板与回车执行 */
  section.querySelectorAll('[data-tpl]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const t = TEMPLATES[Number(btn.dataset.tpl)];
      actionInput.value = t.action;
      editor.setContent(JSON.stringify(t.params, null, 2));
    });
  });
  actionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') runBtn.click();
  });

  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(resultBox.textContent);
      toast('已复制到剪贴板', 'success');
    } catch {
      toast('复制失败：剪贴板不可用', 'error');
    }
  });

  function showResult(ok, info, text) {
    resultInfo.textContent = info;
    resultInfo.style.color = ok ? 'var(--green)' : 'var(--red)';
    resultBox.style.color = ok ? 'var(--green)' : 'var(--red)';
    resultBox.textContent = text;
    copyBtn.classList.toggle('hidden', !text || text === '尚无调用记录');
  }

  runBtn.addEventListener('click', async () => {
    const platform = platformSel.value;
    const action = actionInput.value.trim();
    if (!platform) { toast('请选择适配器', 'error'); return; }
    if (!action) { toast('请输入接口名（action）', 'error'); return; }

    const src = editor.getContent().trim();
    let params = {};
    if (src) {
      if (!editor.isValid()) { toast('参数不是合法的 JSON', 'error'); return; }
      params = JSON.parse(src);
      if (typeof params !== 'object' || params === null || Array.isArray(params)) {
        toast('参数必须是 JSON 对象', 'error');
        return;
      }
    }

    runBtn.classList.add('loading');
    resultInfo.style.color = '';
    resultInfo.textContent = `${platform} · ${action} · 调用中…（最长 30 秒）`;
    resultBox.style.color = 'var(--text-3)';
    resultBox.textContent = '…';
    copyBtn.classList.add('hidden');

    try {
      const res = await api.post('/message/call', { platform, action, params });
      const ok = res.status === 'ok';
      const ms = res.duration_ms !== undefined ? ` · ${res.duration_ms} ms` : '';
      showResult(ok, `${ok ? '✓' : '✗'} ${platform} · ${action}${ms}`, JSON.stringify(res, null, 2));
      if (ok) toast('调用完成', 'success');
      else toast(`调用失败：${escapeHtml(String(res.result))}`, 'error', 5000);
    } catch (err) {
      showResult(false, `✗ ${platform} · ${action}`, err.message);
      toast(`请求异常：${err.message}`, 'error', 5000);
    } finally {
      runBtn.classList.remove('loading');
    }
  });
}

export const apiCallView = { title: '调用接口', init };
