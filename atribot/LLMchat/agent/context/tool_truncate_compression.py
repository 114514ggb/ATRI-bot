from typing import TYPE_CHECKING, List, Optional, Sequence, Union

from atribot.LLMchat.agent.context.compression import BaseCompressionStrategy
from atribot.LLMchat.agent.message import (
    BaseMessage,
    MessageSegment,
    TextSegment,
    ToolMessage,
)

if TYPE_CHECKING:
    from atribot.LLMchat.agent.context.context import AgentContext


class ToolTruncateCompressionStrategy(BaseCompressionStrategy):
    """过长工具结果截断策略

    仅处理 ``ToolMessage``：当工具结果的文本长度超过 ``max_chars`` 时，
    保留前 ``head_chars`` 个字符与后 ``tail_chars`` 个字符，中间插入省略标记。

    - 字符串内容直接按字符切片
    - 消息段列表内容按所有 ``TextSegment`` 拼接后的文本坐标切片，非文本段
      （图片、音频等）原样保留且顺序不变
    - 截断后刷新消息缓存并重算上下文 Token，不删除任何消息

    该策略只做有损改写，因此 ``continues_chain`` 为 True：
    命中后仍需继续执行后续的总结/丢弃策略。
    """

    continues_chain = True

    def __init__(
        self,
        max_chars: int = 8000,
        head_chars: int = 3048,
        tail_chars: int = 1024,
    ) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars 必须为正整数")
        if head_chars < 0 or tail_chars < 0:
            raise ValueError("head_chars 与 tail_chars 不能为负数")
        if head_chars + tail_chars >= max_chars:
            raise ValueError("head_chars + tail_chars 必须小于 max_chars")

        self.max_chars = max_chars
        self.head_chars = head_chars
        self.tail_chars = tail_chars

    @property
    def name(self) -> str:
        return "tool_truncate"

    def should_compress(self, context: AgentContext) -> bool:
        """是否存在文本长度超过阈值的工具消息"""
        return any(
            self._text_length(msg.content) > self.max_chars
            for msg in context.messages
            if isinstance(msg, ToolMessage)
        )

    async def compress(self, context: AgentContext) -> Optional[List[BaseMessage]]:
        """截断超长工具消息内容，不删除消息"""
        changed = False

        for msg in context.messages:
            if not isinstance(msg, ToolMessage):
                continue

            truncated = self._truncate_content(msg.content)
            if truncated is None:
                continue

            msg.content = truncated
            msg.refresh_cache()
            changed = True

        if changed:
            context.total_tokens = context.count_estimate_tokens()

        return None

    @staticmethod
    def _text_length(content: Union[str, Sequence[MessageSegment]]) -> int:
        """统计内容中的文本字符数"""
        if isinstance(content, str):
            return len(content)
        return sum(
            len(segment.text)
            for segment in content
            if isinstance(segment, TextSegment)
        )

    @staticmethod
    def _marker(omitted: int) -> str:
        return f"\n\n...[已省略 {omitted} 个字符]...\n\n"

    def _truncate_content(
        self,
        content: Union[str, Sequence[MessageSegment]],
    ) -> Optional[Union[str, List[MessageSegment]]]:
        """返回截断后的内容；无需截断时返回 None"""
        text_length = self._text_length(content)
        if text_length <= self.max_chars:
            return None

        omitted = text_length - self.head_chars - self.tail_chars

        if isinstance(content, str):
            return (
                content[: self.head_chars]
                + self._marker(omitted)
                + content[text_length - self.tail_chars:]
            )

        return self._truncate_segments(content, text_length, omitted)

    def _truncate_segments(
        self,
        segments: Sequence[MessageSegment],
        text_length: int,
        omitted: int,
    ) -> List[MessageSegment]:
        """按拼接后的文本坐标截断消息段，非文本段原样保留"""
        tail_start = text_length - self.tail_chars
        marker = TextSegment(self._marker(omitted))
        marker_inserted = False

        result: List[MessageSegment] = []
        cursor = 0

        for segment in segments:
            if not isinstance(segment, TextSegment):
                result.append(segment)
                continue

            start = cursor
            end = start + len(segment.text)
            cursor = end

            head_end = min(end, self.head_chars)
            if start < head_end:
                result.append(TextSegment(segment.text[: head_end - start]))

            if not marker_inserted and end > self.head_chars and start < tail_start:
                result.append(marker)
                marker_inserted = True

            tail_begin = max(start, tail_start)
            if tail_begin < end:
                result.append(TextSegment(segment.text[tail_begin - start:]))

        return result
