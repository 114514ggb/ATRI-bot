const API_BASE = '/admin/api';
let _token = localStorage.getItem('atri_admin_token') || '';

// Initialize
if (_token) {
    document.getElementById('access-token').value = _token;
    checkAuth();
}

// Authentication
document.getElementById('login-btn').addEventListener('click', () => {
    const token = document.getElementById('access-token').value;
    if (!token) return;
    _token = token;
    localStorage.setItem('atri_admin_token', _token);
    checkAuth();
});

document.getElementById('btn-logout').addEventListener('click', () => {
    _token = '';
    localStorage.removeItem('atri_admin_token');
    document.getElementById('login-overlay').classList.add('active');
    document.getElementById('app').style.display = 'none';
});

function checkAuth() {
    fetchWithAuth('/status')
        .then(data => {
            if (data.detail === "Unauthorized") throw new Error('Unauthorized');
            document.getElementById('login-overlay').classList.remove('active');
            document.getElementById('app').style.display = 'flex';
            document.getElementById('login-error').style.display = 'none';
            initApp();
        })
        .catch(err => {
            document.getElementById('login-error').style.display = 'block';
            _token = '';
            localStorage.removeItem('atri_admin_token');
        });
}

// App Initialization
function initApp() {
    setupNavigation();
    loadDashboard();
}

async function fetchWithAuth(endpoint, options = {}) {
    const url = API_BASE + endpoint;
    const headers = { 
        'Authorization': `Bearer ${_token}`,
        'Content-Type': 'application/json'
    };
    
    const config = { ...options, headers: { ...headers, ...options.headers } };
    const res = await fetch(url, config);
    if (res.status === 401) {
        document.getElementById('login-overlay').classList.add('active');
        document.getElementById('app').style.display = 'none';
        throw new Error('Unauthorized');
    }
    return await res.json();
}

// Navigation functionality
function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            // Remove active classes
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            
            // Add active class to clicked item and target view
            const targetViewId = e.target.dataset.view;
            e.target.classList.add('active');
            document.getElementById(`view-${targetViewId}`).classList.add('active');
            document.getElementById('view-title').innerText = e.target.innerText;
            
            // Load view specific data
            loadViewData(targetViewId);
        });
    });
}

function loadViewData(view) {
    switch(view) {
        case 'dashboard': loadDashboard(); break;
        case 'groups': loadGroups(1); break;
        case 'users': loadUsers(1); break;
        case 'messages': loadMessages(1); break;
        case 'memory': loadMemory(1); break;
        case 'commands': loadCommands(); break;
        case 'config': loadConfig(); break;
        case 'supplier': loadSupplier(); break;
        // send-msg requires no dynamic load immediately
    }
}

// View: Dashboard
async function loadDashboard() {
    try {
        const stats = await fetchWithAuth('/stats');
        const status = await fetchWithAuth('/status');
        
        // Update stats
        const statsHtml = `
            <div class="stat-card">
                <div class="stat-value">${stats.groups}</div>
                <div class="stat-label">群组总计</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.users}</div>
                <div class="stat-label">用户总计</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.messages}</div>
                <div class="stat-label">消息数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.memories}</div>
                <div class="stat-label">记忆条数</div>
            </div>
        `;
        document.getElementById('dashboard-stats').innerHTML = statsHtml;
        
        // Update status
        let statusHtml = '<table class="apple-table" style="background:transparent">';
        for (const [key, val] of Object.entries(status)) {
            let displayVal = val;
            if (typeof val === 'boolean') {
                displayVal = val ? '🟢 已启用 / 运行中' : '🔴 未启用 / 已结束';
            }
            statusHtml += `<tr><td style="width: 250px; font-weight:600; text-transform: capitalize">${key.replace(/_/g, ' ')}</td><td>${displayVal}</td></tr>`;
        }
        statusHtml += '</table>';
        document.getElementById('dashboard-status').innerHTML = statusHtml;
    } catch (e) {
        console.error("Dashboard load failed", e);
    }
}

// Common pagination renderer
function renderPagination(containerId, current, totalItems, limit, callbackName) {
    const totalPages = Math.ceil(totalItems / limit) || 1;
    let html = '';
    
    html += `<button class="pagination-btn" onclick="${callbackName}(${current - 1})" ${current <= 1 ? 'disabled' : ''}>上一页</button>`;
    html += `<span style="padding: 6px 12px; font-size: 14px;">第 ${current} 页，共 ${totalPages} 页</span>`;
    html += `<button class="pagination-btn" onclick="${callbackName}(${current + 1})" ${current >= totalPages ? 'disabled' : ''}>下一页</button>`;
    
    document.getElementById(containerId).innerHTML = html;
}

// View: Groups
window.loadGroups = async function(page = 1) {
    const data = await fetchWithAuth(`/groups?page=${page}&limit=20`);
    const tbody = document.getElementById('groups-table-body');
    tbody.innerHTML = data.items.map(i => `
        <tr>
            <td>${i.group_id}</td>
            <td>${escapeHtml(i.group_name)}</td>
        </tr>
    `).join('');
    renderPagination('groups-pagination', data.page, data.total, data.limit, 'loadGroups');
}

// View: Users
window.loadUsers = async function(page = 1) {
    const data = await fetchWithAuth(`/users?page=${page}&limit=20`);
    const tbody = document.getElementById('users-table-body');
    tbody.innerHTML = data.items.map(i => `
        <tr>
            <td>${i.user_id}</td>
            <td>${escapeHtml(i.nickname) || '-'}</td>
            <td>${i.permission_type || '-'}</td>
            <td>${i.last_updated || '-'}</td>
        </tr>
    `).join('');
    renderPagination('users-pagination', data.page, data.total, data.limit, 'loadUsers');
}

// View: Messages
window.loadMessages = async function(page = 1) {
    const groupInput = document.getElementById('filter-msg-group').value;
    const userInput = document.getElementById('filter-msg-user').value;
    
    let url = `/messages?page=${page}&limit=50`;
    if (groupInput) url += `&group_id=${groupInput}`;
    if (userInput) url += `&user_id=${userInput}`;
    
    const data = await fetchWithAuth(url);
    const tbody = document.getElementById('messages-table-body');
    tbody.innerHTML = data.items.map(i => `
        <tr>
            <td style="white-space:nowrap; color: var(--text-caption);">${i.time_str || '-'}</td>
            <td>${i.group_id || '私聊'}</td>
            <td>${escapeHtml(i.nickname) || i.user_id} <br><small style="color:var(--text-caption)">${i.user_id}</small></td>
            <td style="max-width: 400px; white-space: pre-wrap; overflow-wrap: anywhere;">${escapeHtml(i.message_content)}</td>
        </tr>
    `).join('');
    renderPagination('messages-pagination', data.page, data.total, data.limit, 'loadMessages');
}

document.getElementById('btn-filter-msg').addEventListener('click', () => loadMessages(1));

// View: Memory
window.loadMemory = async function(page = 1) {
    const catInput = document.getElementById('filter-mem-cat').value;
    const userInput = document.getElementById('filter-mem-user').value;
    
    let url = `/memory?page=${page}&limit=20`;
    if (catInput) url += `&category=${encodeURIComponent(catInput)}`;
    if (userInput) url += `&user_id=${encodeURIComponent(userInput)}`;
    
    const data = await fetchWithAuth(url);
    const tbody = document.getElementById('memory-table-body');
    tbody.innerHTML = data.items.map(i => `
        <tr>
            <td style="white-space:nowrap; color: var(--text-caption);">${i.event_time_str || '-'}</td>
            <td><span class="badge" style="background:var(--bg-main); border:1px solid var(--border-color); color:var(--text-primary); padding:4px 8px; border-radius:6px; font-size:12px;">${escapeHtml(i.category)}</span></td>
            <td>${i.user_id || '系统'}</td>
            <td style="max-width: 400px; line-height: 1.4;">${escapeHtml(i.event)}</td>
            <td style="color: var(--text-caption); font-family: monospace;">${i.importance}</td>
            <td style="color: var(--text-caption); font-family: monospace;">${i.credibility}</td>
        </tr>
    `).join('');
    renderPagination('memory-pagination', data.page, data.total, data.limit, 'loadMemory');
}

document.getElementById('btn-filter-mem').addEventListener('click', () => loadMemory(1));

// View: Commands
async function loadCommands() {
    const data = await fetchWithAuth('/commands');
    const container = document.getElementById('commands-list');
    
    container.innerHTML = data.map(cmd => `
        <div class="grid-item">
            <h4>${cmd.name} <span class="badge" style="float:right">Lv ${cmd.authority_level}</span></h4>
            <p>${escapeHtml(cmd.description)}</p>
            <p style="font-family:monospace; background: var(--input-bg); padding: 6px; border-radius: 6px; font-size: 13px; word-break: break-all;">${escapeHtml(cmd.usage)}</p>
            ${cmd.aliases.length > 0 ? `<p class="mt-2" style="font-size: 12px"><strong>别名:</strong> ${cmd.aliases.map(a => `<span style="background:var(--bg-main); padding: 2px 6px; border-radius:4px; margin-right:4px;">${escapeHtml(a)}</span>`).join('')}</p>` : ''}
        </div>
    `).join('');
}

// View: Config
async function loadConfig() {
    const data = await fetchWithAuth('/config');
    document.getElementById('config-path').innerText = data.path;
    document.getElementById('config-editor').value = data.content;
}

document.getElementById('btn-save-config').addEventListener('click', async () => {
    const btn = document.getElementById('btn-save-config');
    const originalText = btn.innerText;
    btn.innerText = '保存中...';
    btn.disabled = true;
    
    const content = document.getElementById('config-editor').value;
    try {
        const res = await fetchWithAuth('/config', {
            method: 'POST',
            body: JSON.stringify({ content })
        });
        if (res.status === 'ok') {
            alert('主配置 JSON 保存成功！');
            loadConfig();
        }
    } catch(e) {
        alert('保存主配置失败');
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
});

// View: Supplier Config
async function loadSupplier() {
    const data = await fetchWithAuth('/supplier_config');
    document.getElementById('supplier-path').innerText = data.path;
    document.getElementById('supplier-editor').value = data.content;
}

document.getElementById('btn-save-supplier').addEventListener('click', async () => {
    const btn = document.getElementById('btn-save-supplier');
    const originalText = btn.innerText;
    btn.innerText = '保存中...';
    btn.disabled = true;

    const content = document.getElementById('supplier-editor').value;
    try {
        const res = await fetchWithAuth('/supplier_config', {
            method: 'POST',
            body: JSON.stringify({ content })
        });
        if (res.status === 'ok') {
            alert('系统供应商配置文件已保存成功！');
            loadSupplier();
        }
    } catch(e) {
        alert('模型系统供应商配置文件未能保存');
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
});

// View: Send Message
document.getElementById('btn-send-msg').addEventListener('click', async () => {
    const group_id = parseInt(document.getElementById('send-group-id').value);
    const message = document.getElementById('send-msg-content').value;
    const btn = document.getElementById('btn-send-msg');
    
    if (!group_id || !message) {
        alert('请务必输入群组 ID 以及想要发送的消息内容');
        return;
    }
    
    const originalText = btn.innerText;
    btn.innerText = '正在发送信件...';
    btn.disabled = true;
    
    try {
        const res = await fetchWithAuth('/message/send', {
            method: 'POST',
            body: JSON.stringify({ group_id, message })
        });
        const resultLabel = document.getElementById('send-msg-result');
        if(res.status === 'ok') {
            resultLabel.style.color = '#34c759';
            resultLabel.innerText = `发送成功结果: ${JSON.stringify(res.result)}`;
            document.getElementById('send-msg-content').value = '';
        } else {
            resultLabel.style.color = '#ff3b30';
            resultLabel.innerText = `执行发信请求出现失败: ${JSON.stringify(res)}`;
        }
    } catch(e) {
        const resultLabel = document.getElementById('send-msg-result');
        resultLabel.style.color = '#ff3b30';
        resultLabel.innerText = `系统出现异常或中断: ${e.message}`;
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
});

// Utils
function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe.toString()
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}
