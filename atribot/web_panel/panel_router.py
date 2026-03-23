"""ATRI Web 管理面板"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from atribot.core.command.command_parsing import CommandSystem
from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container

router = APIRouter(prefix="/admin", tags=["admin"])
_security = HTTPBearer(auto_error=False)
_start_time = time.time()
db:AsyncPostgreSQL = container.get("database")

def _access_token() -> str:
    return container.get("config").network.access_token


async def _auth(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> None:
    if creds is None or creds.credentials != _access_token():
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/", response_class=HTMLResponse)
async def panel_index() -> HTMLResponse:
    return HTMLResponse(_HTML)


@router.get("/api/status")
async def api_status(_: None = Depends(_auth)) -> Dict[str, Any]:
    cfg = container.get("config")
    uptime = int(time.time() - _start_time)
    h, r = divmod(uptime, 3600)
    m, s = divmod(r, 60)
    return {
        "account_id": cfg.account.id,
        "account_name": cfg.account.name,
        "model": cfg.model.connect.model_name,
        "supplier": cfg.model.connect.supplier,
        "connection_type": cfg.network.connection_type,
        "uptime": f"{h:02d}:{m:02d}:{s:02d}",
        "sandbox": container.exists("SandBox"),
        "mcp": container.exists("MCP"),
        "rag": cfg.model.RAG.enable,
    }


@router.get("/api/stats")
async def api_stats(_: None = Depends(_auth)) -> Dict[str, int]:
    g   = (await db.execute_SQL("SELECT COUNT(*) AS c FROM user_group"))[0]["c"]
    u   = (await db.execute_SQL("SELECT COUNT(*) AS c FROM users"))[0]["c"]
    m   = (await db.execute_SQL("SELECT COUNT(*) AS c FROM message"))[0]["c"]
    mem = (await db.execute_SQL("SELECT COUNT(*) AS c FROM atri_memory"))[0]["c"]
    return {"groups": g, "users": u, "messages": m, "memories": mem}


@router.get("/api/groups")
async def api_groups(
    page: int = 1,
    limit: int = 20,
    all: bool = False,
    _: None = Depends(_auth)
) -> Dict[str, Any]:
    if all:
        rows = await db.execute_SQL("SELECT group_id, group_name FROM user_group ORDER BY group_id")
        return {"items": [dict(r) for r in rows], "total": len(rows), "page": 1, "limit": len(rows)}

    offset = (page - 1) * limit
    rows = await db.execute_SQL(
        "SELECT group_id, group_name FROM user_group ORDER BY group_id LIMIT $1 OFFSET $2",
        (limit, offset)
    )
    total_rows = await db.execute_SQL("SELECT COUNT(*) AS c FROM user_group")
    total = total_rows[0]["c"] if total_rows else 0
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [dict(r) for r in rows],
    }


@router.get("/api/users")
async def api_users(
    page: int = 1,
    limit: int = 20,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    offset = (page - 1) * limit
    rows = await db.execute_SQL(
        """
        SELECT u.user_id, u.nickname,
               to_char(u.last_updated, 'YYYY-MM-DD HH24:MI:SS') AS last_updated,
               p.permission_type
        FROM users u
        LEFT JOIN permissions p ON u.user_id = p.user_id
        ORDER BY u.last_updated DESC NULLS LAST
        LIMIT $1 OFFSET $2
        """,
        (limit, offset),
    )
    total_rows = await db.execute_SQL("SELECT COUNT(*) AS c FROM users")
    total = total_rows[0]["c"] if total_rows else 0
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [dict(r) for r in rows],
    }


@router.get("/api/messages")
async def api_messages(
    page: int = 1,
    limit: int = 50,
    group_id: Optional[int] = None,
    user_id: Optional[int] = None,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    offset = (page - 1) * limit

    conds: List[str] = []
    vals: List[Any] = []
    i = 1
    if group_id is not None:
        conds.append(f"m.group_id = ${i}")
        vals.append(group_id)
        i += 1
    if user_id is not None:
        conds.append(f"m.user_id = ${i}")
        vals.append(user_id)
        i += 1

    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    rows = await db.execute_SQL(
        f"""
        SELECT m.sole_id, m.message_id, m.user_id, m.group_id,
               m.time, m.message_content, u.nickname
        FROM message m
        LEFT JOIN users u ON m.user_id = u.user_id
        {where}
        ORDER BY m.sole_id DESC
        LIMIT ${i} OFFSET ${i + 1}
        """,
        (*vals, limit, offset),
    )
    total_rows = await db.execute_SQL(
        f"SELECT COUNT(*) AS c FROM message m {where}",
        tuple(vals) if vals else None,
    )
    total = total_rows[0]["c"] if total_rows else 0

    items: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if d.get("time"):
            d["time_str"] = datetime.fromtimestamp(d["time"]).strftime("%Y-%m-%d %H:%M:%S")
        items.append(d)

    return {"total": total, "page": page, "limit": limit, "items": items}


@router.get("/api/memory")
async def api_memory(
    page: int = 1,
    limit: int = 20,
    category: Optional[str] = None,
    user_id: Optional[int] = None,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    offset = (page - 1) * limit

    conds: List[str] = []
    vals: List[Any] = []
    i = 1
    if category:
        conds.append(f"category = ${i}::memory_category")
        vals.append(category)
        i += 1
    if user_id is not None:
        conds.append(f"user_id = ${i}")
        vals.append(user_id)
        i += 1

    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    rows = await db.execute_SQL(
        f"""
        SELECT memory_id, user_id, group_id, event_time, event,
               category, importance, credibility, access_count
        FROM atri_memory
        {where}
        ORDER BY memory_id DESC
        LIMIT ${i} OFFSET ${i + 1}
        """,
        (*vals, limit, offset),
    )
    total_rows = await db.execute_SQL(
        f"SELECT COUNT(*) AS c FROM atri_memory {where}",
        tuple(vals) if vals else None,
    )
    total = total_rows[0]["c"] if total_rows else 0

    items: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if d.get("event_time"):
            d["event_time_str"] = datetime.fromtimestamp(d["event_time"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        d["category"] = str(d["category"]) if d.get("category") else ""
        items.append(d)

    return {"total": total, "page": page, "limit": limit, "items": items}


@router.get("/api/commands")
async def api_commands(_: None = Depends(_auth)) -> List[Dict[str, Any]]:
    cmd:CommandSystem = container.get("CommandSystem")
    result: List[Dict[str, Any]] = []
    for name, c in cmd.command_registry.items():
        params = [
            {
                "name": p.name,
                "type": p.param_type.value,
                "description": p.description,
                "required": p.required,
                "default": str(p.default) if p.default is not None else None,
            }
            for p in c.params.values()
        ]
        result.append(
            {
                "name": name,
                "description": c.description,
                "aliases": c.aliases,
                "authority_level": c.authority_level,
                "usage": c.get_usage_string(),
                "examples": c.examples,
                "params": params,
            }
        )
    return sorted(result, key=lambda x: x["name"])


class SendMsgBody(BaseModel):
    group_id: int
    message: str | list


@router.post("/api/message/send")
async def api_send_message(
    body: SendMsgBody,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    send: QQAPIClient = container.get("SendMessage")
    payload = {"group_id": body.group_id, "message": body.message}
    result = await send.async_send("send_group_msg", payload, echo=True)
    return {"status": "ok", "result": result}


@router.get("/api/config")
async def api_get_config(_: None = Depends(_auth)) -> Dict[str, Any]:
    cfg = container.get("config")
    return {
        "content": json.dumps(cfg._raw_config, ensure_ascii=False, indent=2),
        "path": str(cfg.config_file_path),
    }


class ConfigBody(BaseModel):
    content: str


@router.post("/api/config")
async def api_save_config(
    body: ConfigBody,
    _: None = Depends(_auth),
) -> Dict[str, str]:
    cfg = container.get("config")
    try:
        parsed = json.loads(body.content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON 格式错误: {e}")

    config_path = cfg.config_file_path

    config_path.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    return {"status": "ok"}

@router.get("/api/supplier_config")
async def api_get_supplier_config(_: None = Depends(_auth)) -> Dict[str, Any]:
    cfg = container.get("config")
    supplier_path = cfg.file_path.supplier_config_path
    raw = supplier_path.read_text(encoding="utf-8")
    return {
        "content": json.dumps(json.loads(raw), ensure_ascii=False, indent=2),
        "path": str(supplier_path),
        "suppliers": _parse_supplier_summary(json.loads(raw)),
    }


def _parse_supplier_summary(data: dict) -> list:
    result = []
    for item in data.get("api", []):
        result.append({
            "name": item.get("name", ""),
            "base_url": item.get("base_url", ""),
            "api_key": item.get("api_key", ""),
            "models": list(item.get("models", {}).keys()),
        })
    return result


class SupplierConfigBody(BaseModel):
    content: str


@router.post("/api/supplier_config")
async def api_save_supplier_config(
    body: SupplierConfigBody,
    _: None = Depends(_auth),
) -> Dict[str, str]:
    cfg = container.get("config")
    try:
        parsed = json.loads(body.content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON 格式错误: {e}")

    supplier_path = cfg.file_path.supplier_config_path

    supplier_path.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    return {"status": "ok"}
  

@router.post("/api/system/stop")
async def api_system_stop(_: None = Depends(_auth)) -> Dict[str, str]:
    loop = asyncio.get_event_loop()
    loop.call_later(0.5, lambda: os._exit(0))
    return {"status": "stopping"}


@router.post("/api/system/restart")
async def api_system_restart(_: None = Depends(_auth)) -> Dict[str, str]:
    cfg = container.get("config")
    subprocess_args = [sys.executable] + sys.argv
    cwd = str(cfg.file_path.project_root)

    def _do_restart() -> None:
        import subprocess as _sp
        _sp.Popen(subprocess_args, cwd=cwd)
        os._exit(0)

    loop = asyncio.get_event_loop()
    loop.call_later(0.5, _do_restart)
    return {"status": "restarting"}


_HTML = """<!DOCTYPE html>
<html lang="zh-CN" data-bs-theme="light">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>ATRI 管理面板</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"/>
  <style>
    :root {
      --bg-color: #f8fafc;
      --card-bg: #ffffff;
      --border-color: #e2e8f0;
      --accent-color: #2563eb;
      --text-main: #1e293b;
      --text-muted: #64748b;
    }
    body { 
      background-color: var(--bg-color); 
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    /* 自定义滚动条 */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: var(--bg-color); }
    ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

    /* 卡片基础样式 */
    .stat-card { 
      border: 1px solid var(--border-color); 
      background-color: var(--card-bg); 
      border-radius: 12px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    .stat-card:hover { 
      transform: translateY(-4px); 
      box-shadow: 0 12px 20px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05); 
      border-color: #cbd5e1;
    }
    .stat-card .card-header {
      border-bottom: 1px solid var(--border-color);
      background-color: #f8fafc;
      border-top-left-radius: 11px !important;
      border-top-right-radius: 11px !important;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: #334155;
    }

    /* 登录遮罩 */
    #login-overlay { 
      position: fixed; inset: 0; z-index: 9999; 
      background: radial-gradient(circle at center, #f1f5f9 0%, #e2e8f0 100%);
      display: flex; align-items: center; justify-content: center; 
    }
    #login-overlay .card {
      border-radius: 16px;
      box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.5);
    }

    /* 导航栏 */
    .navbar {
      background: rgba(255, 255, 255, 0.9) !important;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border-color) !important;
      position: sticky;
      top: 0;
      z-index: 1000;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .navbar-brand {
      color: var(--text-main) !important;
    }

    /* 选项卡 Nav */
    .nav-tabs {
      border-bottom: none;
      gap: 0.5rem;
      background: var(--card-bg);
      padding: 0.5rem;
      border-radius: 12px;
      border: 1px solid var(--border-color);
      box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .nav-tabs .nav-link { 
      cursor: pointer; 
      transition: all 0.2s ease;
      border: none;
      border-radius: 8px;
      color: var(--text-muted);
      padding: 0.5rem 1.2rem;
      font-weight: 500;
    }
    .nav-tabs .nav-link:hover {
      background: #f1f5f9;
      color: var(--text-main);
      border: none;
    }
    .nav-tabs .nav-link.active { 
      background: var(--accent-color);
      color: #fff !important;
      font-weight: 600;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
      border: none;
    }

    /* 数据表格 */
    .table-responsive { 
      background: var(--card-bg);
      border-radius: 12px;
      border: 1px solid var(--border-color);
      padding: 0;
      overflow: hidden;
      animation: fadeIn 0.4s; 
      box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    .table { margin-bottom: 0; --bs-table-bg: transparent; --bs-table-color: var(--text-main); }
    .table th { 
      font-size: 0.75rem; 
      text-transform: uppercase; 
      letter-spacing: 0.05em; 
      color: #475569; 
      background-color: #f8fafc !important;
      border-bottom: 1px solid var(--border-color) !important;
      padding: 1rem 0.75rem;
      font-weight: 600;
      border-top: none;
    }
    .table-light {
        --bs-table-bg: transparent;
        --bs-table-striped-bg: transparent;
        color: var(--text-main);
    }
    .table td { 
      font-size: 0.88rem; 
      vertical-align: middle; 
      border-bottom: 1px solid var(--border-color);
      padding: 0.85rem 0.75rem;
      color: var(--text-main);
    }
    .table tr:last-child td { border-bottom: none; }
    .table-hover tbody tr:hover { background-color: #f1f5f9; }
    
    /* 分页按钮 */
    .page-btn { display: inline-flex; gap: 4px; flex-wrap: wrap; align-items: center; }
    .pagination { gap: 4px; }
    .page-item .page-link {
      border-radius: 8px !important;
      border: 1px solid var(--border-color);
      background: var(--card-bg);
      color: var(--text-main);
      padding: 0.35rem 0.7rem;
      box-shadow: none !important;
    }
    .page-item.active .page-link {
      background: var(--accent-color);
      border-color: var(--accent-color);
      color: white;
    }
    .page-item.disabled .page-link {
      background: #f8fafc;
      border-color: var(--border-color);
      color: var(--text-muted);
    }

    /* 预格式化文本框 */
    pre.cell { 
      white-space: pre-wrap; word-break: break-all; font-size: 0.8rem;
      max-height: 80px; overflow-y: auto; margin: 0; 
      background: #f1f5f9; border-radius: 8px; padding: 8px 10px; 
      border: 1px solid #e2e8f0;
      color: #334155;
    }

    /* 表单与按钮 */
    .btn { border-radius: 8px; font-weight: 500; transition: all 0.2s; }
    .btn-primary { 
      background-color: var(--accent-color); 
      border-color: var(--accent-color); 
      color: white;
    }
    .btn-primary:hover {
      background-color: #1d4ed8;
      border-color: #1d4ed8;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    .btn-outline-secondary {
      color: #475569;
      border-color: #cbd5e1;
      background-color: white;
    }
    .btn-outline-secondary:hover {
      background-color: #f1f5f9;
      color: #0f172a;
    }
    .form-control, .form-select {
      background-color: #ffffff;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      border-radius: 8px;
    }
    .form-control:focus, .form-select:focus {
      background-color: #ffffff;
      border-color: var(--accent-color);
      box-shadow: 0 0 0 0.2rem rgba(37, 99, 235, 0.15);
      color: var(--text-main);
    }
    .form-control::placeholder { color: #94a3b8; }
    .badge { border-radius: 6px; font-weight: 500; padding: 0.4em 0.6em; }
    
    /* 配置文件编辑器补丁 */
    textarea#cfg-editor, textarea#sup-editor {
      background-color: #f8fafc !important;
      border: 1px solid var(--border-color) !important;
      border-radius: 12px;
      padding: 1rem;
      line-height: 1.5;
      color: #1e293b;
    }
    textarea#cfg-editor:focus, textarea#sup-editor:focus {
      background-color: #ffffff !important;
      border-color: var(--accent-color) !important;
      box-shadow: 0 0 0 0.2rem rgba(37, 99, 235, 0.15) !important;
    }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>
<body>

<!-- 登录遮罩 -->
<div id="login-overlay">
  <div class="card" style="width:340px;">
    <div class="card-body p-4">
      <h5 class="mb-2 text-center fw-bold" style="letter-spacing: 0.05em; color: var(--text-main);">⚡ ATRI 管理面板</h5>
      <p class="text-muted text-center small mb-4">请输入 access_token 登录</p>
      <input id="token-input" type="password" class="form-control mb-3 py-2" placeholder="access_token"/>
      <button class="btn btn-primary w-100 py-2" onclick="login()" style="font-weight: 600;">登录 Dashboard</button>
      <div id="login-err" class="text-danger small mt-3 text-center" style="min-height: 20px;"></div>
    </div>
  </div>
</div>

<!-- 主页面 -->
<div id="app" style="display:none;">

  <!-- 导航栏 -->
  <nav class="navbar navbar-light border-bottom px-3 py-2">
    <span class="navbar-brand fw-bold mb-0 fs-6" style="letter-spacing: 0.05em;">⚡ ATRI 管理面板</span>
    <div class="d-flex align-items-center gap-3">
      <span id="nav-uptime" class="text-muted small fw-medium"></span>
      <button class="btn btn-sm btn-outline-danger px-3" style="border-radius: 6px;" onclick="logout()">退出</button>
    </div>
  </nav>

  <div class="container-fluid px-4 pt-4 pb-4">

    <!-- Tab 导航 -->
    <ul class="nav nav-tabs mb-3" id="mainTabs">
      <li class="nav-item"><a class="nav-link active" onclick="switchTab('dashboard')">📊 概览</a></li>
      <li class="nav-item"><a class="nav-link" onclick="switchTab('groups')">👥 群组</a></li>
      <li class="nav-item"><a class="nav-link" onclick="switchTab('users')">👤 用户</a></li>
      <li class="nav-item"><a class="nav-link" onclick="switchTab('messages')">💬 消息</a></li>
      <li class="nav-item"><a class="nav-link" onclick="switchTab('memory')">🧠 记忆</a></li>
      <li class="nav-item"><a class="nav-link" onclick="switchTab('commands')">⚡ 命令</a></li>
      <li class="nav-item ms-auto"><a class="nav-link" onclick="switchTab('system')">⚙️ 系统</a></li>
    </ul>

    <!-- ══ 概览 ══ -->
    <div id="tab-dashboard">
      <div class="row g-3 mb-3" id="stat-cards"></div>
      <div class="row g-3">
        <div class="col-md-6">
          <div class="card stat-card">
            <div class="card-header fw-semibold">Bot 状态</div>
            <div class="card-body" id="status-info">
              <div class="spinner-border spinner-border-sm text-secondary"></div>
            </div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="card stat-card">
            <div class="card-header fw-semibold">发送群消息</div>
            <div class="card-body">
              <select id="send-group-sel" class="form-select form-select-sm mb-2">
                <option value="">加载中...</option>
              </select>
              <textarea id="send-msg-txt" class="form-control form-control-sm mb-2"
                        rows="3" placeholder="消息内容"></textarea>
              <button class="btn btn-sm btn-primary" onclick="sendMessage()">发送</button>
              <span id="send-result" class="ms-2 small"></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ══ 群组 ══ -->
    <div id="tab-groups" style="display:none;">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <span class="fw-semibold">群组列表</span>
        <button class="btn btn-sm btn-outline-secondary" onclick="loadGroups(1)">↻ 刷新</button>
      </div>
      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead class="table-light"><tr><th>群号</th><th>群名</th></tr></thead>
          <tbody id="groups-tbody"></tbody>
        </table>
      </div>
      <div class="page-btn mt-2" id="groups-page"></div>
    </div>

    <!-- ══ 用户 ══ -->
    <div id="tab-users" style="display:none;">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <span class="fw-semibold">用户列表</span>
        <button class="btn btn-sm btn-outline-secondary" onclick="loadUsers(1)">↻ 刷新</button>
      </div>
      <div class="table-responsive">
        <table class="table table-hover align-middle">
          <thead class="table-light"><tr><th>用户ID</th><th>昵称</th><th>最后活跃</th><th>权限</th></tr></thead>
          <tbody id="users-tbody"></tbody>
        </table>
      </div>
      <div class="page-btn mt-2" id="users-page"></div>
    </div>

    <!-- ══ 消息 ══ -->
    <div id="tab-messages" style="display:none;">
      <div class="d-flex flex-wrap gap-2 align-items-center mb-2">
        <span class="fw-semibold">消息历史</span>
        <input id="msg-gid" type="number" class="form-control form-control-sm"
               style="width:130px;" placeholder="群号"/>
        <input id="msg-uid" type="number" class="form-control form-control-sm"
               style="width:130px;" placeholder="用户ID"/>
        <button class="btn btn-sm btn-primary" onclick="loadMessages(1)">查询</button>
        <button class="btn btn-sm btn-outline-secondary"
                onclick="msgClear()">清除</button>
      </div>
      <div class="table-responsive mt-3">
        <table class="table table-hover align-middle">
          <thead class="table-light"><tr><th>时间</th><th>用户</th><th>群号</th><th>消息内容</th></tr></thead>
          <tbody id="messages-tbody"></tbody>
        </table>
      </div>
      <div class="page-btn mt-2" id="messages-page"></div>
    </div>

    <!-- ══ 记忆 ══ -->
    <div id="tab-memory" style="display:none;">
      <div class="d-flex flex-wrap gap-2 align-items-center mb-2">
        <span class="fw-semibold">记忆系统</span>
        <select id="mem-cat" class="form-select form-select-sm" style="width:150px;">
          <option value="">全部分类</option>
          <option value="preference">偏好</option>
          <option value="fact">事实</option>
          <option value="experience">经历</option>
          <option value="emotion">情感</option>
          <option value="group_topic">群话题</option>
          <option value="knowledge">知识</option>
          <option value="domain">领域知识</option>
          <option value="guideline">行为准则</option>
        </select>
        <input id="mem-uid" type="number" class="form-control form-control-sm"
               style="width:130px;" placeholder="用户ID"/>
        <button class="btn btn-sm btn-primary" onclick="loadMemory(1)">查询</button>
        <button class="btn btn-sm btn-outline-secondary"
                onclick="memClear()">清除</button>
      </div>
      <div class="table-responsive mt-3">
        <table class="table table-hover align-middle">
          <thead class="table-light">
            <tr><th>ID</th><th>用户</th><th>群</th><th>分类</th>
                <th>重要性</th><th>可信度</th><th>访问</th><th>时间</th><th>内容</th></tr>
          </thead>
          <tbody id="memory-tbody"></tbody>
        </table>
      </div>
      <div class="page-btn mt-2" id="memory-page"></div>
    </div>

    <!-- ══ 命令 ══ -->
    <div id="tab-commands" style="display:none;">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <span class="fw-semibold">已注册命令</span>
        <button class="btn btn-sm btn-outline-secondary" onclick="loadCommands()">↻ 刷新</button>
      </div>
      <div id="commands-list" class="row g-2"></div>
    </div>

    <!-- ══ 系统 ══ -->
    <div id="tab-system" style="display:none;">
      <div class="row g-3">

        <!-- Bot 控制 -->
        <div class="col-md-3">
          <div class="card stat-card">
            <div class="card-header fw-semibold">Bot 控制</div>
            <div class="card-body d-flex flex-column gap-2">
              <p class="text-muted small mb-1">
                停止会立即终止进程；重启将重新启动 main.py。<br/>
                <span class="text-warning small">⚠ 重启前请确保先<b>保存配置</b>。</span>
              </p>
              <button class="btn btn-warning" onclick="sysRestart()">🔄 重启 Bot</button>
              <button class="btn btn-danger" onclick="sysStop()">⏹ 停止 Bot</button>
              <div id="sys-result" class="small mt-1"></div>
            </div>
          </div>
        </div>

        <!-- 配置编辑区 -->
        <div class="col-md-9">
          <!-- 子 Tab -->
          <ul class="nav nav-tabs mb-2" id="cfgTabs">
            <li class="nav-item">
              <a class="nav-link active" onclick="switchCfgTab('main')" id="cfgtab-main">
                📄 主配置 (config.json)
              </a>
            </li>
            <li class="nav-item">
              <a class="nav-link" onclick="switchCfgTab('supplier')" id="cfgtab-supplier">
                🔌 供应商配置 (supplier_config.json)
              </a>
            </li>
          </ul>

          <!-- 主配置 -->
          <div id="cfgpanel-main">
            <div class="mb-2 d-flex gap-2 align-items-center flex-wrap">
              <button class="btn btn-sm btn-outline-secondary" onclick="loadConfig()">↻ 重新加载</button>
              <button class="btn btn-sm btn-primary" onclick="saveConfig()">💾 保存配置</button>
              <button class="btn btn-sm btn-outline-info" onclick="toggleRef('cfg-ref')">📖 字段说明</button>
              <span id="cfg-result" class="small ms-1"></span>
              <span id="cfg-path" class="text-muted small ms-auto"></span>
            </div>
            <textarea id="cfg-editor" class="form-control font-monospace"
                      style="min-height:400px; font-size:0.85rem; resize:vertical;"
                      spellcheck="false"></textarea>
            <!-- config.json 字段说明 -->
            <div id="cfg-ref" style="display:none;" class="mt-3">
              <div class="card stat-card">
                <div class="card-header small fw-semibold">📖 config.json 字段说明</div>
                <div class="card-body p-2" style="font-size:.8rem;">
                  <table class="table table-sm table-borderless mb-0" style="font-size:.78rem;">
                    <thead><tr><th style="width:35%">字段路径</th><th>说明</th><th style="width:18%">示例 / 可选值</th></tr></thead>
                    <tbody>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">network — 网络连接</td></tr>
                      <tr><td><code>network.connection_type</code></td><td>连接 NapCat 的方式</td><td><code>WebSocket_server</code> / <code>WebSocket_client</code> / <code>http</code></td></tr>
                      <tr><td><code>network.access_token</code></td><td>鉴权 Token，需与 NapCat 一致，同时也是管理面板登录密码</td><td><code>"ATRI114514"</code></td></tr>
                      <tr><td><code>network.url</code></td><td>WebSocket_client 模式下 NapCat 的地址，或 HTTP 回调地址</td><td><code>"127.0.0.1:8080"</code></td></tr>
                      <tr><td><code>network.host</code></td><td>WebSocket_server 监听绑定的地址</td><td><code>"127.0.0.1"</code></td></tr>
                      <tr><td><code>network.server_port</code></td><td>主服务监听端口</td><td><code>8888</code></td></tr>
                      <tr><td><code>network.admin_port</code></td><td>Web 管理面板监听端口（默认 server_port+1）</td><td><code>8889</code></td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">account — 账号</td></tr>
                      <tr><td><code>account.id</code></td><td>Bot 的 QQ 号</td><td><code>123456789</code></td></tr>
                      <tr><td><code>account.name</code></td><td>Bot 的名称（用于日志/面板显示）</td><td><code>"ATRI-bot"</code></td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">model.connect — 主模型</td></tr>
                      <tr><td><code>model.connect.supplier</code></td><td>使用的供应商名称，须与 supplier_config.json 中 name 一致</td><td><code>"deepseek"</code></td></tr>
                      <tr><td><code>model.connect.model_name</code></td><td>模型标识，须在该供应商的 models 中存在</td><td><code>"deepseek/deepseek-chat"</code></td></tr>
                      <tr><td><code>model.connect.visual_sense</code></td><td>是否启用图像理解（多模态）</td><td><code>true</code> / <code>false</code></td></tr>
                      <tr><td><code>model.connect.user_global_context</code></td><td>是否将用户历史（跨群）加入上下文</td><td><code>true</code> / <code>false</code></td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">model.chat_parameter — 对话参数</td></tr>
                      <tr><td><code>temperature</code></td><td>生成随机性，越高越发散</td><td><code>0.0</code> ~ <code>2.0</code></td></tr>
                      <tr><td><code>max_tokens</code></td><td>单次最大输出 token 数</td><td><code>8000</code></td></tr>
                      <tr><td><code>tool_choice</code></td><td>工具调用策略</td><td><code>"auto"</code> / <code>"none"</code></td></tr>
                      <tr><td><code>thinking_level</code></td><td>思考深度（部分模型支持）</td><td><code>"high"</code> / <code>"medium"</code> / <code>"low"</code></td></tr>
                      <tr><td><code>stream</code></td><td>是否启用流式输出</td><td><code>true</code> / <code>false</code></td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">model.standby_model — 备用模型</td></tr>
                      <tr><td><code>standby_model[].supplier</code></td><td>备用模型的供应商，主模型不可用时按顺序切换</td><td>—</td></tr>
                      <tr><td><code>standby_model[].model_name</code></td><td>备用模型名称</td><td>—</td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">model.RAG — 向量检索</td></tr>
                      <tr><td><code>RAG.enable</code></td><td>是否启用 RAG 记忆检索</td><td><code>true</code> / <code>false</code></td></tr>
                      <tr><td><code>RAG.dimensions</code></td><td>向量维度，需与 Embedding 模型一致</td><td><code>1024</code></td></tr>
                      <tr><td><code>RAG.use_embedding_model</code></td><td>Embedding 模型（supplier + model_name）</td><td>—</td></tr>
                      <tr><td><code>RAG.use_reranker_model</code></td><td>Reranker 重排序模型（supplier + model_name）</td><td>—</td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">ai_chat — 对话行为</td></tr>
                      <tr><td><code>ai_chat.playRole</code></td><td>角色设定名称，对应 character_setting 目录下的文件夹</td><td><code>"ATRI_simplify"</code></td></tr>
                      <tr><td><code>ai_chat.ai_max_record</code></td><td>送入 LLM 的最大上下文轮数</td><td><code>20</code></td></tr>
                      <tr><td><code>ai_chat.group_max_record</code></td><td>群聊消息缓冲区最大保留条数</td><td><code>20</code></td></tr>
                      <tr><td><code>ai_chat.private_max_record</code></td><td>私聊消息缓冲区最大保留条数</td><td><code>20</code></td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">群组白名单</td></tr>
                      <tr><td><code>group_white_list</code></td><td>允许 Bot 响应的群号列表，空数组表示不限制</td><td><code>[123456, 789012]</code></td></tr>
                      <tr><td><code>group_initiative_chat_white_list</code></td><td>允许 Bot 主动发起对话的群号列表</td><td><code>[123456]</code></td></tr>
                      <tr><td><code>group_information_extraction</code></td><td>自动提取话题信息并存入记忆的群号列表</td><td><code>[123456]</code></td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">database — 数据库</td></tr>
                      <tr><td><code>database.host</code></td><td>PostgreSQL 主机地址</td><td><code>"127.0.0.1"</code></td></tr>
                      <tr><td><code>database.port</code></td><td>PostgreSQL 端口</td><td><code>5432</code></td></tr>
                      <tr><td><code>database.user</code></td><td>数据库用户名</td><td><code>"atri"</code></td></tr>
                      <tr><td><code>database.password</code></td><td>数据库密码</td><td><code>"180710"</code></td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">sand_box — 代码沙盒</td></tr>
                      <tr><td><code>sand_box.image</code></td><td>Docker 沙盒镜像名称，镜像不存在时沙盒初始化会跳过但不影响启动</td><td><code>"atri-sandbox:latest"</code></td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          <!-- 供应商配置 -->
          <div id="cfgpanel-supplier" style="display:none;">
            <div class="mb-2 d-flex gap-2 align-items-center flex-wrap">
              <button class="btn btn-sm btn-outline-secondary" onclick="loadSupplierConfig()">↻ 重新加载</button>
              <button class="btn btn-sm btn-primary" onclick="saveSupplierConfig()">💾 保存供应商配置</button>
              <button class="btn btn-sm btn-outline-info" onclick="toggleRef('sup-ref')">📖 字段说明</button>
              <span id="sup-result" class="small ms-1"></span>
              <span id="sup-path" class="text-muted small ms-auto"></span>
            </div>
            <!-- 供应商卡片预览 -->
            <div id="sup-cards" class="row g-2 mb-3"></div>
            <div class="text-muted small mb-2 ms-1 fw-medium">原始 JSON(直接编辑)：</div>
            <textarea id="sup-editor" class="form-control font-monospace"
                      style="min-height:360px; font-size:0.85rem; resize:vertical;"
                      spellcheck="false"></textarea>
            <!-- supplier_config.json 字段说明 -->
            <div id="sup-ref" style="display:none;" class="mt-3">
              <div class="card stat-card">
                <div class="card-header small fw-semibold">📖 supplier_config.json 字段说明</div>
                <div class="card-body p-2" style="font-size:.8rem;">
                  <p class="text-muted small mb-2">
                    顶层结构为 <code>{"api": [...]}}</code>,<code>api</code> 数组中每个对象代表一个供应商。
                    供应商 <code>name</code> 需与 <code>config.json</code> 中 <code>model.connect.supplier</code> 等字段一致。
                  </p>
                  <table class="table table-sm table-borderless mb-0" style="font-size:.78rem;">
                    <thead><tr><th style="width:28%">字段</th><th>说明</th><th style="width:24%">示例 / 备注</th></tr></thead>
                    <tbody>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">api[] — 供应商条目</td></tr>
                      <tr><td><code>name</code></td><td>供应商唯一标识，在 config.json 中通过此名称引用</td><td><code>"deepseek"</code></td></tr>
                      <tr><td><code>base_url</code></td><td>API 端点 URL（OpenAI 兼容格式），必须以 <code>/chat/completions</code> 结尾或为 Ollama embed 地址</td><td><code>"https://api.deepseek.com/v1/chat/completions"</code></td></tr>
                      <tr><td><code>api_key</code></td><td>鉴权 Key。支持字符串（单 key）或字符串数组（多 key 轮询池）</td><td><code>"sk-xxx"</code> 或 <code>["sk-a","sk-b"]</code></td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">models — 该供应商支持的模型</td></tr>
                      <tr><td><code>models</code></td><td>对象，键为模型名，值为该模型的属性</td><td><code>{"gpt-4o": {...}}</code></td></tr>
                      <tr><td><code>models.*.visual_sense</code></td><td>该模型是否支持图像输入（多模态）</td><td><code>true</code> / <code>false</code></td></tr>
                      <tr class="table-active"><td colspan="3" class="fw-semibold py-1">常见供应商配置示例</td></tr>
                      <tr><td>OpenAI / 兼容接口</td><td colspan="2"><code>base_url</code> 填 <code>https://api.openai.com/v1/chat/completions</code>，模型名如 <code>gpt-4o</code></td></tr>
                      <tr><td>Ollama 本地 Embed</td><td colspan="2"><code>base_url</code> 填 <code>http://localhost:11434/api/embed</code>，用于 RAG 向量化，不走 chat 接口</td></tr>
                      <tr><td>多 Key 轮询</td><td colspan="2"><code>api_key</code> 改为数组：<code>["sk-key1","sk-key2"]</code>，系统自动均衡分发</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div><!-- /container -->
</div><!-- /app -->

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
const TAB_NAMES  = ['dashboard','groups','users','messages','memory','commands','system'];
const PERM_MAP   = {blacklist:'<span class="badge bg-danger">黑名单</span>',
                    administrator:'<span class="badge bg-info text-dark">管理员</span>',
                    root:'<span class="badge bg-warning text-dark">Root</span>'};
const CAT_MAP    = {preference:'偏好',fact:'事实',experience:'经历',emotion:'情感',
                    group_topic:'群话题',knowledge:'知识',domain:'领域知识',guideline:'行为准则'};
const AUTH_LABELS = ['无限制','普通用户','管理员','Root'];

/* ── API 工具 ── */
async function api(path, opts={}) {
  const token = localStorage.getItem('atriToken');
  const resp = await fetch('/admin' + path, {
    ...opts,
    headers: {'Authorization':'Bearer '+token,'Content-Type':'application/json',...(opts.headers||{})}
  });
  if (resp.status === 401) { logout(); return null; }
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

/* ── 登录 / 登出 ── */
async function login() {
  const token = document.getElementById('token-input').value.trim();
  if (!token) return;
  localStorage.setItem('atriToken', token);
  try {
    const st = await api('/api/status');
    if (!st) return;
    document.getElementById('login-overlay').style.display = 'none';
    document.getElementById('app').style.display = 'block';
    initApp();
  } catch(e) {
    document.getElementById('login-err').textContent = '令牌错误或服务未就绪';
    localStorage.removeItem('atriToken');
  }
}
function logout() {
  localStorage.removeItem('atriToken');
  location.reload();
}

/* ── 初始化 ── */
function initApp() {
  loadDashboard();
  loadGroupsForSelect();
  setInterval(tickUptime, 10000);
}

/* ── Tab 切换 ── */
function switchTab(tab) {
  TAB_NAMES.forEach(t => {
    document.getElementById('tab-'+t).style.display = t===tab ? 'block' : 'none';
  });
  document.querySelectorAll('#mainTabs .nav-link').forEach((el,i) => {
    el.classList.toggle('active', TAB_NAMES[i]===tab);
  });
  ({dashboard:loadDashboard, groups:()=>loadGroups(1), users:()=>loadUsers(1),
    messages:()=>loadMessages(1), memory:()=>loadMemory(1), commands:loadCommands,
    system:loadSystem})[tab]?.();
}

/* ── 概览 ── */
async function loadDashboard() {
  const [stats, status] = await Promise.all([api('/api/stats'), api('/api/status')]);
  if (!stats || !status) return;
  updateUptime(status.uptime);

  document.getElementById('stat-cards').innerHTML = [
    ['👥 群组','groups','primary'],['👤 用户','users','success'],
    ['💬 消息','messages','info'],  ['🧠 记忆','memories','warning'],
  ].map(([label,key,color]) =>
    `<div class="col-6 col-md-3">
       <div class="card stat-card text-center p-4 h-100 d-flex flex-column justify-content-center">
         <div class="display-5 fw-bold text-${color} mb-1" style="text-shadow: 0 0 20px rgba(var(--bs-${color}-rgb), 0.3);">${stats[key]}</div>
         <div class="text-muted small fw-medium mt-2" style="letter-spacing: 0.05em;">${label}</div>
       </div></div>`).join('');

  const dot = (ok,txt) =>
    `<span class="badge ${ok?'bg-success':'bg-secondary'} me-1">${txt}</span>`;
  document.getElementById('status-info').innerHTML =
    `<table class="table table-sm table-borderless mb-0 small">
       <tr><td class="text-muted w-25">账号</td><td>${esc(status.account_name)} (${status.account_id})</td></tr>
       <tr><td class="text-muted">模型</td><td>${esc(status.model)}</td></tr>
       <tr><td class="text-muted">供应商</td><td>${esc(status.supplier)}</td></tr>
       <tr><td class="text-muted">连接方式</td><td>${esc(status.connection_type)}</td></tr>
       <tr><td class="text-muted">运行时长</td><td>${status.uptime}</td></tr>
       <tr><td class="text-muted">服务</td>
           <td>${dot(status.mcp,'MCP')}${dot(status.sandbox,'Sandbox')}${dot(status.rag,'RAG')}</td></tr>
     </table>`;
}

async function tickUptime() {
  const st = await api('/api/status');
  if (st) updateUptime(st.uptime);
}
function updateUptime(t) {
  document.getElementById('nav-uptime').textContent = '运行 ' + t;
}

/* ── 群组 select (发送消息用) ── */
async function loadGroupsForSelect() {
  const data = await api('/api/groups?all=true');
  if (!data || !data.items) return;
  const groups = data.items;
  document.getElementById('send-group-sel').innerHTML =
    '<option value="">选择群组…</option>' +
    groups.map(g => `<option value="${g.group_id}">${esc(g.group_name)} (${g.group_id})</option>`).join('');
}

/* ── 群组 Tab ── */
async function loadGroups(page=1) {
  const data = await api(`/api/groups?page=${page}&limit=20`);
  if (!data) return;
  document.getElementById('groups-tbody').innerHTML = data.items.length
    ? data.items.map(g =>
        `<tr><td><code>${g.group_id}</code></td><td>${esc(g.group_name)}</td></tr>`).join('')
    : '<tr><td colspan="2" class="text-center text-muted small">暂无数据</td></tr>';
  renderPage('groups-page', page, Math.ceil(data.total/data.limit), loadGroups);
}

/* ── 用户 Tab ── */
async function loadUsers(page) {
  const data = await api(`/api/users?page=${page}&limit=20`);
  if (!data) return;
  document.getElementById('users-tbody').innerHTML = data.items.length
    ? data.items.map(u => {
        const perm = u.permission_type;
        const badge = perm ? (PERM_MAP[perm] || `<span class="badge bg-secondary">${esc(perm)}</span>`)
                           : '<span class="text-muted small">普通</span>';
        return `<tr>
          <td><code>${u.user_id}</code></td>
          <td>${esc(u.nickname)}</td>
          <td class="text-muted small">${u.last_updated||''}</td>
          <td>${badge}</td>
        </tr>`;
      }).join('')
    : '<tr><td colspan="4" class="text-center text-muted small">暂无数据</td></tr>';
  renderPage('users-page', page, Math.ceil(data.total/data.limit), loadUsers);
}

/* ── 消息 Tab ── */
function msgClear() {
  document.getElementById('msg-gid').value='';
  document.getElementById('msg-uid').value='';
  loadMessages(1);
}
async function loadMessages(page) {
  const gid = document.getElementById('msg-gid').value;
  const uid = document.getElementById('msg-uid').value;
  let url = `/api/messages?page=${page}&limit=50`;
  if (gid) url += `&group_id=${gid}`;
  if (uid) url += `&user_id=${uid}`;
  const data = await api(url);
  if (!data) return;
  document.getElementById('messages-tbody').innerHTML = data.items.length
    ? data.items.map(m =>
        `<tr>
           <td class="text-muted small text-nowrap">${m.time_str||''}</td>
           <td><code>${m.user_id}</code><br/><span class="text-muted small">${esc(m.nickname||'')}</span></td>
           <td><code>${m.group_id??'-'}</code></td>
           <td style="max-width:380px;"><pre class="cell">${esc(m.message_content||'')}</pre></td>
         </tr>`).join('')
    : '<tr><td colspan="4" class="text-center text-muted small">暂无数据</td></tr>';
  renderPage('messages-page', page, Math.ceil(data.total/data.limit), loadMessages);
}

/* ── 记忆 Tab ── */
function memClear() {
  document.getElementById('mem-cat').value='';
  document.getElementById('mem-uid').value='';
  loadMemory(1);
}
async function loadMemory(page) {
  const cat = document.getElementById('mem-cat').value;
  const uid = document.getElementById('mem-uid').value;
  let url = `/api/memory?page=${page}&limit=20`;
  if (cat) url += `&category=${cat}`;
  if (uid) url += `&user_id=${uid}`;
  const data = await api(url);
  if (!data) return;
  document.getElementById('memory-tbody').innerHTML = data.items.length
    ? data.items.map(m =>
        `<tr>
           <td class="text-muted small">${m.memory_id}</td>
           <td><code>${m.user_id??'知识库'}</code></td>
           <td><code>${m.group_id??'-'}</code></td>
           <td><span class="badge bg-secondary" style="font-size:.7rem;">${CAT_MAP[m.category]||m.category}</span></td>
           <td class="text-center"><span class="badge bg-danger">${m.importance}</span></td>
           <td class="text-center"><span class="badge bg-info text-dark">${m.credibility}</span></td>
           <td class="text-center text-muted small">${m.access_count}</td>
           <td class="text-muted small text-nowrap">${m.event_time_str||''}</td>
           <td style="max-width:320px;"><pre class="cell">${esc(m.event||'')}</pre></td>
         </tr>`).join('')
    : '<tr><td colspan="9" class="text-center text-muted small">暂无数据</td></tr>';
  renderPage('memory-page', page, Math.ceil(data.total/data.limit), loadMemory);
}

/* ── 命令 Tab ── */
async function loadCommands() {
  const cmds = await api('/api/commands');
  if (!cmds) return;
  document.getElementById('commands-list').innerHTML = cmds.map(c => {
    const aliasHtml = c.aliases.length
      ? `<div class="small mb-1 text-muted">别名: ${c.aliases.map(a=>`<code>/${esc(a)}</code>`).join(' ')}</div>` : '';
    const exHtml = c.examples.length
      ? `<div class="mt-1">${c.examples.map(e=>`<code class="small text-muted">${esc(e)}</code>`).join('<br/>')}</div>` : '';
    return `<div class="col-md-6 col-lg-4">
      <div class="card stat-card h-100">
        <div class="card-body p-3">
          <div class="d-flex justify-content-between align-items-start mb-1">
            <span class="fw-bold">/${esc(c.name)}</span>
            <span class="badge bg-secondary">${AUTH_LABELS[c.authority_level]??c.authority_level}</span>
          </div>
          <p class="text-muted small mb-1">${esc(c.description)}</p>
          ${aliasHtml}
          <code class="small text-info d-block">${esc(c.usage)}</code>
          ${exHtml}
        </div>
      </div></div>`;
  }).join('');
}

/* ── 发送消息 ── */
async function sendMessage() {
  const gid = document.getElementById('send-group-sel').value;
  const raw = document.getElementById('send-msg-txt').value.trim();
  const res = document.getElementById('send-result');
  if (!gid || !raw) {
    res.textContent='请选择群组并输入内容'; res.className='ms-2 small text-warning'; return;
  }
  // 若输入是 JSON 数组则解析为消息段列表，否则当作纯文本字符串
  let message = raw;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) message = parsed;
  } catch(e) {}
  try {
    const data = await api('/api/message/send', {method:'POST', body:JSON.stringify({group_id:+gid, message})});
    const msgId = data?.result?.data?.message_id;
    res.innerHTML = '✓ 发送成功' + (msgId != null ? ` <code class="text-muted">message_id: ${msgId}</code>` : '');
    res.className='ms-2 small text-success';
    document.getElementById('send-msg-txt').value='';
  } catch(e) {
    res.textContent='✗ '+e.message; res.className='ms-2 small text-danger';
  }
}

/* ── 字段说明折叠 ── */
function toggleRef(id) {
  const el = document.getElementById(id);
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

/* ── 系统 Tab ── */
function switchCfgTab(tab) {
  ['main','supplier'].forEach(t => {
    document.getElementById('cfgpanel-'+t).style.display = t===tab ? 'block' : 'none';
    document.getElementById('cfgtab-'+t).classList.toggle('active', t===tab);
  });
  if (tab==='supplier' && !document.getElementById('sup-editor').value)
    loadSupplierConfig();
}

async function loadSystem() {
  loadConfig();
}

async function loadConfig() {
  const data = await api('/api/config');
  if (!data) return;
  document.getElementById('cfg-editor').value = data.content;
  document.getElementById('cfg-path').textContent = data.path;
  document.getElementById('cfg-result').textContent = '';
}

async function saveConfig() {
  const content = document.getElementById('cfg-editor').value;
  const res = document.getElementById('cfg-result');
  try { JSON.parse(content); } catch(e) {
    res.textContent = '✗ JSON 格式错误: ' + e.message;
    res.className = 'small ms-1 text-danger';
    return;
  }
  try {
    const data = await api('/api/config', {method:'POST', body: JSON.stringify({content})});
    res.textContent = `✓ 已保存（备份: ${data.backup}）`;
    res.className = 'small ms-1 text-success';
  } catch(e) {
    res.textContent = '✗ ' + e.message;
    res.className = 'small ms-1 text-danger';
  }
}

/* ── 供应商配置 ── */
async function loadSupplierConfig() {
  const data = await api('/api/supplier_config');
  if (!data) return;
  document.getElementById('sup-editor').value = data.content;
  document.getElementById('sup-path').textContent = data.path;
  document.getElementById('sup-result').textContent = '';
  renderSupplierCards(data.suppliers);
}

function renderSupplierCards(suppliers) {
  document.getElementById('sup-cards').innerHTML = suppliers.map(s => {
    const modelsHtml = s.models.map(m =>
      `<span class="badge bg-secondary me-1 mb-1" style="font-size:.7rem;">${esc(m)}</span>`
    ).join('');
    const keyMasked = s.api_key.length > 8
      ? s.api_key.slice(0,4) + '****' + s.api_key.slice(-4)
      : '****';
    return `<div class="col-md-6 col-lg-4">
      <div class="card stat-card">
        <div class="card-body p-3">
          <div class="fw-semibold mb-1">🔌 ${esc(s.name)}</div>
          <div class="text-muted small text-truncate mb-1" title="${esc(s.base_url)}">${esc(s.base_url)}</div>
          <div class="small mb-2">
            <span class="text-muted">Key: </span>
            <code class="small">${esc(keyMasked)}</code>
          </div>
          <div class="small text-muted mb-1">模型（${s.models.length}）：</div>
          <div>${modelsHtml}</div>
        </div>
      </div></div>`;
  }).join('');
}

async function saveSupplierConfig() {
  const content = document.getElementById('sup-editor').value;
  const res = document.getElementById('sup-result');
  try { JSON.parse(content); } catch(e) {
    res.textContent = '✗ JSON 格式错误: ' + e.message;
    res.className = 'small ms-1 text-danger';
    return;
  }
  try {
    const data = await api('/api/supplier_config', {method:'POST', body: JSON.stringify({content})});
    res.textContent = `✓ 已保存(备份: ${data.backup})`;
    res.className = 'small ms-1 text-success';
    // 刷新卡片预览
    setTimeout(async () => {
      const refreshed = await api('/api/supplier_config');
      if (refreshed) renderSupplierCards(refreshed.suppliers);
    }, 300);
  } catch(e) {
    res.textContent = '✗ ' + e.message;
    res.className = 'small ms-1 text-danger';
  }
}

async function sysStop() {
  if (!confirm('确认停止 Bot 进程？')) return;
  const res = document.getElementById('sys-result');
  try {
    await api('/api/system/stop', {method:'POST'});
    res.textContent = '正在停止…进程即将退出';
    res.className = 'small text-warning';
  } catch(e) {
    res.textContent = '✗ ' + e.message;
    res.className = 'small text-danger';
  }
}

async function sysRestart() {
  if (!confirm('确认重启 Bot?当前连接将断开，约数秒后重新上线。')) return;
  const res = document.getElementById('sys-result');
  try {
    await api('/api/system/restart', {method:'POST'});
    res.textContent = '正在重启…面板将在新进程启动后恢复';
    res.className = 'small text-info';
  } catch(e) {
    res.textContent = '✗ ' + e.message;
    res.className = 'small text-danger';
  }
}

/* ── 分页渲染 ── */
function renderPage(id, cur, total, loader) {
  const el = document.getElementById(id);
  if (total <= 1) { el.innerHTML=''; return; }
  const s = Math.max(1,cur-2), e = Math.min(total,cur+2);
  let html = '<ul class="pagination pagination-sm mb-0">';
  html += `<li class="page-item ${cur<=1?'disabled':''}"><button class="page-link" onclick="${cur>1?`${loader.name}(${cur-1})`:''}">«</button></li>`;
  for (let i=s;i<=e;i++) {
    html += `<li class="page-item ${i===cur?'active':''}"><button class="page-link" onclick="${loader.name}(${i})">${i}</button></li>`;
  }
  html += `<li class="page-item ${cur>=total?'disabled':''}"><button class="page-link" onclick="${cur<total?`${loader.name}(${cur+1})`:''}">»</button></li>`;
  html += `</ul><span class="text-muted small ms-2 align-self-center">共${total}页</span>`;
  el.innerHTML=html;
}

/* ── HTML 转义 ── */
function esc(s) {
  if (s==null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── 启动时自动尝试登录 ── */
document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('atriToken');
  if (saved) { document.getElementById('token-input').value=saved; login(); }
  document.getElementById('token-input').addEventListener('keydown', e => { if(e.key==='Enter') login(); });
});
</script>
</body>
</html>"""
