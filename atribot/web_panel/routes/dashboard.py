"""仪表盘：运行状态 / 统计概览 / token 图表 / 平台适配器状态"""

import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from atribot.core.service_container import container

from ..deps import _auth, _cfg, _db, _safe_count

router = APIRouter()

_start_time = time.time()


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


@router.get("/api/platforms")
async def api_platforms(_: None = Depends(_auth)) -> Dict[str, Any]:
    try:
        status = _adapter_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"平台管理器不可用: {e}")
    return {"items": [{"name": name, **info} for name, info in status.items()]}
