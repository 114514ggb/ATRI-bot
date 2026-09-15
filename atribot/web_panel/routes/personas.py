"""人设管理：列表 / 读取 / 保存 / 新建 / 删除 / 切换默认"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import _auth, _backup_file, _cfg, _chat_manager, _write_json

router = APIRouter()

_PERSONA_KEY_RE = re.compile(r"^[\w\u4e00-\u9fff\-. ]+$")


def _persona_folder() -> Path:
    return Path(_cfg().file_path.chat_manager)


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
