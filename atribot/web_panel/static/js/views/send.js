/* 视图：发送消息（群聊 / 私聊，支持平台选择与 CQ 码） */

import { api } from '../api.js';
import { icon, toast, escapeHtml } from '../ui.js';

async function init(section) {
  section.innerHTML = `
    <div class="grid cols-2" style="align-items:start">
      <div class="card">
        <h3 class="card-title">发送主动消息</h3>
        <p class="card-sub">通过 OneBot API 主动发送，支持 CQ 码（如 [CQ:face,id=178]）</p>
        <div class="field">
          <div class="field-label">消息类型</div>
          <div class="seg" id="send-type">
            <button data-t="group" class="active">群聊</button>
            <button data-t="private">私聊</button>
          </div>
        </div>
        <div class="field" id="send-id-field">
          <div class="field-label" id="send-id-label">群号</div>
          <input class="input mono" id="send-target" placeholder="如 123456789">
        </div>
        <div class="field" id="send-platform-field">
          <div class="field-label">平台（多适配器时选择）</div>
          <select class="select" id="send-platform"><option value="">默认（第一个可用平台）</option></select>
        </div>
        <div class="field">
          <div class="field-label">消息内容</div>
          <textarea class="textarea mono" id="send-content" placeholder="要发送的文本内容，支持 CQ 码…"></textarea>
        </div>
        <button class="btn primary" id="btn-send">${icon('send')} 发送</button>
      </div>
      <div class="card">
        <h3 class="card-title">发送结果</h3>
        <p class="card-sub">API 原始返回内容</p>
        <pre class="mono" id="send-result" style="background:var(--bg-code);border-radius:12px;padding:16px;font-size:12.5px;line-height:1.6;white-space:pre-wrap;word-break:break-all;color:var(--text-3);min-height:200px;margin:0">尚无发送记录</pre>
      </div>
    </div>`;

  let sendType = 'group';

  section.querySelectorAll('#send-type button').forEach((btn) => {
    btn.addEventListener('click', () => {
      section.querySelectorAll('#send-type button').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      sendType = btn.dataset.t;
      section.querySelector('#send-id-label').textContent = sendType === 'group' ? '群号' : '用户 QQ 号';
      section.querySelector('#send-target').placeholder = sendType === 'group' ? '如 123456789' : '如 10001';
    });
  });

  /* 平台列表 */
  try {
    const res = await api.get('/platforms');
    const sel = section.querySelector('#send-platform');
    for (const p of res.items || []) {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = `${p.name}${p.is_connected ? '' : '（未连接）'}`;
      sel.appendChild(opt);
    }
    if ((res.items || []).length <= 1) section.querySelector('#send-platform-field').classList.add('hidden');
  } catch { /* 无平台时隐藏 */ section.querySelector('#send-platform-field').classList.add('hidden'); }

  section.querySelector('#btn-send').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    const target = section.querySelector('#send-target').value.trim();
    const content = section.querySelector('#send-content').value;
    const platform = section.querySelector('#send-platform').value || undefined;
    const resultBox = section.querySelector('#send-result');

    if (!/^\d+$/.test(target)) { toast('请输入有效的数字 ID', 'error'); return; }
    if (!content.trim()) { toast('消息内容不能为空', 'error'); return; }

    btn.classList.add('loading');
    resultBox.style.color = 'var(--text-3)';
    resultBox.textContent = '发送中…';

    try {
      const body = { message: content, platform };
      if (sendType === 'group') body.group_id = Number(target);
      else body.user_id = Number(target);
      const res = await api.post('/message/send', body);
      resultBox.style.color = res.status === 'ok' ? 'var(--green)' : 'var(--red)';
      resultBox.textContent = JSON.stringify(res, null, 2);
      if (res.status === 'ok') {
        toast('发送成功', 'success');
        section.querySelector('#send-content').value = '';
      } else {
        toast(`发送失败：${escapeHtml(String(res.result))}`, 'error', 5000);
      }
    } catch (err) {
      resultBox.style.color = 'var(--red)';
      resultBox.textContent = err.message;
      toast(`发送异常：${err.message}`, 'error', 5000);
    } finally {
      btn.classList.remove('loading');
    }
  });
}

export const sendView = { title: '发送消息', init };
