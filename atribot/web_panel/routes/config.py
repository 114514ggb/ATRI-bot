"""配置管理：主配置 / 供应商配置 / MCP 配置的读写与回滚"""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import _auth, _cfg, _read_config_text, _save_config_file

router = APIRouter()

_VALID_CONN_TYPES = {"WebSocket_client", "WebSocket_server", "http"}


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
