"""ATRI Web 管理面板后端路由

所有服务依赖均为惰性获取（请求内从 DI 容器解析），
使面板可以在不完整的运行环境中安全导入与独立调试。
"""

import asyncio
import json
import logging
import os
import re
import shutil
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from atribot.core.service_container import container

router = APIRouter(prefix="/admin", tags=["admin"])
_security = HTTPBearer(auto_error=False)
_start_time = time.time()

MEMORY_CATEGORIES = [
    "preference", "fact", "experience", "emotion",
    "group_topic", "knowledge", "domain", "guideline",
]

_VALID_CONN_TYPES = {"WebSocket_client", "WebSocket_server", "http"}


_LOG_BUFFER_MAX = 500
_log_buffer: deque = deque(maxlen=_LOG_BUFFER_MAX)
_log_seq = 0
_log_buffer_lock = Lock()


# 第三方库的 DEBUG/INFO 帧/心跳日志（websockets 的 > TEXT / PING / PONG 等）过于嘈杂，
# 面板日志流对这类来源只收录 WARNING 及以上；自家日志（atri-bot.* 等）不受影响
_NOISY_LOGGERS = ("websockets.", "asyncio", "httpx.", "httpcore.", "urllib3", "aiohttp.")


class _PanelLogHandler(logging.Handler):
    """将日志记录追加进环形缓冲，供 WebSocket 日志流消费"""

    def emit(self, record: logging.LogRecord) -> None:
        global _log_seq
        try:
            if record.levelno < logging.WARNING and record.name.startswith(_NOISY_LOGGERS):
                return
            now = datetime.now()
            _log_seq += 1
            _log_buffer.append(
                {
                    "seq": _log_seq,
                    "time": f"{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}",
                    "level": record.levelname,
                    "name": record.name,
                    "message": record.getMessage(),
                }
            )
        except Exception:
            pass


def _ensure_log_handler() -> None:
    root = logging.getLogger()
    if any(isinstance(h, _PanelLogHandler) for h in root.handlers):
        return
    # DEBUG 级别：面板日志流需要展示 atri-bot.* 的 DEBUG 输出
    root.addHandler(_PanelLogHandler(level=logging.DEBUG))
    if root.level == logging.NOTSET or root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)



def _cfg():
    return container.get("config")


def _db():
    return container.get("database")


def _access_token() -> Optional[str]:
    """面板访问令牌:web_panel.access_token > 环境变量 ATRI_PANEL_TOKEN > 第一个平台的 access_token"""
    try:
        cfg = _cfg()
        raw = cfg._raw_config
    except Exception:
        return os.environ.get("ATRI_PANEL_TOKEN") or None
    token = (raw.get("web_panel") or {}).get("access_token") or os.environ.get("ATRI_PANEL_TOKEN")
    if not token:
        for platform in (raw.get("platforms") or {}).values():
            if isinstance(platform, dict) and platform.get("access_token"):
                token = platform["access_token"]
                break
    return token or None


async def _auth(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> None:
    token = _access_token()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="未配置访问令牌：请在 config.json 添加 web_panel.access_token 或设置环境变量 ATRI_PANEL_TOKEN",
        )
    if creds is None or creds.credentials != token:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _chat_manager():
    """获取 ChatManager（可能未启动，如独立调试时）"""
    from atribot.core.cache.management_chat_example import ChatManager

    try:
        return container.get_by_type(ChatManager)
    except Exception:
        return None


def _persona_folder() -> Path:
    return Path(str(_cfg().file_path.chat_manager))


def _backup_file(path) -> Path:
    path = Path(path)
    backup = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        shutil.copy2(path, backup)
    return backup


def _write_json(path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def _read_config_text(path) -> tuple:
    """读取配置文件：合法则返回规范化文本，否则原样返回并标记 invalid"""
    raw = path.read_text(encoding="utf-8")
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2), True
    except (json.JSONDecodeError, ValueError):
        return raw, False


def _save_config_file(path, content: str, validate=None) -> str:
    """解析 + 校验 + 备份 + 写入，返回备份路径"""
    parsed = _parse_json_or_400(content)
    if validate:
        validate(parsed)
    backup = _backup_file(path)
    _write_json(path, parsed)
    return str(backup)


def _parse_json_or_400(content: str) -> dict:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON 格式错误: 第 {e.lineno} 行第 {e.colno} 列 - {e.msg}")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="配置根节点必须是 JSON 对象 {{...}}")
    return parsed


def _validate_main_config(data: dict) -> None:
    errors: List[str] = []

    platforms = data.get("platforms")
    if not isinstance(platforms, dict) or not platforms:
        errors.append("platforms 必须是非空对象")
    else:
        for key, platform in platforms.items():
            if not isinstance(platform, dict):
                errors.append(f"platforms.{key} 必须是对象")
                continue
            conn = platform.get("connection_type")
            if conn not in _VALID_CONN_TYPES:
                errors.append(
                    f"platforms.{key}.connection_type 必须是 {'/'.join(sorted(_VALID_CONN_TYPES))} 之一"
                )
            if not platform.get("access_token"):
                errors.append(f"platforms.{key}.access_token 不能为空")

    account = data.get("account")
    if not isinstance(account, dict) or "id" not in account:
        errors.append("account.id（bot 的 QQ 号）不能为空")
    if not isinstance(data.get("root_user_id"), int):
        errors.append("root_user_id 必须是整数（root 用户 QQ 号）")

    database = data.get("database")
    if not isinstance(database, dict):
        errors.append("database 必须是对象")
    else:
        for field in ("host", "port", "user", "password"):
            if field not in database:
                errors.append(f"database.{field} 不能为空")

    if errors:
        raise HTTPException(status_code=400, detail="；".join(errors))


def _validate_supplier_config(data: dict) -> None:
    api = data.get("api")
    if not isinstance(api, list) or not api:
        raise HTTPException(status_code=400, detail="api 必须是非空数组，至少包含一个供应商")
    for i, supplier in enumerate(api):
        if not isinstance(supplier, dict):
            raise HTTPException(status_code=400, detail=f"api[{i}] 必须是对象")
        if not supplier.get("name"):
            raise HTTPException(status_code=400, detail=f"api[{i}].name 不能为空")
        if not supplier.get("base_url"):
            raise HTTPException(status_code=400, detail=f"api[{i}].base_url 不能为空")
        if not supplier.get("api_key"):
            raise HTTPException(status_code=400, detail=f"api[{i}].api_key 不能为空")


def mount_static(app) -> None:
    """将面板静态资源目录挂载到 FastAPI 应用（/admin/static）"""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/admin/static", StaticFiles(directory=static_dir), name="admin_static")


async def _safe_count(sql: str, args: tuple = ()) -> int:
    try:
        rows = await _db().execute_SQL(sql, args)
        return rows[0]["c"] if rows else 0
    except Exception:
        return 0


@router.get("/", response_class=HTMLResponse)
async def panel_index() -> HTMLResponse:
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


def _adapter_status() -> Dict[str, Any]:
    """从 PlatformManager 读取各适配器的实时状态（独立调试等场景下不可用则抛异常）"""
    from atribot.core.platform.manager import PlatformManager

    pm = container.get_by_type(PlatformManager)
    status = {}
    for name, adapter in pm.adapters.items():
        connection = getattr(adapter, "_connection", None)
        status[name] = {
            "type": getattr(adapter, "source_name", name),
            "is_started": bool(getattr(adapter, "is_started", False)),
            "is_connected": bool(getattr(connection, "is_connected", False)) if connection else False,
        }
    return status


@router.get("/api/status")
async def api_status(_: None = Depends(_auth)) -> Dict[str, Any]:
    raw = _cfg()._raw_config
    platforms: Dict[str, Any] = {}
    conn_types = set()
    try:
        platforms = _adapter_status()
    except Exception:
        for name, platform in (raw.get("platforms") or {}).items():
            if isinstance(platform, dict):
                platforms[name] = {"type": platform.get("connection_type", "?"), "is_started": False, "is_connected": False}

    for platform in (raw.get("platforms") or {}).values():
        if isinstance(platform, dict) and platform.get("connection_type"):
            conn_types.add(platform["connection_type"])

    account = raw.get("account") or {}
    connect = (raw.get("model") or {}).get("connect") or {}
    uptime = int(time.time() - _start_time)
    h, r = divmod(uptime, 3600)
    m, s = divmod(r, 60)
    return {
        "account_id": account.get("id"),
        "account_name": account.get("name"),
        "model": connect.get("model_name"),
        "supplier": connect.get("supplier"),
        "connection_type": sorted(conn_types),
        "uptime": f"{h:02d}:{m:02d}:{s:02d}",
        "platforms": platforms,
        "sandbox": container.exists("SandBox"),
        "mcp": container.exists("MCP"),
        "rag": bool(((raw.get("model") or {}).get("RAG") or {}).get("enable")),
    }


@router.get("/api/stats")
async def api_stats(_: None = Depends(_auth)) -> Dict[str, Any]:
    groups = await _safe_count("SELECT COUNT(*) AS c FROM user_group")
    users = await _safe_count("SELECT COUNT(*) AS c FROM users")
    messages = await _safe_count("SELECT COUNT(*) AS c FROM message")
    memories = await _safe_count("SELECT COUNT(*) AS c FROM atri_memory")
    today_messages = await _safe_count(
        "SELECT COUNT(*) AS c FROM message WHERE time >= EXTRACT(EPOCH FROM CURRENT_DATE)"
    )
    active_contexts = await _safe_count(
        "SELECT COUNT(*) AS c FROM chat_context WHERE last_updated >= NOW() - interval '24 hours'"
    )
    today_tokens = await _safe_count(
        "SELECT COALESCE(SUM(total_tokens), 0) AS c FROM token_statistics WHERE created_at >= CURRENT_DATE"
    )
    return {
        "groups": groups,
        "users": users,
        "messages": messages,
        "memories": memories,
        "today_messages": today_messages,
        "today_tokens": today_tokens,
        "active_contexts": active_contexts,
    }


@router.get("/api/stats/tokens")
async def api_stats_tokens(days: int = 7, _: None = Depends(_auth)) -> Dict[str, Any]:
    days = max(1, min(days, 30))
    try:
        rows = await _db().execute_SQL(
            """
            SELECT to_char(DATE(created_at), 'MM-DD') AS date,
                   COALESCE(SUM(total_tokens), 0) AS total
            FROM token_statistics
            WHERE created_at >= CURRENT_DATE - $1 * interval '1 day'
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
            """,
            (days,),
        )
        items = [{"date": r["date"], "total": r["total"]} for r in rows]
    except Exception:
        items = []
    return {"items": items}


@router.get("/api/groups")
async def api_groups(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = (max(1, page) - 1) * limit

    conds, vals = [], []
    if search:
        conds.append("(CAST(group_id AS TEXT) LIKE $1 OR group_name LIKE $1)")
        vals.append(f"%{search}%")
    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    rows = await _db().execute_SQL(
        f"SELECT group_id, group_name FROM user_group {where} ORDER BY group_id LIMIT ${len(vals) + 1} OFFSET ${len(vals) + 2}",
        (*vals, limit, offset),
    )
    total_rows = await _db().execute_SQL(f"SELECT COUNT(*) AS c FROM user_group {where}", tuple(vals) or None)
    total = total_rows[0]["c"] if total_rows else 0
    return {"total": total, "page": page, "limit": limit, "items": [dict(r) for r in rows]}


@router.get("/api/users")
async def api_users(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = (max(1, page) - 1) * limit

    conds, vals = [], []
    if search:
        conds.append("(CAST(u.user_id AS TEXT) LIKE $1 OR u.nickname LIKE $1)")
        vals.append(f"%{search}%")
    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    rows = await _db().execute_SQL(
        f"""
        SELECT u.user_id, u.nickname,
               to_char(u.last_updated, 'YYYY-MM-DD HH24:MI:SS') AS last_updated,
               p.permission_type
        FROM users u
        LEFT JOIN permissions p ON u.user_id = p.user_id
        {where}
        ORDER BY u.last_updated DESC NULLS LAST
        LIMIT ${len(vals) + 1} OFFSET ${len(vals) + 2}
        """,
        (*vals, limit, offset),
    )
    total_rows = await _db().execute_SQL(
        f"SELECT COUNT(*) AS c FROM users u {where}", tuple(vals) or None
    )
    total = total_rows[0]["c"] if total_rows else 0

    try:
        root_id = int(_cfg()._raw_config.get("root_user_id"))
    except Exception:
        root_id = None
    items = []
    for r in rows:
        d = dict(r)
        d["is_root"] = d.get("user_id") == root_id
        items.append(d)
    return {"total": total, "page": page, "limit": limit, "items": items}


@router.get("/api/messages")
async def api_messages(
    page: int = 1,
    limit: int = 50,
    group_id: Optional[int] = None,
    user_id: Optional[int] = None,
    search: Optional[str] = None,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = (max(1, page) - 1) * limit

    conds: List[str] = []
    vals: List[Any] = []
    if group_id is not None:
        vals.append(group_id)
        conds.append(f"m.group_id = ${len(vals)}")
    if user_id is not None:
        vals.append(user_id)
        conds.append(f"m.user_id = ${len(vals)}")
    if search:
        vals.append(f"%{search}%")
        conds.append(f"m.message_content LIKE ${len(vals)}")
    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    rows = await _db().execute_SQL(
        f"""
        SELECT m.sole_id, m.message_id, m.user_id, m.group_id,
               m.time, m.message_content, u.nickname
        FROM message m
        LEFT JOIN users u ON m.user_id = u.user_id
        {where}
        ORDER BY m.sole_id DESC
        LIMIT ${len(vals) + 1} OFFSET ${len(vals) + 2}
        """,
        (*vals, limit, offset),
    )
    total_rows = await _db().execute_SQL(
        f"SELECT COUNT(*) AS c FROM message m {where}", tuple(vals) or None
    )
    total = total_rows[0]["c"] if total_rows else 0

    items = []
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
    search: Optional[str] = None,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    offset = (max(1, page) - 1) * limit

    conds: List[str] = []
    vals: List[Any] = []
    if category and category in MEMORY_CATEGORIES:
        vals.append(category)
        conds.append(f"category = ${len(vals)}::memory_category")
    if user_id is not None:
        vals.append(user_id)
        conds.append(f"user_id = ${len(vals)}")
    if search:
        vals.append(f"%{search}%")
        conds.append(f"event LIKE ${len(vals)}")
    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    rows = await _db().execute_SQL(
        f"""
        SELECT memory_id, user_id, group_id, event_time, event,
               category, importance, credibility, access_count
        FROM atri_memory
        {where}
        ORDER BY memory_id DESC
        LIMIT ${len(vals) + 1} OFFSET ${len(vals) + 2}
        """,
        (*vals, limit, offset),
    )
    total_rows = await _db().execute_SQL(
        f"SELECT COUNT(*) AS c FROM atri_memory {where}", tuple(vals) or None
    )
    total = total_rows[0]["c"] if total_rows else 0

    items = []
    for r in rows:
        d = dict(r)
        if d.get("event_time"):
            d["event_time_str"] = datetime.fromtimestamp(d["event_time"]).strftime("%Y-%m-%d %H:%M:%S")
        d["category"] = str(d["category"]) if d.get("category") else ""
        items.append(d)
    return {"total": total, "page": page, "limit": limit, "items": items}


@router.get("/api/commands")
async def api_commands(_: None = Depends(_auth)) -> List[Dict[str, Any]]:
    from atribot.core.command.command_parsing import CommandSystem

    cmd: CommandSystem = container.get_by_type(CommandSystem)
    result: List[Dict[str, Any]] = []
    for name, c in cmd.command_registry.items():
        params = [
            {
                "name": p.name,
                "type": p.param_type.value,
                "data_type": getattr(p.type, "__name__", str(p.type)),
                "description": p.description,
                "required": p.required,
                "default": str(p.default) if p.default is not None else None,
                "short_option": p.short_option,
                "long_option": p.long_option,
                "choices": p.choices,
                "metavar": p.metavar,
                "multiple": p.multiple,
            }
            for p in c.params.values()
        ]
        result.append(
            {
                "name": name,
                "description": c.description,
                "aliases": c.aliases,
                "authority_level": c.authority_level,
                "cooldown": c.cooldown,
                "usage": c.get_usage_string(),
                "examples": c.examples,
                "params": params,
            }
        )
    return sorted(result, key=lambda x: x["name"])


@router.get("/api/platforms")
async def api_platforms(_: None = Depends(_auth)) -> Dict[str, Any]:
    try:
        status = _adapter_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"平台管理器不可用: {e}")
    return {"items": [{"name": name, **info} for name, info in status.items()]}



class PermissionBody(BaseModel):
    action: str  # promote / demote / blacklist / unblacklist


@router.put("/api/users/{user_id}/permission")
async def api_user_permission(
    user_id: int,
    body: PermissionBody,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    from atribot.core.command.async_permissions_management import PermissionsManagement

    pm: PermissionsManagement = container.get_by_type(PermissionsManagement)
    operator = _cfg()._raw_config.get("root_user_id")
    try:
        if body.action == "promote":
            await pm.add_administrator(user_id, operator)
        elif body.action == "demote":
            await pm.delete_administrator(user_id, operator)
        elif body.action == "blacklist":
            await pm.add_to_blacklist(user_id, operator)
        elif body.action == "unblacklist":
            await pm.remove_from_blacklist(user_id, operator)
        else:
            raise HTTPException(status_code=400, detail=f"未知操作: {body.action}")
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "role": pm.get_my_permission(user_id)}


@router.delete("/api/memory/{memory_id}")
async def api_memory_delete(memory_id: int, _: None = Depends(_auth)) -> Dict[str, Any]:
    from atribot.LLMchat.RAG.vector_store import MemoryVectorStore

    try:
        ok = await MemoryVectorStore().delete_memory(memory_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"记忆服务不可用: {e}")
    if not ok:
        raise HTTPException(status_code=404, detail=f"记忆 {memory_id} 不存在")
    return {"status": "ok"}


class BatchDeleteBody(BaseModel):
    ids: List[int]


@router.post("/api/memory/batch_delete")
async def api_memory_batch_delete(body: BatchDeleteBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    from atribot.LLMchat.RAG.vector_store import MemoryVectorStore

    try:
        count = await MemoryVectorStore().batch_delete_memories(body.ids)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"记忆服务不可用: {e}")
    return {"status": "ok", "deleted": count}


class MemoryUpdateBody(BaseModel):
    event: Optional[str] = None
    category: Optional[str] = None
    importance: Optional[int] = None
    credibility: Optional[int] = None


@router.put("/api/memory/{memory_id}")
async def api_memory_update(
    memory_id: int,
    body: MemoryUpdateBody,
    _: None = Depends(_auth),
) -> Dict[str, Any]:
    from atribot.LLMchat.RAG.vector_store import MemoryVectorStore

    if body.category is not None and body.category not in MEMORY_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category 必须是: {', '.join(MEMORY_CATEGORIES)}")
    try:
        ok = await MemoryVectorStore().update_memory(
            memory_id,
            event=body.event,
            category=body.category,
            importance=body.importance,
            credibility=body.credibility,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"记忆服务不可用: {e}")
    if not ok:
        raise HTTPException(status_code=404, detail=f"记忆 {memory_id} 不存在")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 配置：主配置 / 供应商 / MCP
# ---------------------------------------------------------------------------

@router.get("/api/config")
async def api_get_config(_: None = Depends(_auth)) -> Dict[str, Any]:
    path = _cfg().config_file_path
    content, valid = _read_config_text(path)
    return {"content": content, "path": str(path), "valid": valid}


class ConfigBody(BaseModel):
    content: str


@router.post("/api/config")
async def api_save_config(body: ConfigBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    backup = _save_config_file(_cfg().config_file_path, body.content, _validate_main_config)
    return {"status": "ok", "needs_restart": True, "backup": backup}


@router.get("/api/supplier_config")
async def api_get_supplier_config(_: None = Depends(_auth)) -> Dict[str, Any]:
    path = _cfg().file_path.supplier_config_path
    content, valid = _read_config_text(path)
    data = json.loads(content) if valid else {}

    suppliers = []
    for item in (data.get("api") or []):
        if not isinstance(item, dict):
            continue
        models = {}
        for model_name, model_cfg in (item.get("models") or {}).items():
            models[model_name] = {
                "visual_sense": bool((model_cfg or {}).get("visual_sense")),
                "audio_sense": bool((model_cfg or {}).get("audio_sense")),
                "video_sense": bool((model_cfg or {}).get("video_sense")),
                "document_sense": bool((model_cfg or {}).get("document_sense")),
            }
        suppliers.append(
            {
                "name": item.get("name", ""),
                "base_url": item.get("base_url", ""),
                "models": models,
            }
        )
    return {"content": content, "path": str(path), "valid": valid, "suppliers": suppliers}


@router.post("/api/supplier_config")
async def api_save_supplier_config(body: ConfigBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    backup = _save_config_file(_cfg().file_path.supplier_config_path, body.content, _validate_supplier_config)
    return {"status": "ok", "needs_restart": True, "backup": backup}


@router.get("/api/mcp_config")
async def api_get_mcp_config(_: None = Depends(_auth)) -> Dict[str, Any]:
    path = _cfg().file_path.mcp_config
    if not path.exists():
        return {"content": "{\n    \"mcpServers\": {}\n}\n", "path": str(path), "valid": True, "exists": False}
    content, valid = _read_config_text(path)
    return {"content": content, "path": str(path), "valid": valid, "exists": True}


@router.post("/api/mcp_config")
async def api_save_mcp_config(body: ConfigBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    backup = _save_config_file(_cfg().file_path.mcp_config, body.content)
    return {"status": "ok", "needs_restart": True, "backup": backup}


class RollbackBody(BaseModel):
    target: str  # config / supplier / mcp


@router.post("/api/config/rollback")
async def api_config_rollback(body: RollbackBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    cfg = _cfg()
    targets = {
        "config": Path(cfg.config_file_path),
        "supplier": Path(cfg.file_path.supplier_config_path),
        "mcp": Path(cfg.file_path.mcp_config),
    }
    if body.target not in targets:
        raise HTTPException(status_code=400, detail="target 必须是 config / supplier / mcp")

    path = targets[body.target]
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        raise HTTPException(status_code=404, detail=f"备份文件不存在: {backup}")

    # 先取出当前内容，恢复备份后再把它写回 .bak，
    # 使 rollback 成为"当前 ↔ 备份"的切换，可以再次回滚撤销
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    shutil.copy2(backup, path)
    if previous is not None:
        backup.write_text(previous, encoding="utf-8")
    return {"status": "ok", "restored_from": str(backup), "needs_restart": True}


_PERSONA_KEY_RE = re.compile(r"^[\w\u4e00-\u9fff\-. ]+$")


def _persona_path(key: str) -> Path:
    if not key or not _PERSONA_KEY_RE.match(key) or key.startswith("."):
        raise HTTPException(status_code=400, detail="人设名只能包含中文、字母、数字、-_. 和空格")
    folder = _persona_folder().resolve()
    path = (folder / f"{key}.txt").resolve()
    if not str(path).startswith(str(folder)):
        raise HTTPException(status_code=400, detail="非法的人设名")
    return path


def _default_persona() -> str:
    return ((_cfg()._raw_config.get("ai_chat") or {}).get("playRole")) or "none"


def _refresh_personas() -> None:
    """热刷新内存中的人设列表（ChatManager 未启动时跳过）"""
    manager = _chat_manager()
    if manager:
        manager.anew_character_settings()


@router.get("/api/personas")
async def api_personas(_: None = Depends(_auth)) -> Dict[str, Any]:
    folder = _persona_folder()
    default_role = _default_persona()

    items = []
    if folder.exists():
        for file in sorted(folder.glob("*.txt")):
            key = file.stem
            try:
                stat = file.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                mtime = ""
            items.append(
                {
                    "key": key,
                    "size": stat.st_size if mtime else 0,
                    "mtime": mtime,
                    "is_default": key == default_role,
                }
            )
    return {"items": items, "default": default_role}


@router.get("/api/personas/{key}")
async def api_persona_get(key: str, _: None = Depends(_auth)) -> Dict[str, Any]:
    path = _persona_path(key)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"人设 {key} 不存在")
    return {"key": key, "content": path.read_text(encoding="utf-8")}


class PersonaContentBody(BaseModel):
    content: str


@router.put("/api/personas/{key}")
async def api_persona_save(key: str, body: PersonaContentBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    path = _persona_path(key)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"人设 {key} 不存在")
    _backup_file(path)
    path.write_text(body.content, encoding="utf-8")

    _refresh_personas()
    manager = _chat_manager()
    refreshed = bool(manager) and key in manager.play_role_list
    return {"status": "ok", "refreshed": refreshed}


class PersonaCreateBody(BaseModel):
    key: str
    content: str = ""


@router.post("/api/personas")
async def api_persona_create(body: PersonaCreateBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    path = _persona_path(body.key)
    if path.exists():
        raise HTTPException(status_code=400, detail=f"人设 {body.key} 已存在")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    _refresh_personas()
    return {"status": "ok"}


@router.delete("/api/personas/{key}")
async def api_persona_delete(key: str, _: None = Depends(_auth)) -> Dict[str, Any]:
    if key == _default_persona():
        raise HTTPException(status_code=400, detail=f"{key} 是当前默认人设，请先切换默认人设再删除")

    path = _persona_path(key)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"人设 {key} 不存在")
    _backup_file(path)
    path.unlink()
    _refresh_personas()
    return {"status": "ok"}


class PersonaDefaultBody(BaseModel):
    key: str


@router.post("/api/personas/default")
async def api_persona_set_default(body: PersonaDefaultBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    path = _persona_path(body.key)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"人设 {body.key} 不存在")

    cfg = _cfg()
    raw = cfg._raw_config
    raw.setdefault("ai_chat", {})["playRole"] = body.key

    config_path = cfg.config_file_path
    _backup_file(config_path)
    _write_json(config_path, raw)

    manager = _chat_manager()
    if manager:
        manager.default_play_role = body.key
    return {"status": "ok", "default": body.key}


class SendMsgBody(BaseModel):
    group_id: Optional[int] = None
    user_id: Optional[int] = None
    message: str | list
    platform: Optional[str] = None


@router.post("/api/message/send")
async def api_send_message(body: SendMsgBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    from atribot.core.platform.manager import PlatformManager

    if body.group_id is None and body.user_id is None:
        raise HTTPException(status_code=400, detail="必须提供 group_id（群聊）或 user_id（私聊）")

    try:
        pm = container.get_by_type(PlatformManager)
    except Exception:
        return {"status": "error", "result": "平台管理器不可用"}

    adapters = pm.adapters
    if not adapters:
        return {"status": "error", "result": "没有可用适配器"}

    if body.platform and body.platform in adapters:
        adapter = adapters[body.platform]
    else:
        adapter = next(iter(adapters.values()))

    client = adapter.get_client()
    if body.user_id is not None:
        action, payload = "send_private_msg", {"user_id": body.user_id, "message": body.message}
    else:
        action, payload = "send_group_msg", {"group_id": body.group_id, "message": body.message}
    result = await client.async_send(action, payload)
    return {"status": "ok", "result": result}


@router.post("/api/system/stop")
async def api_system_stop(_: None = Depends(_auth)) -> Dict[str, str]:
    loop = asyncio.get_event_loop()
    loop.call_later(0.5, lambda: os._exit(0))
    return {"status": "stopping"}


@router.post("/api/system/restart")
async def api_system_restart(_: None = Depends(_auth)) -> Dict[str, str]:
    subprocess_args = [sys.executable] + sys.argv

    def _do_restart() -> None:
        import subprocess as _sp

        _sp.Popen(subprocess_args, cwd=str(_cfg().file_path.project_root))
        os._exit(0)

    loop = asyncio.get_event_loop()
    loop.call_later(0.5, _do_restart)
    return {"status": "restarting"}


# ---------------------------------------------------------------------------
# WebSocket 实时日志
# ---------------------------------------------------------------------------

@router.websocket("/api/ws/logs")
async def ws_logs(websocket: WebSocket, token: str = "") -> None:
    expected = _access_token()
    if not expected or token != expected:
        await websocket.close(code=4401)
        return

    _ensure_log_handler()
    await websocket.accept()

    with _log_buffer_lock:
        history = list(_log_buffer)
    try:
        if history:
            await websocket.send_json({"type": "history", "items": history})
        last_seq = history[-1]["seq"] if history else 0

        while True:
            await asyncio.sleep(0.25)
            with _log_buffer_lock:
                pending = [item for item in _log_buffer if item["seq"] > last_seq]
            if pending:
                last_seq = pending[-1]["seq"]
                await websocket.send_json({"type": "logs", "items": pending})
    except Exception:
        return
