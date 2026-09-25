"""WebUI 聊天：会话/附件/工具预设端点与聊天 WebSocket

核心循环在 chat_engine.py（复用 SubAgentRunner）；这里只做协议适配：
HTTP 端点负责启动信息、附件上传/预览、工具预设持久化与会话管理，
WebSocket 负责收发消息与逐事件转发 Agent 流式输出。
"""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, WebSocket
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..deps import (
    _auth,
    _cfg,
    _ensure_ws_session,
    _require_session,
    _ws_auth,
)
from . import chat_engine as engine
from .chat_engine import registry
from .config import _reload_tool_presets, _validate_tool_presets

router = APIRouter()


@router.get("/api/chat/info")
async def api_chat_info(_: None = Depends(_auth)) -> Dict[str, Any]:
    """聊天页启动信息：默认模型/人设、webui 工具预设、上传限额等"""
    cfg = _cfg()
    connect = cfg._raw_config.get("model", {}).get("connect", {}) or {}
    chat_parameter = cfg._raw_config.get("model", {}).get("chat_parameter", {}) or {}
    default_persona = (cfg._raw_config.get("ai_chat") or {}).get("playRole") or "none"

    preset_exists = engine.WEBUI_PRESET in (cfg._raw_config.get("tool_presets") or {})
    preset_default: List[str] = []
    preset_deferred: List[str] = []
    tc = engine._tool_calls_service()
    preset_names = list(tc.presets) if tc is not None else list((cfg._raw_config.get("tool_presets") or {}).keys())
    if tc is not None:
        try:
            toolset = tc.presets.get(engine.WEBUI_PRESET)
            if toolset is not None:
                preset_default = list(toolset.names())
            preset_deferred = tc.get_preset_deferred_names(engine.WEBUI_PRESET)
        except Exception:
            pass

    return {
        "defaults": {
            "supplier": connect.get("supplier", ""),
            "model": connect.get("model_name", ""),
            "persona": default_persona,
            "chat_parameter": chat_parameter,
        },
        "webui_preset": {
            "name": engine.WEBUI_PRESET,
            "exists": preset_exists,
            "default": preset_default,
            "deferred": preset_deferred,
            "preset_names": preset_names,
        },
        "limits": {
            "image": engine.IMAGE_LIMIT,
            "audio": engine.AUDIO_LIMIT,
            "video": engine.VIDEO_LIMIT,
            "file": engine.FILE_LIMIT,
        },
        "max_turns": engine.MAX_TURNS,
        "id_range": [1, engine.WEBUI_ID_MAX],
    }


@router.post("/api/chat/upload")
async def api_chat_upload(file: UploadFile, _: None = Depends(_auth)) -> Dict[str, Any]:
    """上传一个聊天附件（流式读取，按类别限制大小）"""
    name = file.filename or "file"
    kind = engine.classify_file(name, file.content_type or "")
    limit = engine.size_limit_for(kind)

    chunks: List[bytes] = []
    size = 0
    while True:
        chunk = await file.read(1 << 20)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise HTTPException(
                status_code=413,
                detail=f"{kind} 大小超过限制 {limit // (1024 * 1024)}MB: {name}",
            )
        chunks.append(chunk)

    info = engine.save_attachment(name, file.content_type or "", b"".join(chunks))
    engine.purge_old_uploads()
    return {"status": "ok", "file": engine.attachment_brief(info)}


@router.get("/api/chat/files/{file_id}")
async def api_chat_file(
    file_id: str,
    token: str = "",
) -> FileResponse:
    """附件预览（img/audio/video 标签无法带 Header，会话令牌走 query 参数）"""
    _require_session(token)
    info = engine.get_attachment(file_id)
    if info is None:
        raise HTTPException(status_code=404, detail="附件不存在或已过期")
    # FileResponse 的 filename 已带 attachment；再挂一道 CSP，即便将来丢掉 disposition 也不会同源渲染
    # （nosniff 由 install_security_headers 对 /admin 全量下发，不在此重复）
    return FileResponse(
        info["path"],
        media_type=info["mime"],
        filename=info["name"],
        headers={"Content-Security-Policy": "default-src 'none'"},
    )


_AVATAR_CANDIDATES = ("ATRI-bot.png", "ATRI-bot.jpg", "ATRI-bot.jpeg", "ATRI-bot.webp", "ATRI-bot.gif")
_AVATAR_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}


def _find_bot_image() -> Optional[Path]:
    """配置文件同级的 ATRI-bot 图（固定候选文件名，无路径穿越风险）"""
    base = Path(_cfg().config_file_path).parent
    for name in _AVATAR_CANDIDATES:
        path = base / name
        if path.is_file():
            return path
    return None


@router.get("/api/chat/avatar")
async def api_chat_avatar(token: str = "") -> FileResponse:
    """机器人头像：配置文件同级的 ATRI-bot 图（img 标签走 query 令牌；FileResponse 自带 ETag，换图自动失效）"""
    _require_session(token)
    path = _find_bot_image()
    if path is None:
        raise HTTPException(status_code=404, detail="未找到头像图片（在配置目录下放置 ATRI-bot.png）")
    return FileResponse(path, media_type=_AVATAR_MEDIA[path.suffix.lower()])


@router.get("/api/panel/logo")
async def api_panel_logo() -> FileResponse:
    """面板品牌图：免鉴权——登录页与 favicon 在拿到令牌之前就要显示，
    且仅读取配置目录下固定文件名的 ATRI-bot 图，泄露面只是头像本身。
    FileResponse 自带 ETag，换图自动失效。"""
    path = _find_bot_image()
    if path is None:
        raise HTTPException(status_code=404, detail="未找到品牌图片（在配置目录下放置 ATRI-bot.png）")
    return FileResponse(path, media_type=_AVATAR_MEDIA[path.suffix.lower()])


class ChatToolsBody(BaseModel):
    tools: List[str]
    deferred: Optional[List[str]] = None
    """待发现组目标名单；缺省表示不改动待发现组"""


async def _sync_group(tc: Any, group: str, current: set, target: set) -> None:
    """把 webui 预设某个分组的名单同步为 target（增删各一次写入，组间互斥由 ToolPresetManager 保证）"""
    for op, names in (("remove", current - target), ("add", target - current)):
        if names:
            await tc.modify_preset_tools(engine.WEBUI_PRESET, op, sorted(names), group=group)


def _create_webui_preset(name: str, tools: List[str], deferred: List[str]) -> None:
    """在 config.json 中补齐缺失的预设段（仅用于固定预设，如 webui）

    ToolPresetManager.modify_preset_tools 禁止新建预设，这里直接写盘 + 热重载，
    否则用户在浏览器端遇到「预设不存在」就无路可走。
    """
    path = _cfg().config_file_path
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("tool_presets", {})[name] = {"default": tools, "deferred": deferred} if deferred else tools

    shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))  # 与 POST /api/config 一致，先备份再写
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    _reload_tool_presets()


@router.post("/api/chat/tools")
async def api_chat_tools_save(body: ChatToolsBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    """把当前编辑的工具列表保存为该预设的默认组与待发现组（持久化到 config.json）

    传全量目标名单：先同步待发现组（跨组移动的工具会自动从默认组移除），再同步默认组。
    两组互斥由 ToolPresetManager 保证；预设不存在时（被手删 / 从未配置）会直接创建。
    """
    tc = engine._tool_calls_service()
    if tc is None:
        raise HTTPException(503, "工具系统不可用（bot 未启动或 ToolCalls 未注册）")

    name = engine.WEBUI_PRESET
    target_tools = sorted(set(body.tools))
    target_deferred = sorted(set(body.deferred)) if body.deferred is not None else None
    pair_errors = _validate_tool_presets(
        {"tool_presets": {name: {"default": target_tools, "deferred": target_deferred or []}}}
    )
    if pair_errors:
        raise HTTPException(status_code=400, detail=pair_errors[0])

    if tc.presets.get(name) is None:
        _create_webui_preset(name, target_tools, target_deferred or [])
        return {"status": "ok", "created": True, "tools": target_tools, "deferred": target_deferred or []}

    try:
        if target_deferred is not None:
            await _sync_group(tc, "deferred", set(tc.get_preset_deferred_names(name)), set(target_deferred))
        await _sync_group(tc, "default", set(tc.presets[name].names()), set(target_tools))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _reload_tool_presets()
    return {
        "status": "ok",
        "created": False,
        "tools": target_tools,
        "deferred": target_deferred if target_deferred is not None else sorted(tc.get_preset_deferred_names(name)),
    }


@router.get("/api/chat/sessions")
async def api_chat_sessions(_: None = Depends(_auth)) -> Dict[str, Any]:
    return {"items": await registry.list_overview()}


@router.delete("/api/chat/sessions/{session_id}")
async def api_chat_session_delete(session_id: int, _: None = Depends(_auth)) -> Dict[str, Any]:
    await registry.delete(session_id)
    return {"status": "ok", "deleted": session_id}


# ---------- 聊天 WebSocket ----------

def _history_payload(session: "engine.ChatSession") -> Dict[str, Any]:
    return {
        "type": "history",
        "session": session.id,
        "items": session.timeline,
        "running": session.running,
        "persona": session.persona_key or engine.PERSONA_CUSTOM,
    }


@router.websocket("/api/ws/chat")
async def ws_chat(websocket: WebSocket, token: str = "", ticket: str = "") -> None:
    # _ws_auth 内部已 accept（失败时以 4401 关闭）；优先一次性票据，兼容旧 ?token=
    session_ref = await _ws_auth(websocket, token, ticket)
    if session_ref is None:
        return

    queue: asyncio.Queue = asyncio.Queue()
    subscribed: Optional[engine.ChatSession] = None
    sender_task: Optional[asyncio.Task] = None

    def _unsubscribe() -> None:
        nonlocal queue, subscribed
        if subscribed is not None and queue is not None:
            subscribed.unsubscribe(queue)
        subscribed = None

    async def _sender() -> None:
        while True:
            message = await queue.get()
            await websocket.send_json(message)

    async def _switch(session: "engine.ChatSession") -> None:
        """切换当前订阅的会话（复用同一个队列）"""
        nonlocal subscribed
        _unsubscribe()
        subscribed = session
        session.listeners.add(queue)

    try:
        sender_task = asyncio.create_task(_sender())
        await websocket.send_json({"type": "ready"})

        while True:
            try:
                data = await websocket.receive_json()
            except ValueError:
                await websocket.send_json({"type": "error", "message": "消息必须是 JSON 对象"})
                continue
            if not isinstance(data, dict):
                await websocket.send_json({"type": "error", "message": "消息必须是 JSON 对象"})
                continue

            # 会话可能已被吊销/过期：逐条复验，失效则断开（防长连接绕过登出）
            if not await _ensure_ws_session(websocket, session_ref):
                return

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "load":
                session_id = data.get("session")
                try:
                    session = await registry.get_or_load(int(session_id))
                except (KeyError, TypeError, ValueError) as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
                    continue
                await _switch(session)
                await websocket.send_json(_history_payload(session))

            elif msg_type == "create":
                session = await registry.create()
                await _switch(session)
                await websocket.send_json({"type": "session", "id": session.id})
                await websocket.send_json(_history_payload(session))

            elif msg_type == "stop":
                if subscribed is not None and subscribed.running:
                    subscribed.task.cancel()
                    await websocket.send_json({"type": "stopping", "session": subscribed.id})
                else:
                    await websocket.send_json({"type": "error", "message": "当前没有正在进行的生成"})

            elif msg_type == "edit":
                # 编辑回退：截断到第 um_index 条用户消息并替换文本，可选立即重发
                um_index = data.get("um_index")
                text = str(data.get("text") or "")
                resend = bool(data.get("resend"))
                settings = data.get("settings") or {}
                session_id = data.get("session")
                try:
                    if session_id is not None:
                        session = await registry.get_or_load(int(session_id))
                    elif subscribed is not None:
                        session = subscribed
                    else:
                        raise KeyError("未指定会话")
                except (KeyError, TypeError, ValueError) as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
                    continue
                if session is not subscribed:
                    await _switch(session)
                if session.running:
                    await websocket.send_json({"type": "busy", "session": session.id})
                    continue
                if not engine.edit_user_message(session, um_index, text):
                    await websocket.send_json({"type": "error", "message": f"消息序号无效: {um_index}"})
                    continue
                await engine.db_save(session)
                session.broadcast(_history_payload(session))
                if resend:
                    started = await engine.start_regenerate(session, settings)
                    if not started:
                        await websocket.send_json({"type": "busy", "session": session.id})

            elif msg_type == "send":
                text = data.get("text") or ""
                file_ids = data.get("files") or []
                settings = data.get("settings") or {}
                nonce = data.get("nonce") or ""
                if not isinstance(file_ids, list) or not all(isinstance(f, str) for f in file_ids):
                    await websocket.send_json({"type": "error", "message": "files 必须是附件 id 数组"})
                    continue
                if not text.strip() and not file_ids:
                    await websocket.send_json({"type": "error", "message": "消息内容不能为空"})
                    continue

                session_id = data.get("session")
                try:
                    if session_id is None:
                        session = await registry.create()
                        await _switch(session)
                        await websocket.send_json({"type": "session", "id": session.id})
                    else:
                        session = await registry.get_or_load(int(session_id))
                        if session is not subscribed:
                            await _switch(session)
                except (KeyError, TypeError, ValueError) as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
                    continue

                started = await engine.start_turn(session, text, file_ids, settings, nonce)
                if not started:
                    await websocket.send_json({"type": "busy", "session": session.id})

            else:
                await websocket.send_json({"type": "error", "message": f"未知消息类型: {msg_type}"})

    except Exception:
        return
    finally:
        if sender_task is not None:
            sender_task.cancel()
        _unsubscribe()
