/* API 请求封装：会话令牌管理、统一错误处理、全局加载进度条 */

import { loadbarBegin, loadbarEnd } from './ui.js';

const API_BASE = '/admin/api';
const TOKEN_KEY = 'atri_admin_token';
const EXPIRES_KEY = 'atri_admin_expires';

let _unauthorizedHandler = null;

export function onUnauthorized(fn) {
  _unauthorizedHandler = fn;
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRES_KEY);
  }
}

/** 登录成功后保存会话令牌与到期时间（用于到点自动退出登录） */
export function setSession(sessionToken, expiresInSeconds) {
  localStorage.setItem(TOKEN_KEY, sessionToken);
  const expiresIn = Number(expiresInSeconds) || 0;
  if (expiresIn > 0) localStorage.setItem(EXPIRES_KEY, String(Date.now() + expiresIn * 1000));
  else localStorage.removeItem(EXPIRES_KEY);
}

/** 会话剩余毫秒数；无到期记录时返回 null（交给 401 兜底） */
export function getSessionRemainingMs() {
  const expiresAt = Number(localStorage.getItem(EXPIRES_KEY));
  if (!expiresAt) return null;
  return expiresAt - Date.now();
}

async function request(method, path, body, { auth = true, handle401 = true } = {}) {
  loadbarBegin();
  try {
    const options = { method, headers: {} };
    if (auth) options.headers.Authorization = `Bearer ${getToken()}`;
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }

    let res;
    try {
      res = await fetch(API_BASE + path, options);
    } catch {
      throw new Error('无法连接到面板服务，请确认 bot 正在运行');
    }

    if (res.status === 401 && handle401) {
      if (_unauthorizedHandler) _unauthorizedHandler();
      const err = new Error('会话已失效，请重新登录');
      err.status = 401;
      throw err;
    }

    let data = null;
    try {
      data = await res.json();
    } catch {
      /* 空 body */
    }

    if (!res.ok) {
      const detail = data && data.detail ? data.detail : `请求失败 (HTTP ${res.status})`;
      const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      err.status = res.status;
      if (res.status === 429) err.retryAfter = Number(res.headers.get('Retry-After')) || 0;
      throw err;
    }
    return data;
  } finally {
    loadbarEnd();
  }
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  del: (path) => request('DELETE', path),

  /** 登录：用面板访问令牌换取短期会话令牌；失败异常带 status（401/429/503）与 retryAfter */
  login: (token) => request('POST', '/login', { token }, { auth: false, handle401: false }),

  /** 登出：吊销服务端当前会话（尽力而为；本地令牌由调用方清理） */
  async logout() {
    try {
      await request('POST', '/logout');
    } catch {
      /* 会话可能已失效，忽略即可 */
    }
  },
};

/** WebSocket 地址（path 形如 /ws/logs）：现取一张一次性票据拼 URL，避免会话令牌出现在 WS URL 里 */
export async function wsUrl(path) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const res = await fetch(`${API_BASE}/ws_ticket`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error('无法获取 WebSocket 票据，请重新登录');
  const { ticket } = await res.json();
  return `${proto}://${location.host}${API_BASE}${path}?ticket=${encodeURIComponent(ticket)}`;
}
