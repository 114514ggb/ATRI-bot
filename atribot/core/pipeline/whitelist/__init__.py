from logging import Logger
from typing import TYPE_CHECKING, ClassVar

from atribot.core.atri_config import atriConfig
from atribot.core.cache.message_store import store_message_to_db
from atribot.core.pipeline.middleware import PipelineMiddleware
from atribot.core.service_container import container

if TYPE_CHECKING:
    from atribot.core.type.bot_types import atriMessageEvent


class WhitelistMiddleware(PipelineMiddleware):
    """群白名单预处理中间件

    检查消息来源群是否在白名单中，非白名单群的消息会被丢弃。
    但 root_user_id 可以绕过白名单限制（用于调试/管理）。
    """

    name: ClassVar[str] = "whitelist"

    def __init__(self) -> None:
        self._log: Logger = container.get_by_type(Logger).getChild("Whitelist")
        self._group_white_list: list[int] = []
        self._root_user_id: int = 0

    async def initialize(self) -> None:
        """初始化时从容器获取配置"""
        config: atriConfig = container.get_by_type(atriConfig)
        self._group_white_list = config.group_white_list
        self._root_user_id = config.root_user_id

    async def process(self, msg: atriMessageEvent) -> atriMessageEvent | None:
        """处理消息：白名单检查

        Args:
            msg: 待处理的消息信封

        Returns:
            msg  — 在白名单中或无需检查（私聊/通知/root,继续传递
            None — 不在白名单中，丢弃消息
        """
        if msg.group_id is None:
            return msg

        if msg.user_id == self._root_user_id:
            return msg

        if msg.group_id in self._group_white_list:
            self._log.debug("群相关事件:%s",msg.event.primeval)
            return msg

        await store_message_to_db(msg)#不在也存吧

        return None
