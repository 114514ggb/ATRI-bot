"""QQ 官方机器人 WebSocket 网关客户端

协议（与 Discord 类似）::

    建立 wss 连接
    <- op 10 Hello  {"d": {"heartbeat_interval": 41250}}
    -> op 2  Identify {"d": {"token": "QQBot xxx", "intents": N, "shard": [0, 1]}}
    <- op 0  READY    {"d": {"session_id": ..., "user": {...}}}
    -> op 1  Heartbeat {"d": last_seq}   （按 heartbeat_interval 周期发送）
    <- op 11 Heartbeat ACK
    <- op 0  Dispatch {"t": "GROUP_AT_MESSAGE_CREATE", "d": {...}, "s": 42}

断线后优先 ``op 6 Resume``（携带 session_id + seq），``op 9`` 表示会话失效需要重新
Identify；``op 7`` 表示服务端要求重连。
"""

from __future__ import annotations

import asyncio
import inspect
import json
from logging import Logger
from typing import Any, Callable, Optional

import aiohttp

from atribot.core.logger import get_named_logger
from atribot.core.platform.qqbot.api import QQBotApiClient
from atribot.core.platform.qqbot.auth import QQBotTokenManager

OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_RESUME = 6
OP_RECONNECT = 7
OP_INVALID_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11

DEFAULT_HEARTBEAT_INTERVAL = 30.0
"""未收到 Hello 时的兜底心跳间隔（秒）"""


class QQBotGatewayClient:
    """QQ 官方机器人网关长连接

    对外接口与 ``OneBotWSClient`` 对齐：``start`` / ``close`` /
    ``add_listener`` / ``remove_listener`` / ``wait_for_connection`` /
    ``is_connected`` / ``retry_count``。
    """

    def __init__(
        self,
        api: QQBotApiClient,
        tokens: QQBotTokenManager,
        *,
        intents: int,
        log: Logger | None = None,
        retry_delay: float = 1.0,
        max_retry_delay: float = 60.0,
    ) -> None:
        self._api = api
        self._tokens = tokens
        self._intents = intents
        self.log = log or get_named_logger("QQBotGateway")

        self._retry_delay = retry_delay
        self._max_retry_delay = max_retry_delay

        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._running = False
        self._ready = asyncio.Event()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._retry_count = 0

        self._listeners: list[Callable[[dict], Any]] = []

        self._session_id: str = ""
        self._last_seq: int = 0
        self._bot_user: dict[str, Any] = {}

    # ------------------------------------------------------------------ 状态
    @property
    def is_connected(self) -> bool:
        """是否已收到 READY / RESUMED 且连接仍然打开"""
        if self._ws is None or self._ws.closed:
            return False
        return self._ready.is_set()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def retry_count(self) -> int:
        return self._retry_count

    @property
    def intents(self) -> int:
        """当前订阅的事件位掩码"""
        return self._intents

    @property
    def bot_user(self) -> dict[str, Any]:
        """READY 事件里的机器人自身信息（id / username）"""
        return dict(self._bot_user)

    @property
    def session_id(self) -> str:
        return self._session_id

    async def wait_for_connection(self, timeout: Optional[float] = None) -> bool:
        """等待 READY（或 RESUMED）"""
        try:
            if timeout:
                await asyncio.wait_for(self._ready.wait(), timeout=timeout)
            else:
                await self._ready.wait()
            return True
        except asyncio.TimeoutError:
            return False

    def add_listener(self, callback: Callable[[dict], Any]) -> None:
        """注册 dispatch 监听器（参数为原始 payload）"""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[dict], Any]) -> None:
        """移除 dispatch 监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    # ------------------------------------------------------------------ 生命周期
    async def start(self) -> None:
        """启动网关连接（阻塞直到 close() 被调用）"""
        if self._running:
            return
        self._running = True
        try:
            await self._run_forever()
        except asyncio.CancelledError:
            raise
        finally:
            self._running = False
            self._ready.clear()

    async def close(self) -> None:
        """关闭网关连接"""
        self._running = False
        self._ready.clear()

        await self._stop_heartbeat()

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001 - 关闭阶段的异常只记日志
                self.log.debug("关闭 WebSocket 时出现异常", exc_info=True)
            self._ws = None

        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

        self._listeners.clear()
        self.log.info("QQ 官方机器人网关已关闭")

    async def _run_forever(self) -> None:
        delay = self._retry_delay
        while self._running:
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - 任何异常都要重连
                self._ready.clear()
                if not self._running:
                    break
                self._retry_count += 1
                self.log.warning(
                    "QQ 官方机器人网关异常: %s（%d 次重连，%.1fs 后重试）",
                    exc,
                    self._retry_count,
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_retry_delay)

            if not self._running:
                break
            if self._session_id:
                self.log.info("正在恢复 QQ 官方机器人网关会话...")
            else:
                self.log.info("正在重新连接 QQ 官方机器人网关...")
            # 避免服务端立即断开时形成紧凑重连循环
            await asyncio.sleep(self._retry_delay)

    async def _connect_once(self) -> None:
        await self._stop_heartbeat()

        gateway_url = await self._api.get_gateway_url()
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        self.log.info("正在连接 QQ 官方机器人网关: %s", gateway_url)
        async with self._session.ws_connect(gateway_url, heartbeat=None, max_msg_size=0) as ws:
            self._ws = ws
            try:
                async for message in ws:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        await self._on_payload(message.data)
                    elif message.type == aiohttp.WSMsgType.ERROR:
                        raise RuntimeError(f"WebSocket 错误: {ws.exception()}")
                    elif message.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSING,
                    ):
                        break
            finally:
                self._ws = None
                self._ready.clear()
                await self._stop_heartbeat()

        self.log.warning("QQ 官方机器人网关连接已断开")

    # ------------------------------------------------------------------ 收包
    async def _on_payload(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except ValueError:
            self.log.warning("网关消息不是合法 JSON: %s", raw[:200])
            return

        event_type = payload.get("t")
        data = payload.get("d") or {}
        op = payload.get("op")
        if op is None and event_type:
            # 个别代理/测试服务端会省略 op=0，按 dispatch 处理
            op = OP_DISPATCH

        if op == OP_HELLO:
            await self._on_hello(data)
            return
        if op == OP_HEARTBEAT_ACK:
            return
        if op == OP_RECONNECT:
            self.log.info("服务端要求重连网关")
            await self._close_ws()
            return
        if op == OP_INVALID_SESSION:
            self.log.warning("网关会话失效，重新 Identify")
            self._session_id = ""
            self._last_seq = 0
            await self._close_ws()
            return
        if op == OP_HEARTBEAT:
            return

        if op != OP_DISPATCH:
            self.log.debug("收到未处理 op=%s: %s", op, raw[:200])
            return

        seq = payload.get("s")
        if isinstance(seq, int) and seq > 0:
            self._last_seq = seq

        if event_type == "READY":
            self._session_id = str(data.get("session_id") or "")
            user = data.get("user") or {}
            if isinstance(user, dict):
                self._bot_user = user
            self._ready.set()
            self._retry_count = 0
            self.log.info(
                "QQ 官方机器人已上线: %s (%s)",
                user.get("username") if isinstance(user, dict) else None,
                user.get("id") if isinstance(user, dict) else None,
            )
        elif event_type == "RESUMED":
            self._ready.set()
            self._retry_count = 0
            self.log.info("QQ 官方机器人网关会话已恢复")

        for listener in list(self._listeners):
            await self._safe_callback(listener, payload)

    async def _on_hello(self, data: dict[str, Any]) -> None:
        try:
            interval_ms = float(data.get("heartbeat_interval") or 0)
        except (TypeError, ValueError):
            interval_ms = 0.0
        interval = (interval_ms / 1000.0) if interval_ms > 0 else DEFAULT_HEARTBEAT_INTERVAL

        await self._start_heartbeat(interval)

        if self._session_id:
            await self._send_payload(
                {
                    "op": OP_RESUME,
                    "d": {
                        "token": await self._token_string(),
                        "session_id": self._session_id,
                        "seq": self._last_seq,
                    },
                }
            )
        else:
            await self._send_payload(
                {
                    "op": OP_IDENTIFY,
                    "d": {
                        "token": await self._token_string(),
                        "intents": self._intents,
                        "shard": [0, 1],
                    },
                }
            )

    async def _token_string(self) -> str:
        token = await self._tokens.get_token()
        return f"QQBot {token}"

    async def _send_payload(self, payload: dict[str, Any]) -> None:
        if self._ws is None or self._ws.closed:
            raise RuntimeError("网关连接尚未建立")
        await self._ws.send_str(json.dumps(payload, ensure_ascii=False))

    async def _close_ws(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                self.log.debug("关闭 WebSocket 失败", exc_info=True)
            self._ws = None
        self._ready.clear()

    # ------------------------------------------------------------------ 心跳
    async def _start_heartbeat(self, interval: float) -> None:
        await self._stop_heartbeat()
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(interval),
            name="QQBotGateway.heartbeat",
        )

    async def _stop_heartbeat(self) -> None:
        task = self._heartbeat_task
        self._heartbeat_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                self.log.debug("停止心跳任务时出现异常", exc_info=True)

    async def _heartbeat_loop(self, interval: float) -> None:
        self.log.debug("网关心跳已启动（间隔 %.1fs）", interval)
        while self._running and self._ws is not None and not self._ws.closed:
            try:
                await self._send_payload({"op": OP_HEARTBEAT, "d": self._last_seq})
            except Exception:  # noqa: BLE001 - 发送失败交给外层重连
                self.log.debug("发送心跳失败", exc_info=True)
                return
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------ 回调
    async def _safe_callback(self, callback: Callable[[dict], Any], payload: dict) -> None:
        try:
            if inspect.iscoroutinefunction(callback):
                await callback(payload)
            else:
                result = callback(payload)
                if inspect.isawaitable(result):
                    await result
        except Exception:  # noqa: BLE001 - 单个监听器异常不影响连接
            self.log.exception("网关事件回调执行失败")
