"""配置管理：主配置 / 供应商配置 / MCP 配置的读写与回滚"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import _auth, _cfg, _read_config_text, _save_config_file

router = APIRouter()

log = logging.getLogger("atri-bot.WebPanelConfig")

_VALID_CONN_TYPES = {"WebSocket_client", "WebSocket_server", "http"}

_TOOL_SEARCH_NAME = "tool_search"


def _name_list(key: str, group: str, raw: Any, errors: List[str]) -> List[str]:
    """取某个分组的工具名列表：缺省视为空列表，非字符串数组则记错并返回空列表"""
    if raw is None:
        return []
    if isinstance(raw, list) and all(isinstance(name, str) for name in raw):
        return raw
    errors.append(f"tool_presets.{key}.{group} 必须是字符串数组")
    return []


def _validate_tool_presets(data: dict) -> List[str]:
    """校验 tool_presets：每项须为 null / 字符串数组 / {default,deferred}，且 tool_search 与 deferred 成对

    与前端 components/tool-preset-editor.js 的 validatePresetPairing 规则一致，
    兜住源码模式手改、聊天页保存等多条写入路径。
    """
    presets = data.get("tool_presets")
    if presets is None:
        return []
    if not isinstance(presets, dict):
        return ["tool_presets 必须是对象"]

    errors: List[str] = []
    for key, value in presets.items():
        if value is None:  # null = 不限制（全部工具）
            continue
        if isinstance(value, list):  # 单列表 = 只有默认组
            value = {"default": value}
        elif not isinstance(value, dict):
            errors.append(f"tool_presets.{key} 必须是 null、字符串数组或 {{default, deferred}} 对象")
            continue

        unknown = [group for group in value if group not in ("default", "deferred")]
        if unknown:
            errors.append(f"tool_presets.{key} 含未知分组: {', '.join(sorted(unknown))}")
        default = _name_list(key, "default", value.get("default"), errors)
        deferred = _name_list(key, "deferred", value.get("deferred"), errors)
        if _TOOL_SEARCH_NAME in default and not deferred:
            errors.append(f"tool_presets.{key}：default 含 tool_search 但 deferred 为空，没有可发现的内容")
        elif _TOOL_SEARCH_NAME not in default and deferred:
            errors.append(f"tool_presets.{key}：配置了 deferred 但 default 缺少 tool_search，这些工具无法被模型发现")
    return errors


def _reload_tool_presets() -> bool:
    """把刚写盘的工具预设同步到运行中的 ToolCalls 与 atriConfig（面板与 bot 同进程）

    不热重载的话会出现「配置页改了预设 → 聊天页仍旧值 → 聊天页保存又把改动覆盖」，
    或「聊天页保存 → 点刷新工具 → 预设回退」（reload_local_tools 从 atriConfig 重读）。
    独立面板/开发模式下没有 ToolCalls 服务，静默跳过。
    """
    from atribot.core.service_container import container

    if not container.exists("ToolCalls"):
        return False
    try:
        presets = _cfg().reload_section("tool_presets") or {}
        container.get("ToolCalls").load_presets_from_config(presets)
    except Exception as exc:  # 热重载失败不应影响保存结果
        log.warning("工具预设热重载失败（配置已写入磁盘，重启后生效）: %s", exc)
        return False
    return True


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

    errors.extend(_validate_tool_presets(data))

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
    presets_reloaded = _reload_tool_presets()  # 工具预设立即生效，其余配置段仍需重启
    return {"status": "ok", "needs_restart": True, "backup": backup, "presets_reloaded": presets_reloaded}


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
    presets_reloaded = _reload_tool_presets() if body.target == "config" else False
    return {
        "status": "ok",
        "restored_from": str(backup),
        "needs_restart": True,
        "presets_reloaded": presets_reloaded,
    }
