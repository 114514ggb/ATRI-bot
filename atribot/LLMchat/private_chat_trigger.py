from logging import Logger

from atribot.core.atri_config import atriConfig
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope
from atribot.core.type.chat_types import MessageAggregationWindow, WindowCloseReason
from atribot.LLMchat.chat import PrivateChat

PRIVATE_CHAT_WINDOW_SECONDS = 7.0  # 聚合窗口时长(秒),无新消息即触发回应
PRIVATE_CHAT_WINDOW_MAX_MESSAGES = 10  # 单批消息条数上限,达到即提前触发
PRIVATE_CHAT_FLOOD_INTERVAL = 0.3  # 极端刷屏判定阈值(秒),平均间隔低于此值直接不响应


class privateChatTrigger:
    """决定bot如何响应私聊消息(LLM私聊受白名单限制)

    白名单用户的私聊消息先进入聚合窗口,同一用户在窗口时间内
    连续发送的消息会被攒成一批,窗口关闭后一次性交给LLM回应
    """

    def __init__(self) -> None:
        self.log: Logger = container.get_by_type(Logger).getChild("PrivateChatTrigger")
        self.config: atriConfig = container.get_by_type(atriConfig)
        self.private_chat_white_list: list = self.config.all_config.get("private_chat_white_list", [])
        self.private_chat = container.get_by_type(PrivateChat)
        self.message_window: MessageAggregationWindow[MessageEventEnvelope] = MessageAggregationWindow(
            on_flush=self._flush_private_messages,
            window_seconds=PRIVATE_CHAT_WINDOW_SECONDS,
            max_buffer_size=PRIVATE_CHAT_WINDOW_MAX_MESSAGES,
        )

    async def decision(self, event: MessageEventEnvelope) -> bool:
        """私聊消息决策:是否交由LLM接管回复

        Args:
            event: 私聊消息信封(context_loader 已挂载 private_context)

        Returns:
            bool: True 表示消息已被聚合窗口接管,中断 EventBus 后续监听器
        """
        user_id: int = event.user_id

        #白名单外的用户不触发LLM私聊
        if not (user_id in self.private_chat_white_list or user_id == self.config.root_user_id):
            self.log.debug(f"用户{user_id}不在LLM私聊白名单内,跳过")
            return False

        private_context = event._extra.get("private_context")

        #极端刷屏防护
        if private_context and private_context.time_window.get_recent_avg_interval(4) < PRIVATE_CHAT_FLOOD_INTERVAL:
            self.log.info(f"用户{user_id}私聊消息发送异常频繁(疑似刷屏),跳过")
            return False

        self.message_window.add(user_id, event)
        return True

    async def _flush_private_messages(
        self,
        user_id: int,
        events: list[MessageEventEnvelope],
        reason: WindowCloseReason,
    ) -> None:
        """聚合窗口关闭回调:把整批消息交给LLM回应"""
        try:
            self.log.info(f"用户{user_id}私聊聚合窗口关闭({reason.value}),共{len(events)}条消息,触发LLM回应")
            prompt = "用户在私聊中给你发送了新消息,你们正在进行一对一的对话"
            if len(events) > 1:
                prompt += (
                    "这些消息是用户在短时间内连续发送的,可能是同一段话分成多条,请综合理解后作为整体回应"
                    "用户可能还没说完,若感觉话未说完可保持沉默等待下一条"
                )
            await self.private_chat.step(events=events, prompt=prompt)
        except Exception:
            self.log.exception(f"用户{user_id}私聊聚合回调执行失败")
