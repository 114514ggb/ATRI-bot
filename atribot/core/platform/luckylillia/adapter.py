import logging
from typing import Any

from atribot.core.atri_config import (
    HttpAdapterConfig,
    PlatformInstanceConfig,
    WebSocketClientConfig,
    WebSocketServerConfig,
)
from atribot.core.platform import register_adapter
from atribot.core.platform.luckylillia.connection import LuckyLilliaWSClient
from atribot.core.platform.luckylillia.send import LuckyLilliaSendClient
from atribot.core.platform.message_queue import MessageQueue
from atribot.core.platform.onebot.adapter import OneBotAdapter
from atribot.core.platform.onebot.connection import OneBotHttpServer, OneBotWSServer
from atribot.core.platform.onebot.cqcode import cq_to_segments

__all__ = ["LuckyLilliaAdapter", "cq_to_segments"]


@register_adapter("luckylillia")
class LuckyLilliaAdapter(OneBotAdapter):
    """LuckyLilliaBot(LLBot) OneBot11 平台适配器

    与 NapCat 适配器共用事件解析、发送链路，仅覆写连接与发送客户端：
    LLBot 的正向 WS 只在根路径挂载 action/事件，且语音、文件无需额外 HTTP 端口。
    """

    def _build_connection(self) -> tuple[Any, str]:
        config = self._config
        if isinstance(config, WebSocketClientConfig):
            return (
                LuckyLilliaWSClient(
                    url=config.url,
                    access_token=config.access_token or None,
                    log=self._log.getChild("WSClient"),
                ),
                f"http://{config.url}",
            )
        if isinstance(config, WebSocketServerConfig):
            self._log.warning(
                "LLBot 适配器处于反向 WS 模式，请在 LLBot 的 OneBot11 反向 WS 中填写 ws://%s:%d",
                config.host,
                config.port,
            )
            return (
                OneBotWSServer(
                    host=config.host,
                    port=config.port,
                    access_token=config.access_token,
                    log=self._log.getChild("WSServer"),
                ),
                f"http://{config.host}:{config.port}",
            )
        if isinstance(config, HttpAdapterConfig):
            self._log.warning(
                "LLBot 适配器处于 HTTP 模式，需在 LLBot 中启用 OneBot11 的 HTTP POST(Webhook) 并把地址指向本机"
            )
            return (
                OneBotHttpServer(
                    host=config.host,
                    port=config.port,
                    access_token=config.access_token,
                    log=self._log.getChild("HttpServer"),
                ),
                config.url or f"http://127.0.0.1:{config.port}",
            )
        raise ValueError(
            f"不支持的连接类型: {config.connection_type} (平台: {self._source_name})"
        )

    def _build_send_client(self, http_base_url: str) -> LuckyLilliaSendClient:
        return LuckyLilliaSendClient(
            access_token=self._config.access_token or "",
            connection_type=self._config.connection_type,
            ws_connection=self._connection,
            source_name=self._source_name,
            log=self._log.getChild("Send"),
        )

    async def _normalize_event(self, data: dict) -> dict:
        """兼容 LLBot 的事件格式

        * ``message_format=string`` 时把 CQ 码文本转成消息段数组；
        * 其余（含 ``forward`` 段补全）复用基类逻辑。
        """
        message = data.get("message")
        if isinstance(message, str):
            data = dict(data)
            data["message"] = cq_to_segments(message)
            self._log.debug("收到的消息为 string 格式，已转换为 array")

        return await super()._normalize_event(data)
