from abc import ABC, abstractmethod
from typing import Any

from atribot.core.type.chat_message_types import SendMessage


class PlatformAdapter(ABC):
    """平台适配器抽象基类"""

    @abstractmethod
    async def start(self) -> None:
        """建立与平台服务的连接，开始监听事件

        实现时：
        1. 建立连接(WebSocket / HTTP 等
        2. 注册原始消息回调，回调中将数据转为 OneBotEvent → Message
        3. 将 Message 推入 Platform 层的 MessageQueue
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """断开连接，清理资源"""
        ...

    @abstractmethod
    async def send(self, message: SendMessage, echo: bool = False) -> Any:
        """发送消息到平台

        Args:
            message: 已构建好的消息对象 (GroupMessage / PrivateMessage)
            echo: 是否等待并返回发送结果

        Returns:
            平台响应(echo=True 时返回响应结果)
        """
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """平台来源标识

        用于填充 Message.source 字段，如 "napcat"、"llonebot"、"telegram"
        """
        ...
