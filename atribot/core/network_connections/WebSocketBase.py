from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional


class WebSocketBase(ABC):
    """WebSocket 连接基类"""

    @abstractmethod
    async def start(self) -> None:
        """启动连接"""
        ...

    @abstractmethod
    async def send(self, data: Dict, with_echo: bool = False) -> Optional[Dict]:
        """发送消息"""
        ...

    @abstractmethod
    def add_listener(self, callback: Callable[[Dict], Any]) -> None:
        """添加消息监听器"""
        ...

    @abstractmethod
    def remove_listener(self, callback: Callable[[Dict], Any]) -> None:
        """移除消息监听器"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """优雅关闭连接"""
        ...
