/* API 请求封装：token 管理、统一错误处理、全局加载进度条 */

import { loadbarBegin, loadbarEnd } from './ui.js';

const API_BASE = '/admin/api';
const TOKEN_KEY = 'atri_admin_token';

let _unauthorizedHandler = null;

export function onUnauthorized(fn) {
  _unauthorizedHandler = fn;
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request(method, path, body) {
  loadbarBegin();
  try {
    const options = {
      method,
      headers: { Authorization: `Bearer ${getToken()}` },
    };
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

    if (res.status === 401) {
      if (_unauthorizedHandler) _unauthorizedHandler();
      throw new Error('登录令牌无效');
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
};

/** WebSocket 日志地址 */
export function logsWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}${API_BASE}/ws/logs?token=${encodeURIComponent(getToken())}`;
}
