from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from atribot.core.type.bot_types import atriMessageEvent


class PipelineMiddleware(ABC):
    """预处理中间件抽象基类"""

    name: ClassVar[str] = ""
    """中间件名称，用于日志标识和动态移除"""

    async def initialize(self) -> None:
        """中间件初始化回调"""
        pass

    async def cleanup(self) -> None:
        """中间件清理回调"""
        pass

    @abstractmethod
    async def process(self, msg: atriMessageEvent) -> atriMessageEvent | None:
        """处理消息

        Args:
            msg: 待处理的消息信封

        Returns:
            Message  — 继续传递给下一中间件
            None     — 短路，丢弃此消息
        """
        ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"
