from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from atribot.LLMchat.agent.message import BaseMessage, ToolMessage

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
        子类可自行决定被移除消息的处置方式（直接丢弃、或总结后插回上下文开头等）。

        Args:
            context: 待压缩的 Agent 对话上下文

        Returns:
            可选的被移除的消息列表；若无消息被移除则返回 None
        """
        ...


class DefaultCompressionStrategy(BaseCompressionStrategy):
    """默认上下文压缩策略：纯截断，不依赖任何外部服务

    基于消息数量和 Token 数量的双重阈值判断：
    - 消息数量超过 user_max_record 时触发（-1 表示不限制）
    - Token 数量超过 max_context_tokens * 0.8 时触发

    压缩方式：丢弃前半部分消息，并确保剩余部分的首条消息不是 ToolMessage
    （孤立的工具响应会让后续请求非法）。被丢弃的消息不保留总结。
    """

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
        """丢弃前半部分消息，并保证截断后的首条消息不是 ToolMessage"""
        removed_messages: List[BaseMessage] = []

        discard_count = len(context._messages) // 2

        for _ in range(discard_count):
            if context._messages:
                removed_messages.append(context._messages.popleft())

        # 截断后首条若是工具响应，说明其对应的调用已被丢弃，需继续向后弹出
        while context._messages and isinstance(context._messages[0], ToolMessage):
            removed_messages.append(context._messages.popleft())

        context.total_tokens = context.count_estimate_tokens()

        return removed_messages or None
