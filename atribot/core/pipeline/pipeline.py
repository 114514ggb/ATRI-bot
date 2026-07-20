from logging import Logger
from typing import TYPE_CHECKING

from atribot.core.service_container import container

if TYPE_CHECKING:
    from atribot.core.pipeline.middleware import PipelineMiddleware
    from atribot.core.type.bot_types import Message


class Pipeline:
    """预处理管道（责任链模式）"""

    def __init__(self) -> None:
        self._middlewares: list[PipelineMiddleware] = []
        self._log: Logger = container.get_by_type(Logger).getChild("Pipeline")

    def add_middleware(self, mw: PipelineMiddleware) -> Pipeline:
        """追加中间件到链尾

        Args:
            mw: 中间件实例

        Returns:
            self,支持链式调用
        """
        self._middlewares.append(mw)
        self._log.debug("添加中间件: %s", mw)
        return self

    def remove_middleware(self, name: str) -> PipelineMiddleware | None:
        """按名称移除中间件

        Args:
            name: 中间件的 name 属性值

        Returns:
            被移除的中间件实例，未找到返回 None
        """
        for i, mw in enumerate(self._middlewares):
            if mw.name == name:
                del self._middlewares[i]
                self._log.debug("移除中间件: %s", mw)
                return mw
        return None

    async def process(self, msg: Message) -> Message | None:
        """链式处理消息

        Args:
            msg: 待处理的消息信封

        Returns:
            Message  — 通过全部中间件
            None     — 被某个中间件短路丢弃
        """
        for mw in self._middlewares:
            if msg := await mw.process(msg):
                return msg
            self._log.debug("中间件 %s 短路，丢弃消息", mw)
            return None

    @property
    def middleware_count(self) -> int:
        """当前中间件数量"""
        return len(self._middlewares)

    @property
    def middlewares(self) -> tuple[PipelineMiddleware, ...]:
        """当前中间件列表"""
        return tuple(self._middlewares)

    def __repr__(self) -> str:
        names = [mw.name or type(mw).__name__ for mw in self._middlewares]
        return f"Pipeline({' → '.join(names) if names else '(empty)'})"
