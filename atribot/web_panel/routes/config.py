"""配置管理：主配置 / 供应商配置 / MCP 配置的读写与回滚"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import _auth, _backup_file, _cfg, _parse_json_or_400, _read_config_text, _write_json

router = APIRouter()

log = logging.getLogger("atri-bot.WebPanelConfig")

_VALID_CONN_TYPES = {"WebSocket_client", "WebSocket_server", "http", "qqbot"}

_PLATFORM_SECRET_KEYS = ("access_token", "app_secret")
"""平台条目中需要打码的密钥字段（OneBot 的 access_token / QQ 官方机器人的 app_secret）"""

_TOOL_SEARCH_NAME = "tool_search"

_KEEP_SENTINEL = "__KEEP__"
"""密钥打码哨兵：GET 用哨兵替换真实密钥，POST 保存时哨兵还原为磁盘上的旧值"""


def _mask_secrets_enabled() -> bool:
    """web_panel.mask_secrets（默认 true）：配置接口是否对密钥打码"""
    try:
        return (_cfg()._raw_config.get("web_panel") or {}).get("mask_secrets", True) is not False
    except Exception:
        return True


def _current_json(path) -> dict:
    """读磁盘上的当前配置（用于哨兵还原）；不可读时返回空 dict"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def mask_secrets(kind: str, data: dict) -> dict:
    """按配置类型把敏感字段换成哨兵（就地修改并返回入参）"""
    if kind == "main":
        wp = data.get("web_panel")
        if isinstance(wp, dict) and wp.get("access_token"):
            wp["access_token"] = _KEEP_SENTINEL
        db = data.get("database")
        if isinstance(db, dict) and db.get("password"):
            db["password"] = _KEEP_SENTINEL
        for platform in (data.get("platforms") or {}).values():
            if not isinstance(platform, dict):
                continue
            for secret_key in _PLATFORM_SECRET_KEYS:
                if platform.get(secret_key):
                    platform[secret_key] = _KEEP_SENTINEL
    elif kind == "supplier":
        for item in data.get("api") or []:
            if isinstance(item, dict) and item.get("api_key"):
                item["api_key"] = [_KEEP_SENTINEL] if isinstance(item["api_key"], list) else _KEEP_SENTINEL
    elif kind == "mcp":
        for server in (data.get("mcpServers") or {}).values():
            if isinstance(server, dict) and isinstance(server.get("env"), dict):
                for env_key, value in list(server["env"].items()):
                    if value:
                        server["env"][env_key] = _KEEP_SENTINEL
    return data


def restore_secrets(kind: str, new: dict, old: dict) -> None:
    """保存前把哨兵还原为磁盘旧值；哨兵但无旧值时报 400（不落盘半套密钥）"""
    if kind == "main":
        wp_new, wp_old = new.get("web_panel"), old.get("web_panel")
        if isinstance(wp_new, dict) and wp_new.get("access_token") == _KEEP_SENTINEL:
            previous = wp_old.get("access_token") if isinstance(wp_old, dict) else None
            if not previous:
                raise HTTPException(400, "web_panel.access_token 是占位符但没有可还原的旧值，请填写真实口令")
            wp_new["access_token"] = previous
        db_new, db_old = new.get("database"), old.get("database")
        if isinstance(db_new, dict) and db_new.get("password") == _KEEP_SENTINEL:
            previous = db_old.get("password") if isinstance(db_old, dict) else None
            if not previous:
                raise HTTPException(400, "database.password 是占位符但没有可还原的旧值，请填写真实密码")
            db_new["password"] = previous
        platforms_old = old.get("platforms") or {}
        for name, platform in (new.get("platforms") or {}).items():
            if not isinstance(platform, dict):
                continue
            old_platform = platforms_old.get(name)
            for secret_key in _PLATFORM_SECRET_KEYS:
                if platform.get(secret_key) != _KEEP_SENTINEL:
                    continue
                previous = old_platform.get(secret_key) if isinstance(old_platform, dict) else None
                if not previous:
                    raise HTTPException(
                        400,
                        f"platforms.{name}.{secret_key} 是占位符但没有可还原的旧值，请填写真实值",
                    )
                platform[secret_key] = previous
    elif kind == "supplier":
        old_keys = {
            item.get("name"): item.get("api_key")
            for item in old.get("api") or []
            if isinstance(item, dict) and item.get("name")
        }
        for item in new.get("api") or []:
            if not isinstance(item, dict):
                continue
            key = item.get("api_key")
            masked = key == _KEEP_SENTINEL or (
                isinstance(key, list) and bool(key) and all(k == _KEEP_SENTINEL for k in key)
            )
            if not masked:
                continue
            previous = old_keys.get(item.get("name"))
            if not previous:
                raise HTTPException(400, f"供应商 {item.get('name')} 的 api_key 是占位符但没有可还原的旧值，请填写真实密钥")
            item["api_key"] = previous
    elif kind == "mcp":
        old_servers = old.get("mcpServers") or {}
        for name, server in (new.get("mcpServers") or {}).items():
            if not isinstance(server, dict) or not isinstance(server.get("env"), dict):
                continue
            old_server = old_servers.get(name)
            old_env = old_server.get("env") if isinstance(old_server, dict) and isinstance(old_server.get("env"), dict) else {}
            for env_key, value in list(server["env"].items()):
                if value != _KEEP_SENTINEL:
                    continue
                if not old_env.get(env_key):
                    raise HTTPException(400, f"mcpServers.{name}.env.{env_key} 是占位符但没有可还原的旧值，请填写真实值")
                server["env"][env_key] = old_env[env_key]


def mask_text(kind: str, content: str, valid: bool) -> tuple:
    """把合法配置文本打码后重新序列化；返回 (content, masked)"""
    if not valid or not _mask_secrets_enabled():
        return content, False
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        return content, False
    return json.dumps(mask_secrets(kind, parsed), ensure_ascii=False, indent=2), True


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


def _validate_tts(data: dict) -> List[str]:
    """校验 tts 区块：缺省合法（运行时回退内置三情感），配置了则要求字段形态正确"""
    tts = data.get("tts")
    if tts is None:
        return []
    if not isinstance(tts, dict):
        return ["tts 必须是对象"]

    errors: List[str] = []
    api_url = tts.get("api_url")
    if api_url is not None:
        if not isinstance(api_url, str) or not api_url.strip():
            errors.append("tts.api_url 必须是非空字符串")
        elif not api_url.strip().lower().startswith(("http://", "https://")):
            errors.append("tts.api_url 必须是 http:// 或 https:// 开头的地址")

    emotions = tts.get("emotions")
    if emotions is None:
        return errors
    if not isinstance(emotions, dict):
        errors.append("tts.emotions 必须是对象（情感名 → 参考音频配置）")
        return errors

    for name, item in emotions.items():
        if not isinstance(name, str) or not name.strip():
            errors.append("tts.emotions 的情感名不能为空")
            continue
        if any(ch.isspace() for ch in name):
            errors.append(f"tts.emotions.{name} 的情感名不能包含空白字符")
        if not isinstance(item, dict):
            errors.append(f"tts.emotions.{name} 必须是对象")
            continue
        path = item.get("refer_wav_path")
        if not isinstance(path, str) or not path.strip():
            errors.append(f"tts.emotions.{name}.refer_wav_path 不能为空")
        for field in ("prompt_text", "prompt_language"):
            value = item.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(f"tts.emotions.{name}.{field} 必须是字符串")
    return errors


def _has_tool_calls_service() -> bool:
    """运行中的 bot 是否注册了 ToolCalls（独立面板/开发模式下没有）"""
    from atribot.core.service_container import container

    return container.exists("ToolCalls")


def _reload_tool_presets() -> bool:
    """重载工具预设段，由订阅了 `tool_presets` 的 ToolCalls 完成实际刷新

    面板与 bot 同进程才有运行时消费者；独立面板/开发模式下返回 False，
    表示「仅写盘，重启后生效」。
    """
    if not _has_tool_calls_service():
        return False
    try:
        _cfg().reload_section("tool_presets")
    except Exception as exc:  # 热重载失败不应影响保存结果
        log.warning("工具预设热重载失败（配置已写入磁盘，重启后生效）: %s", exc)
        return False
    return True


def _hot_reload_main_config(before: Dict[str, Any]) -> List[str]:
    """重载保存/回滚后发生变化的顶层配置段，并触发 atriConfig 的订阅者回调

    Args:
        before (Dict[str, Any]): 变更前的顶层配置快照

    Returns:
        List[str]: 成功热重载的段名
    """
    cfg = _cfg()
    try:
        with open(cfg.config_file_path, "r", encoding="utf-8") as file_handler:
            after = json.load(file_handler)
    except Exception as exc:
        log.warning("配置热重载失败（磁盘内容不可读，重启后生效）: %s", exc)
        return []
    if not isinstance(after, dict):
        return []

    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    reloaded: List[str] = []
    for key in changed:
        try:
            cfg.reload_section(key)  # 内部通知订阅者
        except Exception as exc:
            log.warning("配置段 %s 热重载失败（重启后生效）: %s", key, exc)
            continue
        reloaded.append(key)
    return reloaded


def _validate_chat_model_overrides(data: dict) -> List[str]:
    """校验 model.group_chat / model.private_chat 覆盖块

    两块均可选；填了就必须是对象，supplier / model_name 若出现必须是非空字符串
    （留空或省略即回退 model.connect）。
    """
    model = data.get("model")
    if model is None:
        return []
    if not isinstance(model, dict):
        return ["model 必须是对象"]

    errors: List[str] = []
    for scope in ("group_chat", "private_chat"):
        override = model.get(scope)
        if override is None:
            continue
        if not isinstance(override, dict):
            errors.append(f"model.{scope} 必须是对象（{{supplier, model_name}}）")
            continue
        for field_name in ("supplier", "model_name"):
            value = override.get(field_name)
            if value is not None and not isinstance(value, str):
                errors.append(f"model.{scope}.{field_name} 必须是字符串（留空回退主聊天模型）")
    return errors


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
            elif conn == "qqbot":
                if not platform.get("app_id"):
                    errors.append(f"platforms.{key}.app_id 不能为空")
                if not platform.get("app_secret"):
                    errors.append(f"platforms.{key}.app_secret 不能为空")
            elif not platform.get("access_token"):
                errors.append(f"platforms.{key}.access_token 不能为空")

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
    errors.extend(_validate_tts(data))
    errors.extend(_validate_chat_model_overrides(data))

    keywords = data.get("initiative_chat_keyword_trigger")
    if keywords is not None and (
        not isinstance(keywords, list)
        or not all(isinstance(k, str) and k.strip() for k in keywords)
    ):
        # 空数组合法：表示关闭关键词触发；缺键则回退内置默认词
        errors.append("initiative_chat_keyword_trigger 必须是字符串数组，元素不能为空字符串（空数组表示关闭关键词触发）")

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
    content, masked = mask_text("main", content, valid)
    return {"content": content, "path": str(path), "valid": valid, "masked": masked}


class ConfigBody(BaseModel):
    content: str


@router.post("/api/config")
async def api_save_config(body: ConfigBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    cfg = _cfg()
    path = cfg.config_file_path
    before = dict(cfg._raw_config)
    parsed = _parse_json_or_400(body.content)
    if _mask_secrets_enabled():
        restore_secrets("main", parsed, _current_json(path))
    _validate_main_config(parsed)
    backup = _backup_file(path)
    _write_json(path, parsed)
    # 变化的配置段统一热重载：订阅者（工具预设/关键词/模型/白名单…）在回调里刷新
    hot_reloaded = _hot_reload_main_config(before)
    return {
        "status": "ok",
        "needs_restart": True,
        "backup": str(backup),
        "presets_reloaded": "tool_presets" in hot_reloaded and _has_tool_calls_service(),
        "keywords_reloaded": "initiative_chat_keyword_trigger" in hot_reloaded,
        "hot_reloaded": hot_reloaded,
    }


@router.get("/api/supplier_config")
async def api_get_supplier_config(_: None = Depends(_auth)) -> Dict[str, Any]:
    path = _cfg().file_path.supplier_config_path
    content, valid = _read_config_text(path)
    content, masked = mask_text("supplier", content, valid)
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
    return {"content": content, "path": str(path), "valid": valid, "suppliers": suppliers, "masked": masked}


@router.post("/api/supplier_config")
async def api_save_supplier_config(body: ConfigBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    path = _cfg().file_path.supplier_config_path
    parsed = _parse_json_or_400(body.content)
    if _mask_secrets_enabled():
        restore_secrets("supplier", parsed, _current_json(path))
    _validate_supplier_config(parsed)
    backup = _backup_file(path)
    _write_json(path, parsed)
    return {"status": "ok", "needs_restart": True, "backup": str(backup)}


@router.get("/api/mcp_config")
async def api_get_mcp_config(_: None = Depends(_auth)) -> Dict[str, Any]:
    path = _cfg().file_path.mcp_config
    if not path.exists():
        return {"content": "{\n    \"mcpServers\": {}\n}\n", "path": str(path), "valid": True, "exists": False, "masked": False}
    content, valid = _read_config_text(path)
    content, masked = mask_text("mcp", content, valid)
    return {"content": content, "path": str(path), "valid": valid, "exists": True, "masked": masked}


@router.post("/api/mcp_config")
async def api_save_mcp_config(body: ConfigBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    path = _cfg().file_path.mcp_config
    parsed = _parse_json_or_400(body.content)
    if _mask_secrets_enabled():
        restore_secrets("mcp", parsed, _current_json(path))
    backup = _backup_file(path)
    _write_json(path, parsed)
    return {"status": "ok", "needs_restart": True, "backup": str(backup)}


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
    before = dict(cfg._raw_config)
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    shutil.copy2(backup, path)
    if previous is not None:
        backup.write_text(previous, encoding="utf-8")
    hot_reloaded = _hot_reload_main_config(before) if body.target == "config" else []
    return {
        "status": "ok",
        "restored_from": str(backup),
        "needs_restart": True,
        "presets_reloaded": "tool_presets" in hot_reloaded and _has_tool_calls_service(),
        "hot_reloaded": hot_reloaded,
    }
