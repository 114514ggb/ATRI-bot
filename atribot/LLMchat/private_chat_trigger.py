from logging import Logger

from atribot.core.atri_config import atriConfig
from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope
from atribot.LLMchat.chat import PrivateChat


class privateChatTrigger:
    """决定bot如何响应私聊消息(LLM私聊受白名单限制)"""

    def __init__(self) -> None:
        self.log: Logger = container.get_by_type(Logger).getChild("PrivateChatTrigger")
        self.config: atriConfig = container.get_by_type(atriConfig)
        self.blacklist = container.get_by_type(PermissionsManagement).blacklist
        self.private_chat_white_list:list = self.config.all_config.get("private_chat_white_list", [])
        self.private_chat = container.get_by_type(PrivateChat)

    def _in_white_list(self, user_id: int) -> bool:
        """LLM私聊白名单检查,root用户可绕过

        Args:
            user_id: 私聊用户的QQ号

        Returns:
            是否允许触发LLM私聊
        """
        return user_id in self.private_chat_white_list or user_id == self.config.root_user_id

    async def decision(self, event: MessageEventEnvelope) -> bool:
        """私聊消息决策:是否交由LLM接管回复

        Args:
            event: 私聊消息信封(context_loader 已挂载 private_context)

        Returns:
            bool: True 表示已处理,中断 EventBus 后续监听器
        """
        user_id: int = event.user_id

        #黑名单用户不响应
        if user_id in self.blacklist:
            return False

        #白名单外的用户不触发LLM私聊
        if not self._in_white_list(user_id):
            self.log.debug(f"用户{user_id}不在LLM私聊白名单内,跳过")
            return False

        private_context = event._extra.get("private_context")

        #消息间隔过低时大概率是用户在连续分段输入,本轮不触发,留给下一条一起回应
        if private_context and private_context.time_window.get_recent_avg_interval(4) < 1:
            self.log.info(f"用户{user_id}私聊消息发送过快,本轮不响应")
            return False

        self.log.info(f"用户{user_id}触发LLM私聊")
        await self.private_chat.step(
            event=event,
            prompt=(
                "用户在私聊中给你发送了新消息,你们正在进行一对一的对话,正常情况下请积极回复用户。"
                "注意用户可能正在分段输入,要是感觉用户的话还没说完,可以保持沉默等待下一条消息再一起回应"
            ),
        )
        return True
