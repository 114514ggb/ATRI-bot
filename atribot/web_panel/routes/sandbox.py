"""容器管理：沙盒状态展示 / 启停控制 / 沙盒内交互终端

面板只依赖 SandBoxBase 的 panel_* 扩展点（能力声明、状态快照、终端流），
不感知具体后端——切换 docker / no-sandbox / e2b 或接入新实现时无需改这里。
"""

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket

from atribot.core.service_container import container
from atribot.LLMchat.sandbox.factory import create_sandbox, resolve_sandbox_config
from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase

from ..deps import _auth, _cfg, _ensure_ws_session, _ws_auth

router = APIRouter()


def _sandbox() -> Optional[SandBoxBase]:
    try:
        return container.get("SandBox")
    except Exception:
        return None


def _sandbox_config() -> dict:
    try:
        config = _cfg()
        raw = (config._raw_config or {}).get("sand_box") or {}
        document_root = getattr(getattr(config, "file_path", None), "document_root", None)
        return resolve_sandbox_config(raw, document_root)
    except Exception:
        return {}


def _reload_sandbox_tools() -> Optional[list]:
    """沙盒可用性变化后全量重载本地工具（失败不影响沙盒操作）"""
    try:
        from atribot.LLMchat.MCP.tool_calls import ToolCalls

        return container.get_by_type(ToolCalls).reload_local_tools()
    except Exception:
        return None


async def _send(websocket: WebSocket, payload: dict) -> None:
    try:
        await websocket.send_json(payload)
    except Exception:
        pass  # 连接已断开


# ---------- 状态与启停 ----------

@router.get("/api/sandbox/status")
async def api_sandbox_status(_: None = Depends(_auth)) -> dict:
    sb = _sandbox()
    result = {"configured": sb is not None, "type": str(_sandbox_config().get("type", "docker")).lower()}
    if sb is None:
        return result
    result["capabilities"] = sb.panel_capabilities()
    try:
        status = await sb.panel_status()
    except Exception as e:
        status = {
            "backend": getattr(sb, "backend", "?"),
            "display": getattr(sb, "backend_display", "未知后端"),
            "running": False,
            "rows": [("状态查询失败", str(e))],
        }
    result.update(status)
    return result


@router.post("/api/sandbox/start")
async def api_sandbox_start(_: None = Depends(_auth)) -> dict:
    sb = _sandbox()
    if sb is not None and sb.is_running:
        return {"status": "already_running"}
    try:
        if sb is None:
            # bot 启动时沙盒初始化失败（如 Docker 未就绪）：面板可在此懒启动
            sb = create_sandbox(_sandbox_config())
            await sb.start()
            container.register("SandBox", sb, cleanup=sb.stop)
        else:
            await sb.start()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"沙盒启动失败：{e}")
    _reload_sandbox_tools()
    return {"status": "started", "backend": sb.backend}


@router.post("/api/sandbox/stop")
async def api_sandbox_stop(_: None = Depends(_auth)) -> dict:
    sb = _sandbox()
    if sb is None:
        raise HTTPException(status_code=503, detail="沙盒未初始化")
    if not sb.is_running:
        return {"status": "already_stopped"}
    try:
        await sb.stop()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"沙盒停止失败：{e}")
    _reload_sandbox_tools()
    return {"status": "stopped"}


@router.post("/api/sandbox/restart")
async def api_sandbox_restart(_: None = Depends(_auth)) -> dict:
    sb = _sandbox()
    if sb is None:
        raise HTTPException(status_code=503, detail="沙盒未初始化")
    try:
        await sb.restart()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"沙盒重启失败：{e}")
    _reload_sandbox_tools()
    return {"status": "restarted", "backend": sb.backend}


@router.post("/api/sandbox/refresh-tools")
async def api_sandbox_refresh_tools(_: None = Depends(_auth)) -> dict:
    """重读 sand_box 配置并刷新依赖工具的启用状态与描述（无需重启进程）

    会用当前 config.json 的 sand_box 段重建沙盒实例（未运行时仅注册不启动），
    使切换 type / work_dir / tool_prompts 后立即可用。
    """
    config = _sandbox_config()
    try:
        new_sandbox = create_sandbox(config)

        prev = _sandbox()
        was_running = bool(prev is not None and prev.is_running)
        if prev is not None:
            try:
                await prev.stop()
            except Exception:
                pass
            container.unregister("SandBox")

        if was_running:
            await new_sandbox.start()
        container.register("SandBox", new_sandbox, cleanup=new_sandbox.stop)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"沙盒重建失败：{e}")

    changed = _reload_sandbox_tools()
    return {
        "status": "refreshed",
        "backend": new_sandbox.backend,
        "running": new_sandbox.is_running,
        "changed_tools": changed or [],
    }


# ---------- 沙盒终端 ----------

class _TerminalSession:
    """单个 WebSocket 连接的沙盒终端会话"""

    def __init__(self, sandbox: SandBoxBase):
        self.sandbox = sandbox
        self.cwd = sandbox.panel_terminal_info().get("cwd", "/")
        self.busy = False
        self.handle = None


@router.websocket("/api/ws/sandbox-terminal")
async def ws_sandbox_terminal(websocket: WebSocket, token: str = "", ticket: str = "") -> None:
    # _ws_auth 内部已 accept（失败时以 4401 关闭）；优先一次性票据，兼容旧 ?token=
    session_ref = await _ws_auth(websocket, token, ticket)
    if session_ref is None:
        return

    sb = _sandbox()
    if sb is None:
        # 先 accept 再带 code 关闭：pre-accept 的 close 会被 uvicorn 转成
        # HTTP 403，浏览器永远收不到自定义 close code
        await websocket.accept()
        await websocket.close(code=4450)  # 沙盒未初始化
        return
    if not sb.panel_capabilities().get("terminal"):
        await websocket.accept()
        await websocket.close(code=4451)  # 当前后端不支持终端
        return

    session = _TerminalSession(sb)
    hello = {"type": "hello", "commands": [], **sb.panel_terminal_info()}
    await _send(websocket, hello)

    try:
        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")
            if mtype == "exec":
                cmd = str(msg.get("cmd") or "").strip()
                if not cmd or len(cmd) > 8192:
                    continue
                # 会话复验：吊销/过期后立即断开，不再接受新命令
                if not await _ensure_ws_session(websocket, session_ref):
                    return
                if session.busy:
                    await _send(websocket, {"type": "output", "data": "[atri] 已有命令在执行，请等待完成或先终止\n"})
                    continue
                if not getattr(sb, "is_running", False):
                    await _send(websocket, {"type": "output", "data": "[atri] 沙盒未运行，请先在上方启动\n"})
                    continue
                asyncio.create_task(_run_exec(websocket, session, cmd))
            elif mtype == "kill":
                if session.handle is not None:
                    session.handle.kill()
            elif mtype == "ping":
                await _send(websocket, {"type": "pong"})
            elif mtype == "complete":
                # 路径补全暂未适配容器内文件系统：保持协议应答为空
                await _send(websocket, {"type": "complete", "id": msg.get("id"), "items": []})
    except Exception:
        pass  # WebSocket 断开或坏帧
    finally:
        if session.handle is not None:
            session.handle.kill()  # 连接关闭时终止仍在运行的命令


async def _run_exec(websocket: WebSocket, session: _TerminalSession, cmd: str) -> None:
    session.busy = True
    started = time.monotonic()
    code = -1
    try:
        async def send(text: str) -> None:
            await _send(websocket, {"type": "output", "data": text})

        try:
            handle = await session.sandbox.panel_exec_stream(cmd, send, cwd=session.cwd)
        except NotImplementedError:
            await send("[atri] 当前后端不支持终端执行\n")
            return
        except RuntimeError as e:
            await send(f"[atri] 沙盒不可用：{e}\n")
            return

        session.handle = handle
        code = await handle.wait()
        if getattr(handle, "new_cwd", None):
            session.cwd = handle.new_cwd
    except Exception as e:  # WebSocket 断开等
        await _send(websocket, {"type": "output", "data": f"\n[atri] 执行出错：{e}\n"})
        code = -1
    finally:
        session.handle = None
        session.busy = False
        await _send(
            websocket,
            {
                "type": "exit",
                "code": code,
                "ms": round((time.monotonic() - started) * 1000),
                "cwd": session.cwd,
            },
        )
