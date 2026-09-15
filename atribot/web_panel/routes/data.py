"""数据浏览：群列表 / 用户列表 / 消息记录，以及用户权限操作"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from atribot.core.service_container import container

from ..deps import _auth, _cfg, _db

router = APIRouter()


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
