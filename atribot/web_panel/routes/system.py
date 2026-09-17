"""系统控制：停止 / 重启进程，WebSocket 实时日志流"""

import asyncio
import os
import secrets
import subprocess
import sys
from typing import Dict

from fastapi import APIRouter, Depends, WebSocket

from ..deps import (
    _access_token,
    _auth,
    _auth_rate_limited,
    _cfg,
    _clear_auth_failures,
    _ensure_log_handler,
    _log_buffer,
    _log_buffer_lock,
    _register_auth_failure,
)

router = APIRouter()


@router.post("/api/system/stop")
async def api_system_stop(_: None = Depends(_auth)) -> Dict[str, str]:
    loop = asyncio.get_event_loop()
    loop.call_later(0.5, lambda: os._exit(0))
    return {"status": "stopping"}


@router.post("/api/system/restart")
async def api_system_restart(_: None = Depends(_auth)) -> Dict[str, str]:
    subprocess_args = [sys.executable] + sys.argv

    def _do_restart() -> None:
        subprocess.Popen(subprocess_args, cwd=str(_cfg().file_path.project_root))
        os._exit(0)

    loop = asyncio.get_event_loop()
    loop.call_later(0.5, _do_restart)
    return {"status": "restarting"}


@router.websocket("/api/ws/logs")
async def ws_logs(websocket: WebSocket, token: str = "") -> None:
    expected = _access_token()
    if not expected:
        await websocket.close(code=4401)
        return

    ip = websocket.client.host if websocket.client else "?"
    if _auth_rate_limited(ip) is not None:
        await websocket.close(code=4429)  # 与 HTTP 共用同一套失败锁定
        return
    if not secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        _register_auth_failure(ip)
        await websocket.close(code=4401)
        return
    _clear_auth_failures(ip)

    _ensure_log_handler()
    await websocket.accept()

    with _log_buffer_lock:
        history = list(_log_buffer)
    try:
        if history:
            await websocket.send_json({"type": "history", "items": history})
        last_seq = history[-1]["seq"] if history else 0

        while True:
            await asyncio.sleep(0.25)
            with _log_buffer_lock:
                pending = [item for item in _log_buffer if item["seq"] > last_seq]
            if pending:
                last_seq = pending[-1]["seq"]
                await websocket.send_json({"type": "logs", "items": pending})
    except Exception:
        return
