from abc import ABC, abstractmethod
from typing import Any

from atribot.core.platform.send_client import LoginInfo
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
    async def send(self, message: SendMessage) -> Any:
        """发送消息到平台

        Args:
            message: 已构建好的消息对象 (GroupMessage / PrivateMessage)

        Returns:
            平台响应结果
        """
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """平台来源标识

        用于填充 Message.source 字段，如 "napcat"、"llonebot"、"telegram"
        """
        ...

    @abstractmethod
    def get_client(self) -> object:
        """获取平台的底层客户端对象

        返回平台原生客户端对象（如 OneBotSendClient
        用于调用平台特有方法。调用方应使用 isinstance 检查类型后再调用。

        Returns:
            平台客户端对象，具体类型由子类决定
        """
        ...

    @property
    def is_connected(self) -> bool:
        """连接是否已建立（子类按需覆写）"""
        return False

    def get_connection_info(self) -> dict[str, Any]:
        """返回连接运行状态快照，用于状态查询命令 / 面板展示

        子类可覆写以补充连接细节（如重连次数）。

        Returns:
            状态字典，至少包含 is_connected 字段
        """
        return {"is_connected": self.is_connected}

    async def call_api(self, action: str, params: dict) -> Any:
        """通用 API 调用

        当平台特有操作未在客户端对象中暴露时，
        可直接通过 action 字符串调用底层 API。

        子类可按需覆写此方法以实现具体的 API 调用逻辑。

        Args:
            action: API 动作名称（如 "set_group_ban"
            params: 请求参数字典

        Returns:
            API 响应，或 None
        """
        raise NotImplementedError(
            f"{type(self).__name__} 未实现 call_api()"
        )

    async def get_login_info(self) -> LoginInfo | None:
        """获取当前登录帐号的信息

        子类按需覆写；未实现时返回 None
        """
        return None
