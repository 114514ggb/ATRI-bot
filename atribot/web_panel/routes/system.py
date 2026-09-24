"""系统控制：停止进程（Ctrl+C 语义优雅关闭）、WebSocket 实时日志流

面板不提供重启：整体重启需要正确的「先回收再拉起」时序，已移除；
需要重启时只提供「立即关闭」，由用户在终端手动重新启动。
"""

import asyncio
import logging
import signal
from typing import Dict

from fastapi import APIRouter, Depends, WebSocket

from ..deps import (
    _auth,
    _ensure_log_handler,
    _log_buffer,
    _log_buffer_lock,
    _ws_auth,
)

router = APIRouter()

log = logging.getLogger("atri-bot.System")

STOP_TRIGGER_DELAY = 0.3
"""回包后多久投递 SIGINT（秒）：SIGINT 会立刻结束事件循环，必须先让响应发出去"""


def _trigger_graceful_stop() -> None:
    """伪造一次 Ctrl+C，交给 asyncio.Runner 的 SIGINT 处理器去优雅关闭

    main.py 的 ``asyncio.run()`` 在运行期安装了 SIGINT 处理器：第一次 SIGINT 会
    cancel 主任务 → ``main()`` 收到 CancelledError → finally 走
    ``BotFramework.graceful_shutdown()``，回收沙盒 / MCP / 数据库连接池 / 插件等资源，
    最终以退出码 0 结束。因此这里与用户在终端按 Ctrl+C 完全同一条路径。

    注意：signal.raise_signal 需要投递到主线程的事件循环（当前架构成立：
    asyncio.run + 面板 uvicorn 都跑在主线程），Windows / POSIX 行为一致。
    """
    log.info("收到管理面板的停止请求，以 Ctrl+C 语义优雅关闭")
    signal.raise_signal(signal.SIGINT)


@router.post("/api/system/stop")
async def api_system_stop(_: None = Depends(_auth)) -> Dict[str, str]:
    """请求优雅关闭；延迟触发，确保本响应先发出去"""
    loop = asyncio.get_running_loop()
    loop.call_later(STOP_TRIGGER_DELAY, _trigger_graceful_stop)
    return {"status": "stopping"}


@router.websocket("/api/ws/logs")
async def ws_logs(websocket: WebSocket, token: str = "") -> None:
    # _ws_auth 内部已 accept（失败时带 4401/4429 关闭）
    if not await _ws_auth(websocket, token):
        return

    _ensure_log_handler()

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
