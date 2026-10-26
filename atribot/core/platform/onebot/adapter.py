import asyncio
import json
import logging
from typing import Any

from atribot.core.atri_config import (
    HttpAdapterConfig,
    PlatformInstanceConfig,
    WebSocketClientConfig,
    WebSocketServerConfig,
)
from atribot.core.platform import register_adapter
from atribot.core.platform.base import PlatformAdapter
from atribot.core.platform.message_queue import MessageQueue
from atribot.core.platform.onebot.connection import OneBotHttpServer, OneBotWSClient, OneBotWSServer
from atribot.core.platform.onebot.message_event import OneBotMessageEvent
from atribot.core.platform.onebot.send import OneBotSendClient
from atribot.core.platform.send_client import LoginInfo
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import SendMessage
from atribot.core.type.onebot_event_types import OneBotEvent


@register_adapter("onebot")
class OneBotAdapter(PlatformAdapter):
    """OneBot 协议平台适配器

    子类可通过以下类属性替换实现细节，无需重写构造流程：
        _log_name: 日志子名
        _message_event_cls: 事件信封类型
        _send_client_cls: 发送客户端类型
        _default_ws_path: 正向 WS 默认路径（None 沿用 NapCat 的 /websocket 逻辑）
    """

    _log_name: str = "OneBotAdapter"
    _message_event_cls: type[OneBotMessageEvent] = OneBotMessageEvent
    _send_client_cls: type[OneBotSendClient] = OneBotSendClient
    _default_ws_path: str | None = None

    def __init__(
        self,
        config: PlatformInstanceConfig,
        queue: MessageQueue,
    ):
        self._config = config
        self._queue = queue
        self._source_name = config.source_name
        self._log = container.get_by_type(logging.Logger).getChild(f"{self._log_name}.{config.source_name}")
        self._started = False

        if isinstance(config, WebSocketClientConfig):
            self._connection = OneBotWSClient(
                url=config.url,
                access_token=config.access_token,
                log=self._log.getChild("WSClient"),
                path=config.ws_path or self._default_ws_path,
            )
            http_base_url = f"http://{config.url}".rstrip("/")
        elif isinstance(config, WebSocketServerConfig):
            self._connection = OneBotWSServer(
                host=config.host,
                port=config.port,
                access_token=config.access_token,
                log=self._log.getChild("WSServer"),
            )
            http_base_url = f"http://{config.host}:{config.port}".rstrip("/")
        elif isinstance(config, HttpAdapterConfig):
            self._connection = OneBotHttpServer(
                host=config.host,
                port=config.port,
                access_token=config.access_token,
                log=self._log.getChild("HttpServer"),
            )
            http_base_url = (config.url or "").rstrip("/")
        else:
            raise ValueError(
                f"不支持的连接类型: {config.connection_type} "
                f"(平台: {self._source_name})"
            )
        self._send_client = self._send_client_cls(
            access_token=config.access_token or "",
            http_base_url=http_base_url,
            connection_type=config.connection_type,
            ws_connection=self._connection,
            log=self._log.getChild("Send"),
        )

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def is_connected(self) -> bool:
        return bool(getattr(self._connection, "is_connected", False))

    def get_connection_info(self) -> dict[str, Any]:
        """返回连接运行状态快照（供状态查询命令 / 面板展示）"""
        return {
            "adapter": type(self).__name__,
            "is_started": self._started,
            "is_running": bool(getattr(self._connection, "is_running", False)),
            "is_connected": self.is_connected,
            "retry_count": getattr(self._connection, "retry_count", None),
        }


    async def start(self) -> None:
        """启动适配器：注册消息回调 → 启动连接(WS / HTTP)"""
        if self._started:
            return

        self._connection.add_listener(self._on_raw_message)
        self._log.info(
            "正在连接 (type=%s, source=%s, target=%s)",
            self._config.connection_type,
            self._source_name,
            getattr(self._config, "url", f"{getattr(self._config, 'host', '?')}:{getattr(self._config, 'port', '?')}"),
        )

        self._conn_task = asyncio.create_task(self._connection.start())
        self._started = True

        if hasattr(self._connection, "wait_for_connection"):
            if await self._connection.wait_for_connection(timeout=5.0):
                self._log.info("连接已建立")
            else:
                self._log.warning("连接尚未建立（等待重连 / 客户端接入）")
        else:
            self._log.info("已启动（监听中）")

    async def stop(self) -> None:
        """停止适配器"""
        if not self._started:
            return

        self._log.info("正在停止...")
        try:
            self._connection.remove_listener(self._on_raw_message)
        except (ValueError, Exception) as e:
            self._log.warning("移除监听器时出错: %s", e)

        await self._connection.close()
        await self._send_client.close()
        self._started = False
        self._log.info("已停止")

    async def send(self, message: SendMessage) -> Any:
        """发送消息到 OneBot 平台

        Args:
            message: 已构建好的 GroupMessage 或 PrivateMessage

        Returns:
            API 响应，或 None
        """
        return await self._send_client.send(message)

    def get_client(self) -> object:
        """获取 OneBotSendClient 实例"""
        return self._send_client

    async def call_api(self, action: str, params: dict) -> Any:
        """通用 OneBot API 调用

        直接调用任意 OneBot API 动作

        Args:
            action: API 动作名称
            params: 请求参数字典

        Returns:
            API 响应，或 None
        """
        return await self._send_client.async_send(action, params)

    async def get_login_info(self) -> LoginInfo | None:
        """获取当前登录帐号的信息"""
        return await self._send_client.get_login_info()

    async def _on_raw_message(self, data: dict) -> None:
        """收到原始 OneBot 事件后的回调(WS / HTTP)

        将原始事件字典转换为类型化的 Message 并推入队列
        """
        # self._log.debug(f"事件:{data}")
        try:
            event = OneBotEvent.from_dict(data)
        except (ValueError, Exception) as e:
            self._log.warning(
                "事件解析失败: %s | raw=%s",
                e,
                json.dumps(data, ensure_ascii=False)[:200],
            )
            return

        msg = self._message_event_cls(
            event=event,
            source=self._source_name,
            direction="incoming",
            send_client=self._send_client,
        )
        pushed = await self._queue.push(msg)

        if not pushed:
            self._log.warning(
                "❌ 消息未能入队(队列满): %s post_type=%s",
                type(event).__name__,
                event.post_type.value,
            )

