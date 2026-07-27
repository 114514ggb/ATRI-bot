import asyncio
import json
import os
import sys
import time
from datetime import datetime
from logging import Logger
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from atribot.core.command.command_parsing import CommandSystem
from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.service_container import container

router = APIRouter(prefix="/admin", tags=["admin"])
_security = HTTPBearer(auto_error=False)
_start_time = time.time()
db:AsyncPostgreSQL = container.get("database")
cfg:Logger = container.get("config")

def _access_token() -> str:
    return cfg.network.access_token


async def _auth(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> None:
    if creds is None or creds.credentials != _access_token():
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/", response_class=HTMLResponse)
async def panel_index() -> HTMLResponse:
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(html_content)

@router.get("/static/style.css", response_class=FileResponse)
async def get_style():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "style.css"), media_type="text/css")

@router.get("/static/script.js", response_class=FileResponse)
async def get_script():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "script.js"), media_type="application/javascript")


@router.get("/api/status")
async def api_status(_: None = Depends(_auth)) -> Dict[str, Any]:
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
    send = container.get("SendMessage")
    payload = {"group_id": body.group_id, "message": body.message}
    result = await send.async_send("send_group_msg", payload)
    return {"status": "ok", "result": result}


@router.get("/api/config")
async def api_get_config(_: None = Depends(_auth)) -> Dict[str, Any]:
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
    subprocess_args = [sys.executable] + sys.argv

    def _do_restart() -> None:
        import subprocess as _sp
        _sp.Popen(subprocess_args, cwd=str(cfg.file_path.project_root))
        os._exit(0)

    loop = asyncio.get_event_loop()
    loop.call_later(0.5, _do_restart)
    return {"status": "restarting"}


