import asyncio
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional, Union

from atribot.common_utils.message_utils import count_estimate_tokens
from atribot.LLMchat.agent.context.compression import (
    BaseCompressionStrategy,
    DefaultCompressionStrategy,
)
from atribot.LLMchat.agent.message import (
    AssistantMessage,
    BaseMessage,
    MessageSegment,
    SystemMessage,
    ToolMessage,
    UserMessage,
)


@dataclass(slots=True)
class BaseContext(ABC):
    """对话上下文基类"""
    
    @property
    @abstractmethod
    def messages(self) -> Iterable[BaseMessage]:
        """上下文消息集合

        Returns:
            Iterable[BaseMessage]: 消息集合
        """
        ...
    
    @abstractmethod
    def extend(self, messages: Iterable[BaseMessage]) -> None:
        """扩展多条实例化的消息

        Args:
            messages (Iterable[BaseMessage]): 消息集合
        """
        ...

    @abstractmethod
    def copy(self) -> BaseContext:
        """创建当前上下文的副本

        Returns:
            BaseContext: 当前上下文的新副本
        """
        ...

    def extend_from_context(self, other: BaseContext) -> BaseContext:
        """将另一个上下文的消息合并到当前上下文的副本中，返回新的上下文

        Args:
            other (BaseContext): 另一个上下文对象

        Returns:
            BaseContext: 合并后的新上下文
        """
        new_context = self.copy()
        new_context.extend(other.messages)
        return new_context

    def to_openai_list(self) -> List[Dict[str, Any]]:
        """转换为 OpenAI 兼容的上下文列表

        Returns:
            List[Dict[str, Any]]: OpenAI 格式的消息列表
        """
        return [msg.to_openai_dict() for msg in self.messages]


@dataclass(slots=True)
class AgentContext(BaseContext):
    """Agent专用对话上下文"""

    _messages: Deque[BaseMessage] = field(default_factory=deque)
    """内部的上下文集合"""

    user_max_record: int = -1
    """消息总的长度限制（-1 表示不限制）"""

    max_output_tokens: int = 32768
    """模型输出的最大 Token 长度"""

    max_context_tokens: int = 128000
    """最大允许的上下文 Token 长度"""

    play_role: str = ""
    """对话开头模型人物提示词(System Content)
    对话中固定不变的部分
    """

    total_tokens: int = 0
    """当前上下文已占用的 Token 数量"""

    async_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """异步锁"""

    compression_strategies: List[BaseCompressionStrategy] = field(
        default_factory=lambda: [DefaultCompressionStrategy()]
    )
    """压缩策略链（责任链模式），按顺序遍历，首个命中即停止"""

    def __post_init__(self):
        if self._messages is None:
            self._messages = deque()
        elif isinstance(self._messages, list):
            self._messages = deque(self._messages)
        if self.compression_strategies is None:
            self.compression_strategies = [DefaultCompressionStrategy()]

    @property
    def messages(self) -> Deque[BaseMessage]:
        return self._messages

    def __getitem__(self, index):
        return self._messages[index]

    def __len__(self):
        return len(self._messages)

    def __iter__(self):
        return iter(self._messages)

    def __contains__(self, item):
        return item in self._messages

    def __reversed__(self):
        return reversed(self._messages)

    def append(self, message: BaseMessage) -> None:
        """追加一条实例化的消息

        Args:
            message (BaseMessage): 消息实体
        """
        self._messages.append(message)

    def extend(self, messages: Iterable[BaseMessage]) -> None:
        """扩展多条实例化的消息

        Args:
            messages (Iterable[BaseMessage]): 消息集合
        """
        self._messages.extend(messages)

    def copy(self) -> AgentContext:
        """创建当前上下文的副本

        Returns:
            AgentContext: 当前上下文的新副本
        """
        return AgentContext(
            _messages=deque(self._messages),
            user_max_record=self.user_max_record,
            max_output_tokens=self.max_output_tokens,
            max_context_tokens=self.max_context_tokens,
            play_role=self.play_role,
            total_tokens=self.total_tokens,
            compression_strategies=list(self.compression_strategies),
        )

    def clear(self) -> None:
        """清空上下文"""
        self._messages.clear()

    def to_openai_list(self) -> List[Dict[str, Any]]:
        """获取结构化并序列化的 OpenAI Context 列表格式

        Returns:
            List[Dict[str, Any]]: OpenAI 格式的消息列表
        """
        res = []
        if self.play_role:
            res.append({"role": "system", "content": self.play_role})
        
        for msg in self._messages:
            res.append(msg.to_openai_dict())

        return res

    def add_user_message(self, content: Union[str, List[MessageSegment]]) -> None:
        """快捷添加用户消息

        Args:
            content (Union[str, List[MessageSegment]]): 消息内容
        """
        self._messages.append(UserMessage(content=content))

    def add_assistant_message(
        self,
        content: Optional[str] = None,
        reasoning_content: Optional[str] = None,
        extra_content: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """快捷添加助手消息

        Args:
            content (Optional[str]): 助手消息内容
            reasoning_content (Optional[str]): 模型思考内容
            extra_content (Optional[Dict[str, Any]]): 兼容字段
            tool_calls (Optional[List[Dict[str, Any]]]): 工具调用信息
        """
        self._messages.append(
            AssistantMessage(
                content=content,
                reasoning_content=reasoning_content,
                extra_content=extra_content,
                tool_calls=tool_calls
            )
        )

    def add_system_message(self, content: str) -> None:
        """快捷添加系统消息

        Args:
            content (str): 系统消息内容
        """
        self._messages.append(SystemMessage(content=content))

    def add_tool_message(self, name: str, tool_call_id: str, content: Union[str, List[MessageSegment]]) -> None:
        """快捷添加工具响应消息

        Args:
            name (str): 工具名称
            tool_call_id (str): 工具调用 ID
            content (Union[str, List[MessageSegment]]): 工具返回内容
        """
        self._messages.append(ToolMessage(name=name, tool_call_id=tool_call_id, content=content))

    async def record_validity_check(self, current_tokens: Optional[int] = None) -> Optional[List[BaseMessage]]:
        """
        遍历压缩策略链，对上下文进行验证与压缩

        Args:
            current_tokens (Optional[int]): 当前上下文 Token 长度，若未指定则通过估算自动获取

        Returns:
            Optional[List[BaseMessage]]: 被移除的消息列表。若未触发压缩则返回 None
        """
        if current_tokens is not None:
            self.total_tokens = current_tokens
        else:
            self.total_tokens = self.count_estimate_tokens()

        for strategy in self.compression_strategies:
            if strategy.should_compress(self):
                return await strategy.compress(self)

        return None

    def is_dangerous(self) -> bool:
        """
        检查当前上下文是否处于危险状态。
        即当前上下文 Token 长度加上输出的最大 Token 长度是否超过最大上下文长度。

        Returns:
            bool: 处于危险状态返回 True,否则返回 False。
        """
        return (self.total_tokens + self.max_output_tokens) > self.max_context_tokens

    def count_estimate_tokens(self) -> int:
        """
        获取上下文 Token 估算值

        Returns:
            int: 估算的 token 数量
        """
        return count_estimate_tokens(self.to_openai_list())