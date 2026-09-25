"""数据库控制台：连接状态 / 表结构 / SQL 执行"""

import asyncio
import logging
import re
import time
from datetime import date, datetime
from datetime import time as dt_time
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..deps import _auth, _cfg, _db

router = APIRouter()

log = logging.getLogger("atri-bot.WebPanelDB")
"""面板 SQL 控制台审计日志（与终端一样可事后追溯；atri-bot.* 前缀会进面板日志流）"""

_DB_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DB_QUERY_MAX_ROWS = 500
_DB_QUERY_TIMEOUT = 30  # 秒
_DB_READ_VERBS = {"select", "show", "explain", "values", "table", "with"}

_DB_WRITE_HINTS = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|comment|copy|vacuum|reindex|refresh|call|do|merge|lock)\b",
    re.IGNORECASE,
)


def _db_console_readonly() -> bool:
    """web_panel.db_console_readonly（默认 false）：SQL 控制台是否只允许查询语句"""
    try:
        return bool((_cfg()._raw_config.get("web_panel") or {}).get("db_console_readonly"))
    except Exception:
        return False


def _audit(client_ip: str, sql: str, result: str, duration_ms: int) -> None:
    """记录一条 SQL 审计（单行化 + 截断，避免日志注入与刷屏）"""
    one_line = " ".join(sql.split())
    snippet = one_line if len(one_line) <= 300 else one_line[:300] + "…"
    log.info("面板执行 SQL（%s，%dms，%s）：%s", client_ip, duration_ms, result, snippet)


def _db_json_safe(v: Any) -> Any:
    """把 asyncpg 解码出的 PG 值转成 JSON 可序列化形态，超长文本截断"""
    if isinstance(v, (datetime, date, dt_time)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return f"<二进制 {len(bytes(v))} 字节>"
    if isinstance(v, str) and len(v) > 600:
        return v[:600] + f"…[已截断，共 {len(v)} 字符]"
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


def _db_conn_info() -> Dict[str, Any]:
    """数据库连接信息（不含密码），仅供面板展示"""
    try:
        raw = _cfg()._raw_config.get("database") or {}
        return {"host": raw.get("host"), "port": raw.get("port"), "user": raw.get("user")}
    except Exception:
        return {}


@router.get("/api/db/status")
async def api_db_status(_: None = Depends(_auth)) -> Dict[str, Any]:
    try:
        db = _db()
    except Exception as e:
        return {"available": False, "reason": f"数据库服务未注册（bot 未启动？）：{e}"}

    pool = getattr(db, "_pool", None)
    pool_info = None
    if pool is not None:
        try:
            pool_info = {"size": pool.get_size(), "idle": pool.get_idle_size()}
        except Exception:
            pool_info = None

    try:
        rows = await db.execute_SQL(
            """
            SELECT version() AS version,
                   current_database() AS db_name,
                   pg_size_pretty(pg_database_size(current_database())) AS db_size,
                   now() - pg_postmaster_start_time() AS uptime,
                   (SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()) AS connections
            """
        )
        r = dict(rows[0]) if rows else {}
    except Exception as e:
        return {"available": False, "reason": str(e), **_db_conn_info()}

    return {
        "available": True,
        "version": r.get("version"),
        "db_name": r.get("db_name"),
        "db_size": str(r.get("db_size") or ""),
        "uptime": str(r.get("uptime") or ""),
        "connections": r.get("connections"),
        "pool": pool_info,
        **_db_conn_info(),
    }


@router.get("/api/db/tables")
async def api_db_tables(_: None = Depends(_auth)) -> Dict[str, Any]:
    try:
        rows = await _db().execute_SQL(
            """
            SELECT c.relname AS table_name,
                   c.reltuples::bigint AS row_estimate,
                   pg_total_relation_size(c.oid) AS size_bytes,
                   pg_size_pretty(pg_total_relation_size(c.oid)) AS size_pretty,
                   (SELECT COUNT(*) FROM pg_attribute a
                    WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped) AS column_count,
                   obj_description(c.oid, 'pg_class') AS comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY pg_total_relation_size(c.oid) DESC
            """
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"数据库不可用: {e}")
    return {"tables": [dict(r) for r in rows]}


@router.get("/api/db/table")
async def api_db_table(name: str, _: None = Depends(_auth)) -> Dict[str, Any]:
    if not _DB_TABLE_NAME_RE.match(name or ""):
        raise HTTPException(status_code=400, detail="非法表名")
    db = _db()
    try:
        columns = await db.execute_SQL(
            """
            SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
            """,
            (name,),
        )
        indexes = await db.execute_SQL(
            """
            SELECT indexname, indexdef FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = $1
            ORDER BY indexname
            """,
            (name,),
        )
        constraints = await db.execute_SQL(
            """
            SELECT con.conname AS name, con.contype AS type, pg_get_constraintdef(con.oid) AS def
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = $1
            ORDER BY con.contype, con.conname
            """,
            (name,),
        )
        count_rows = await db.execute_SQL(f'SELECT COUNT(*) AS c FROM "{name}"')
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"数据库不可用: {e}")
    return {
        "name": name,
        "row_count": count_rows[0]["c"] if count_rows else 0,
        "columns": [dict(r) for r in columns],
        "indexes": [dict(r) for r in indexes],
        "constraints": [dict(r) for r in constraints],
    }


class DbQueryBody(BaseModel):
    sql: str


@router.post("/api/db/query")
async def api_db_query(body: DbQueryBody, request: Request, _: None = Depends(_auth)) -> Dict[str, Any]:
    sql = body.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL 不能为空")
    if len(sql) > 100_000:
        raise HTTPException(status_code=400, detail="SQL 过长（上限 100000 字符）")

    cleaned = re.sub(r"--[^\n]*", " ", sql).strip()
    while cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    first_word = (cleaned.split(None, 1) or [""])[0].lower()
    # fetch 路径：返回结果集的语句；含 RETURNING 的写语句同样有结果集
    fetchable = first_word in _DB_READ_VERBS or "returning" in cleaned.lower()
    # asyncpg 的 fetch 不支持多语句，提前拒绝避免歧义报错
    if fetchable and ";" in cleaned:
        raise HTTPException(status_code=400, detail="返回结果集的语句一次只能执行一条，多条请分开运行")

    if _db_console_readonly() and (first_word not in _DB_READ_VERBS or _DB_WRITE_HINTS.search(cleaned)):
        # 只读模式：仅放行查询语句（字面量里出现写关键词会误拦，属保守取舍）；
        # _DB_WRITE_HINTS 已覆盖 INSERT/UPDATE/DELETE/MERGE，无需再单独匹配 RETURNING
        raise HTTPException(
            status_code=403,
            detail="数据库控制台已开启只读模式（web_panel.db_console_readonly），仅允许查询语句",
        )

    client_ip = request.client.host if request.client else "?"

    try:
        db = _db()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"数据库服务未注册: {e}")

    started = time.monotonic()
    status: Optional[str] = None
    records = None
    try:
        pool = getattr(db, "_pool", None)
        if pool is not None:
            async with pool.acquire() as conn:
                if fetchable:
                    records = await conn.fetch(sql, timeout=_DB_QUERY_TIMEOUT)
                else:
                    status = await conn.execute(sql, timeout=_DB_QUERY_TIMEOUT)
        elif fetchable:
            # dev mock：无连接池时退回 execute_SQL
            records = await db.execute_SQL(sql)
        else:
            await db.execute_SQL(sql)
            status = "(dev mock) OK"
    except asyncio.TimeoutError:
        _audit(client_ip, sql, "超时", round((time.monotonic() - started) * 1000))
        return {"ok": False, "error": f"执行超时（上限 {_DB_QUERY_TIMEOUT} 秒）"}
    except Exception as e:
        _audit(client_ip, sql, "失败", round((time.monotonic() - started) * 1000))
        return {"ok": False, "error": str(e).strip() or type(e).__name__}
    duration_ms = round((time.monotonic() - started) * 1000)
    _audit(client_ip, sql, "成功", duration_ms)

    if not fetchable:
        return {"ok": True, "kind": "status", "status": status, "duration_ms": duration_ms}

    columns = list(records[0].keys()) if records else []
    truncated = len(records) > _DB_QUERY_MAX_ROWS
    rows = [{k: _db_json_safe(rec[k]) for k in columns} for rec in records[:_DB_QUERY_MAX_ROWS]]
    return {
        "ok": True,
        "kind": "rows",
        "columns": columns,
        "rows": rows,
        "row_count": len(records),
        "truncated": truncated,
        "duration_ms": duration_ms,
    }
