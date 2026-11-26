import asyncio
import json
import logging
from asyncio import CancelledError, sleep
from typing import Optional
from urllib.parse import quote

from websockets.exceptions import ConnectionClosed, InvalidStatusCode
from websockets.legacy.client import connect as ws_connect

from atribot.core.platform.onebot.connection import OneBotWSClient


class LuckyLilliaWSClient(OneBotWSClient):
    """LuckyLilliaBot(LLBot) OneBot11 正向 WS 客户端

    与 NapCat 实现的主要差异：

    * **路径**：LLBot 只在 ``/``、``/api``、``/event`` 上挂载 action 与事件推送，
      NapCat 常用的 ``/websocket`` 在 LLBot 上会得到一条“握手成功但收不到任何事件”
      的连接，因此这里固定连接 ``/``（同一路径同时支持 action 与事件）。
    * **鉴权**：LLBot 支持 ``?access_token=`` 查询参数和 ``Authorization: Bearer``，
      这里使用查询参数，避免额外维护 header。
    * **重连**：token 错误时 LLBot 会先回 1403 再以 1008 断开，
      需要指数退避 + 明确提示，避免每秒重连刷屏。
    """

    def __init__(
        self,
        url: str = "127.0.0.1:3001",
        access_token: Optional[str] = None,
        retry_delay: float = 2.0,
        max_retries: Optional[int] = None,
        echo_timeout: float = 15.0,
        log: logging.Logger | None = None,
    ):
        super().__init__(
            url=url,
            access_token=access_token,
            max_retries=0,
            retry_delay=retry_delay,
            echo_timeout=echo_timeout,
            log=log,
        )
        self._max_retries = max_retries
        self._auth_warned = False

    def _target(self) -> str:
        """日志用的目标地址（不含 token）"""
        raw = (self.url or "").strip()
        if "://" in raw:
            raw = raw.split("://", 1)[1]
        return raw.split("/", 1)[0].split("?", 1)[0]

    def _build_uri(self) -> str:
        """构建 WebSocket URI（固定根路径 + access_token 查询参数）"""
        raw = (self.url or "").strip()
        scheme = "ws"
        if "://" in raw:
            scheme, raw = raw.split("://", 1)
            scheme = scheme.lower()
            if scheme not in ("ws", "wss"):
                scheme = "ws"
        netloc = raw.split("/", 1)[0].split("?", 1)[0]
        uri = f"{scheme}://{netloc}/"
        if self.access_token:
            uri += f"?access_token={quote(self.access_token, safe='')}"
        self.log.debug(
            "目标 URI: %s",
            uri.replace(self.access_token, "***") if self.access_token else uri,
        )
        return uri

    def _next_delay(self) -> float:
        """指数退避，上限 30 秒"""
        backoff = self.retry_delay * (2 ** min(max(self._retry_count - 1, 0), 4))
        return min(backoff, 30.0)

    async def _connect(self) -> None:
        """连接 LLBot，失败时按指数退避无限重试"""
        while self._running:
            if self._max_retries is not None and self._retry_count >= self._max_retries:
                self.log.error("连接失败，已达最大重试次数 %d 次", self._max_retries)
                return
            try:
                self.websocket = await ws_connect(
                    self._build_uri(),
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                )
                self.log.info("WebSocket 连接成功: %s", self._target())
                self._retry_count = 0
                self._auth_warned = False
                self._connected.set()
                return
            except InvalidStatusCode as e:
                self._retry_count += 1
                self._connected.clear()
                delay = self._next_delay()
                if e.status_code in (401, 403):
                    self.log.error(
                        "LLBot 拒绝了连接(HTTP %s)：请检查配置中的 access_token 是否与 LLBot 的 Token 一致",
                        e.status_code,
                    )
                else:
                    self.log.warning("握手失败(HTTP %s): %s, %.1f 秒后重试", e.status_code, e, delay)
                await sleep(delay)
            except CancelledError:
                raise
            except Exception as e:
                self._retry_count += 1
                self._connected.clear()
                delay = self._next_delay()
                self.log.warning(
                    "连接失败 (第%d次): %s, %.1f 秒后重试...",
                    self._retry_count, e, delay,
                )
                await sleep(delay)

    async def _receive_messages(self) -> None:
        """接收事件/回包，断线后退避重连"""
        while self._running:
            try:
                if not self.websocket:
                    await self._connected.wait()
                    continue

                data = json.loads(await self.websocket.recv())

                # action 回包
                if isinstance(data, dict) and data.get("echo"):
                    future = self.pending_requests.pop(data["echo"], None)
                    if future and not future.done():
                        future.set_result(data)
                    continue

                # 无 echo 的主动错误（如 token 校验失败）
                if isinstance(data, dict) and "post_type" not in data and "retcode" in data:
                    self.log.error(
                        "LLBot 返回错误: retcode=%s message=%s",
                        data.get("retcode"),
                        data.get("message") or data.get("wording") or data.get("msg"),
                    )
                    continue

                # echo 只能由本循环读取，事件交给独立任务分发
                await self._enqueue_event(data)

            except json.JSONDecodeError as e:
                self.log.error("JSON 解析错误: %s", e)
            except ConnectionClosed as e:
                self._connected.clear()
                if not self._running:
                    break
                if e.code == 1008:
                    if not self._auth_warned:
                        self.log.error(
                            "LLBot 主动断开连接(code=1008)，通常是 access_token 与 LLBot 配置不一致: %s",
                            e.reason,
                        )
                        self._auth_warned = True
                else:
                    self.log.warning("WebSocket 连接断开: code=%s %s", e.code, e.reason)
                await self._reconnect()
            except CancelledError:
                raise
            except Exception as e:
                self.log.error("接收消息时发生错误: %s", e)
                self._connected.clear()
                if self._running:
                    await self._reconnect()

    async def _reconnect(self) -> None:
        self._retry_count += 1
        delay = self._next_delay()
        self.log.info("正在重新连接 (%.1f 秒后)...", delay)
        await sleep(delay)
        if self._running:
            await self._connect()

    async def wait_for_connection(self, timeout: Optional[float] = None) -> bool:
        """等待连接建立

        Args:
            timeout: 超时时间(秒)，None 表示无限等待

        Returns:
            是否在超时前成功连接
        """
        try:
            if timeout is not None:
                await asyncio.wait_for(self._connected.wait(), timeout=timeout)
            else:
                await self._connected.wait()
            return True
        except asyncio.TimeoutError:
            return False
