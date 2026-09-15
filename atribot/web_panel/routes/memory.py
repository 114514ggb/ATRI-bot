"""长期记忆：列表浏览 / 单条与批量删除 / 字段修改"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import _auth, _db

router = APIRouter()

MEMORY_CATEGORIES = [
    "preference", "fact", "experience", "emotion",
    "group_topic", "knowledge", "domain", "guideline",
]


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
