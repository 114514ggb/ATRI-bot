from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from atribot.core.pipeline.pipeline import Pipeline
    from atribot.core.type.bot_types import Message


class PipelineMiddleware(ABC):
    """预处理中间件抽象基类"""

    name: ClassVar[str] = ""
    """中间件名称，用于日志标识和动态移除"""

    async def on_setup(self, pipeline: Pipeline) -> None:
        """中间件挂载到 Pipeline 时的回调（可选覆写）

        Args:
            pipeline: 所属的 Pipeline 实例
        """
        pass

    @abstractmethod
    async def process(self, msg: Message) -> Message | None:
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
