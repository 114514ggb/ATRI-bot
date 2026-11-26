"""连续重复工具调用检测

当模型在单轮工具循环中连续多次调用同一工具时(参数可以不同),
在该次工具结果末尾追加一次提示,要求其确认重复调用是否必要。

检测器由调用方(主聊天 ``LLMCoordinator.tool_calls_while`` 与 Agent
``SubAgentRunner``)各自持有一个实例,因此计数只在单轮对话内累计。
"""

from atribot.core.type.llm_message_types import ChatContent, TextContentPart

REPEAT_CALL_THRESHOLD = 3
"""连续调用同一工具的提示阈值"""


def build_repeat_hint(tool_name: str, streak: int) -> str:
    """构建注入给模型的重复调用提示文本

    Args:
        tool_name: 被重复调用的工具名
        streak: 当前连续调用次数

    Returns:
        str: 提示文本
    """
    return (
        "<repeat_tool_hint>"
        f"你已连续多次调用工具「{tool_name}」。"
        "请先确认继续调用是否必要:若已有结果足够完成任务,请立即停止调用工具并直接给出结论;"
        "若确实需要继续,请调整参数或换用其他方式,避免无意义的重复调用。"
        "</repeat_tool_hint>"
    )


def append_hint_to_output(content: ChatContent, hint: str) -> ChatContent:
    """把提示追加到工具结果尾部

    提示直接作为工具结果的一部分返回,不额外插入一条消息,
    因此不会打断 assistant tool_calls 与 tool 消息的对应关系。

    Args:
        content: 工具输出(纯文本或多模态内容段列表)
        hint: 提示文本

    Returns:
        ChatContent: 追加提示后的工具输出
    """
    if isinstance(content, str):
        return f"{content}\n\n{hint}" if content else hint

    text_part: TextContentPart = {"type": "text", "text": hint}
    return [*content, text_part]


class ToolRepeatGuard:
    """连续重复工具调用检测器

    每次工具调用后调用 :meth:`observe`;当同一工具连续出现
    ``threshold`` 次时返回提示文本,不要求参数完全相同。
    同一连续序列只提示一次;工具名发生变化即重置计数。
    """

    def __init__(self, threshold: int = REPEAT_CALL_THRESHOLD) -> None:
        """初始化检测器

        Args:
            threshold: 连续调用同一工具的提示阈值(至少为 2)
        """
        if threshold < 2:
            raise ValueError("threshold 必须大于等于 2")

        self.threshold: int = threshold
        self._last_tool: str | None = None
        self._streak: int = 0
        self._hinted: bool = False

    def observe(self, tool_name: str) -> str | None:
        """记录一次工具调用

        Args:
            tool_name: 工具名

        Returns:
            str | None: 达到阈值且本连续序列尚未提示时返回提示文本,否则返回 None
        """
        if tool_name == self._last_tool:
            self._streak += 1
        else:
            self._last_tool = tool_name
            self._streak = 1
            self._hinted = False

        if self._streak >= self.threshold and not self._hinted:
            self._hinted = True
            return build_repeat_hint(tool_name, self._streak)

        return None

    def reset(self) -> None:
        """重置检测状态(新的一轮工具循环开始时调用)"""
        self._last_tool = None
        self._streak = 0
        self._hinted = False
