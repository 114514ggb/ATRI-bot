/* 视图：记忆管理（筛选 / 编辑 / 删除 / 批量删除） */

import { api } from '../api.js';
import { icon, toast, escapeHtml, renderPagination, skeletonRows, confirmDialog, openModal, debounce } from '../ui.js';

const CATEGORIES = ['preference', 'fact', 'experience', 'emotion', 'group_topic', 'knowledge', 'domain', 'guideline'];
const CAT_LABEL = {
  preference: '偏好', fact: '事实', experience: '经历', emotion: '情感',
  group_topic: '群话题', knowledge: '知识', domain: '领域', guideline: '准则',
};

const state = { page: 1, limit: 20, category: '', user: '', search: '' };

async function init(section) {
  section.innerHTML = `
    <div class="filter-bar">
      <select class="select" id="mem-cat">
        <option value="">全部类别</option>
        ${CATEGORIES.map((c) => `<option value="${c}" ${state.category === c ? 'selected' : ''}>${CAT_LABEL[c]} (${c})</option>`).join('')}
      </select>
      <input class="input mono" id="mem-user" placeholder="用户 QQ 筛选" value="${escapeHtml(state.user)}" style="width:150px">
      <input class="input" id="mem-search" placeholder="搜索记忆内容…" value="${escapeHtml(state.search)}" style="width:200px">
      <button class="btn primary sm" id="mem-apply">${icon('search')} 筛选</button>
      <span class="spacer"></span>
      <button class="btn danger sm hidden" id="mem-batch-del">${icon('trash')} 删除选中 (<span id="mem-sel-count">0</span>)</button>
    </div>
    <div id="mem-table"></div>`;

  const apply = () => {
    state.category = section.querySelector('#mem-cat').value;
    state.user = section.querySelector('#mem-user').value.trim();
    state.search = section.querySelector('#mem-search').value.trim();
    state.page = 1;
    load(section);
  };
  section.querySelector('#mem-apply').addEventListener('click', apply);
  section.querySelector('#mem-user').addEventListener('keydown', (e) => { if (e.key === 'Enter') apply(); });
  section.querySelector('#mem-search').addEventListener('input', debounce(apply, 400));
  section.querySelector('#mem-cat').addEventListener('change', apply);

  section.querySelector('#mem-batch-del').addEventListener('click', () => batchDelete(section));

  section.addEventListener('change', (e) => {
    if (e.target.matches('#mem-table input[type="checkbox"]')) updateSelCount(section);
  });

  section.addEventListener('click', async (e) => {
    const editBtn = e.target.closest('[data-edit-mem]');
    if (editBtn) { openEditModal(Number(editBtn.dataset.editMem), section); return; }

    const delBtn = e.target.closest('[data-del-mem]');
    if (delBtn) {
      const id = Number(delBtn.dataset.delMem);
      if (await confirmDialog({ title: '删除记忆', message: `确定删除记忆 <b>#${id}</b> 吗？此操作不可撤销。`, danger: true, confirmText: '删除' })) {
        try {
          await api.del(`/memory/${id}`);
          toast('已删除', 'success');
          load(section);
        } catch (err) { toast(`删除失败：${err.message}`, 'error', 5000); }
      }
    }
  });

  await load(section);
}

async function load(section) {
  const box = section.querySelector('#mem-table');
  box.innerHTML = `<div class="table-wrap"><div style="padding:6px 16px">${skeletonRows(6)}</div></div>`;

  const params = new URLSearchParams({ page: state.page, limit: state.limit });
  if (state.category) params.set('category', state.category);
  if (state.user) params.set('user_id', state.user);
  if (state.search) params.set('search', state.search);
  const data = await api.get(`/memory?${params}`);

  const rows = data.items.length
    ? data.items
        .map(
          (m) => `<tr data-mid="${m.memory_id}">
            <td><label class="check-row"><input type="checkbox" data-sel="${m.memory_id}"></label></td>
            <td class="muted" style="white-space:nowrap">${escapeHtml(m.event_time_str || '-')}</td>
            <td><span class="badge teal">${CAT_LABEL[m.category] || escapeHtml(m.category)}</span></td>
            <td class="mono">${escapeHtml(String(m.user_id || '系统'))}</td>
            <td class="msg-cell">${escapeHtml(m.event)}</td>
            <td class="mono muted">${m.importance}</td>
            <td class="mono muted">${m.credibility}</td>
            <td><div class="row-actions">
              <button class="icon-btn" data-edit-mem="${m.memory_id}" title="编辑">${icon('edit')}</button>
              <button class="icon-btn del" data-del-mem="${m.memory_id}" title="删除">${icon('trash')}</button>
            </div></td>
          </tr>`
        )
        .join('')
    : `<tr class="empty-row"><td colspan="8">没有匹配的记忆</td></tr>`;

  box.innerHTML = `<div class="table-wrap"><div class="table-scroll">
    <table class="tbl">
      <thead><tr>
        <th style="width:36px"></th><th>时间</th><th>类别</th><th>用户</th>
        <th>记忆内容</th><th>重要度</th><th>可信度</th><th style="width:90px">操作</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div><div class="pagination"></div></div>`;

  renderPagination(box.querySelector('.pagination'), data, (page, limit) => {
    state.page = page;
    state.limit = limit;
    load(section);
  });
  updateSelCount(section);
}

function selectedIds(section) {
  return Array.from(section.querySelectorAll('#mem-table input[data-sel]:checked')).map((c) => Number(c.dataset.sel));
}

function updateSelCount(section) {
  const ids = selectedIds(section);
  const btn = section.querySelector('#mem-batch-del');
  btn.classList.toggle('hidden', ids.length === 0);
  section.querySelector('#mem-sel-count').textContent = ids.length;
}

async function batchDelete(section) {
  const ids = selectedIds(section);
  if (!ids.length) return;
  if (!(await confirmDialog({ title: '批量删除', message: `确定删除选中的 <b>${ids.length}</b> 条记忆吗？此操作不可撤销。`, danger: true, confirmText: `删除 ${ids.length} 条` }))) return;
  try {
    const res = await api.post('/memory/batch_delete', { ids });
    toast(`已删除 ${res.deleted} 条记忆`, 'success');
    load(section);
  } catch (e) { toast(`批量删除失败：${e.message}`, 'error', 5000); }
}

async function openEditModal(id, section) {
  /* 从已渲染表格行中找到当前数据 */
  const row = section.querySelector(`tr[data-mid="${id}"]`);
  if (!row) return;
  const cells = row.querySelectorAll('td');
  const event = cells[4].textContent;
  const importance = cells[5].textContent;
  const credibility = cells[6].textContent;
  const category = row.querySelector('.badge').textContent;

  const catKey = Object.keys(CAT_LABEL).find((k) => CAT_LABEL[k] === category) || 'fact';

  openModal({
    title: `编辑记忆 #${id}`,
    wide: true,
    bodyHtml: `
      <div class="field">
        <div class="field-label">记忆内容</div>
        <textarea class="textarea" id="mem-edit-event">${escapeHtml(event)}</textarea>
      </div>
      <div class="field-grid">
        <div class="field">
          <div class="field-label">类别</div>
          <select class="select" id="mem-edit-cat">
            ${CATEGORIES.map((c) => `<option value="${c}" ${c === catKey ? 'selected' : ''}>${CAT_LABEL[c]} (${c})</option>`).join('')}
          </select>
        </div>
        <div class="field">
          <div class="field-label">重要度（1-10）</div>
          <input class="input" type="number" min="1" max="10" id="mem-edit-imp" value="${escapeHtml(importance)}">
        </div>
        <div class="field">
          <div class="field-label">可信度（1-10）</div>
          <input class="input" type="number" min="1" max="10" id="mem-edit-cred" value="${escapeHtml(credibility)}">
        </div>
      </div>
      <div class="notice warn">${icon('alert')}<div>修改内容不会重新生成语义向量，可能影响该条记忆的检索精度。</div></div>`,
    actions: [
      { label: '取消', class: 'ghost', onClick: ({ close }) => close() },
      {
        label: '保存修改',
        class: 'primary',
        onClick: async ({ close, el, btn }) => {
          btn.classList.add('loading');
          try {
            await api.put(`/memory/${id}`, {
              event: el.querySelector('#mem-edit-event').value.trim(),
              category: el.querySelector('#mem-edit-cat').value,
              importance: Number(el.querySelector('#mem-edit-imp').value),
              credibility: Number(el.querySelector('#mem-edit-cred').value),
            });
            close();
            toast('记忆已更新', 'success');
            load(section);
          } catch (e) {
            btn.classList.remove('loading');
            toast(`更新失败：${e.message}`, 'error', 5000);
          }
        },
      },
    ],
  });
}

export const memoryView = { title: '记忆管理', init };
