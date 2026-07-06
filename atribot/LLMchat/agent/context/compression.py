from __future__ import annotations

from abc import ABC, abstractmethod
from logging import Logger
from typing import TYPE_CHECKING, List, Optional

from atribot.core.service_container import container
from atribot.LLMchat.agent.message import AssistantMessage, BaseMessage, UserMessage
from atribot.LLMchat.memory.memory_system import MemorySystem

if TYPE_CHECKING:
    from atribot.LLMchat.agent.context.context import AgentContext


class BaseCompressionStrategy(ABC):
    """上下文压缩策略抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称，用于日志追踪和调试"""
        ...

    @abstractmethod
    def should_compress(self, context: AgentContext) -> bool:
        """判断是否需要对该上下文执行压缩

        Args:
            context: 待检查的 Agent 对话上下文

        Returns:
            True 表示需要压缩,False 表示跳过
        """
        ...

    @abstractmethod
    async def compress(self, context: AgentContext) -> Optional[List[BaseMessage]]:
        """对上下文执行压缩操作

        该方法会直接修改传入的 context。
        子类实现应负责：压缩消息、对移除的消息进行总结、将总结插入上下文开头。

        Args:
            context: 待压缩的 Agent 对话上下文

        Returns:
            可选的被移除的消息列表；若无消息被移除则返回 None
        """
        ...


class DefaultCompressionStrategy(BaseCompressionStrategy):
    """默认上下文压缩策略

    基于消息数量和 Token 数量的双重阈值判断：
    - 消息数量超过 user_max_record 时触发
    - Token 数量超过 compression_threshold * max_context_tokens 时触发

    压缩方式：丢弃前半部分消息，并确保剩余部分首条消息为 UserMessage
    """

    def __init__(self):
        super().__init__()
        self.log: Logger = container.get_by_type(Logger).getChild("AgentCtx")
        self.memory_system = container.get_by_type(MemorySystem)


    @property
    def name(self) -> str:
        return "default"

    def should_compress(self, context: AgentContext) -> bool:
        """双重条件判断：消息数超限 或 Token 数超过阈值百分比"""
        trigger_by_count = (
            context.user_max_record != -1
            and len(context._messages) > context.user_max_record
        )
        trigger_by_tokens = (
            context.total_tokens
            > (context.max_context_tokens * 0.8)
        )
        return trigger_by_count or trigger_by_tokens

    async def compress(self, context: AgentContext) -> Optional[List[BaseMessage]]:
        """丢弃前半部分消息，确保首条为 UserMessage,并对被移除的消息进行总结后插入上下文开头"""
        removed_messages: List[BaseMessage] = []

        discard_count = len(context._messages) // 2

        for _ in range(discard_count):
            if context._messages:
                removed_messages.append(context._messages.popleft())

        # 确保截断后的首条消息为 UserMessage，不满足则继续向后弹出
        while context._messages and not isinstance(context._messages[0], UserMessage):
            removed_messages.append(context._messages.popleft())

        # 对被移除的消息进行总结并插入到上下文开头
        if removed_messages:
            try:
                removed_text = "\n".join(
                    str(msg.to_openai_dict()) for msg in removed_messages
                )
                if summarize_text := await self.memory_system.summarize_context(removed_text):
                    context._messages.appendleft(
                        AssistantMessage(content=summarize_text[:3000])
                    )
                    self.log.info(
                        f"Agent上下文总结完成, 压缩 {len(removed_messages)} 条消息"
                        f" 为 {len(summarize_text)} 字符的摘要"
                    )
                else:
                    self.log.info("Agent上下文总结返回为空, 跳过摘要插入")
            except Exception as e:
                self.log.exception(f"Agent上下文总结出现错误: {e}")

        context.total_tokens = context.count_estimate_tokens()

        return removed_messages
