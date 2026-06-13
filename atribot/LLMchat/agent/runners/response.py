"""Agent 运行时产出的事件 / 响应类型体系

定义了 Agent Runner 在 step() / run() 过程中通过 AsyncGenerator
产出的所有事件类型，覆盖流式增量、语义级事件、汇总结果和错误

流式模式(AgentData.kwargs["stream"] = True):
    step()  → TextDelta* → [ToolCallStart → ToolCallResult]* → StepSummary
    run()   → (step1: TextDelta* → ... → StepSummary) → ... → RunSummary

非流式模式(stream = False / 未设置):
    step()  → StepSummary
    run()   → RunSummary

Usage:
    from atribot.LLMchat.agent.runners.response import (
        AgentEvent, AgentEventType,
        TextDeltaChunk, ReasoningDeltaChunk, ToolCallStartChunk,
        ToolCallResultChunk, AgentStatusChunk,
        StepSummary, RunSummary, AgentError,
    )
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from atribot.LLMchat.LLM_supervisor import GenerationResponse


class AgentEventType(Enum):
    """Agent 事件类型枚举"""

    #流式中间事件
    TEXT_DELTA = auto()
    """文本增量"""
    REASONING_DELTA = auto()
    """思考过程增量"""     
    TOOL_CALL_START = auto()
    """工具调用开始"""
    TOOL_CALL_RESULT = auto()
    """工具调用结果"""
    AGENT_STATUS = auto()         
    """Agent 状态变更"""

    #汇总事件
    STEP_SUMMARY = auto()
    """单步汇总"""
    RUN_SUMMARY = auto()
    """多步最终汇总"""

    ERROR = auto()


@dataclass(slots=True)
class AgentEvent(ABC):
    """所有 Agent 运行时事件的抽象基类

    每个子类都携带 event_type 用于快速判别事件类别，
    并提供 to_dict() 用于序列化 / 日志记录
    """

    event_type: AgentEventType = field(init=False)
    """事件类型标识，由子类在 __post_init__ 或默认值中设定"""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict,便于跨进程 / 日志 / UI 消费"""
        return {"event_type": self.event_type.name}


@dataclass(slots=True)
class AgentStreamChunk(AgentEvent, ABC):
    """流式中间事件的抽象基类

    所有流式事件在 stream=True 时产出
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 确保子类不意外继承 event_type 默认值


@dataclass(slots=True)
class TextDeltaChunk(AgentStreamChunk):
    """文本增量 — 逐 token 产出的内容片段

    Attributes:
        delta: 本次增量文本(通常 1~若干 token)
        step_index: 当前步序号(多步模式下标识所属步骤)
    """

    delta: str
    step_index: int = 0
    event_type: AgentEventType = field(default=AgentEventType.TEXT_DELTA, init=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "delta": self.delta,
            "step_index": self.step_index,
        }


@dataclass(slots=True)
class ReasoningDeltaChunk(AgentStreamChunk):
    """思考过程增量 — 推理模型的思维链片段

    Attributes:
        delta: 本次思考增量文本
        step_index: 当前步序号
    """

    delta: str
    step_index: int = 0
    event_type: AgentEventType = field(default=AgentEventType.REASONING_DELTA, init=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "delta": self.delta,
            "step_index": self.step_index,
        }


@dataclass(slots=True)
class ToolCallStartChunk(AgentStreamChunk):
    """工具调用开始事件

    Attributes:
        tool_name: 工具名称
        tool_call_id: 工具调用唯一 ID
        arguments: 已解析的参数快照(可选，流式场景下可能不完整)
        step_index: 当前步序号
    """

    tool_name: str
    tool_call_id: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    step_index: int = 0
    event_type: AgentEventType = field(default=AgentEventType.TOOL_CALL_START, init=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "arguments": self.arguments,
            "step_index": self.step_index,
        }


@dataclass(slots=True)
class ToolCallResultChunk(AgentStreamChunk):
    """工具调用结果事件

    Attributes:
        tool_name: 工具名称
        tool_call_id: 工具调用唯一 ID
        result: 工具返回结果(文本或结构化数据)
        is_error: 工具执行过程中是否出错
        step_index: 当前步序号
    """

    tool_name: str
    tool_call_id: str
    result: Any
    is_error: bool = False
    step_index: int = 0
    event_type: AgentEventType = field(default=AgentEventType.TOOL_CALL_RESULT, init=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "result": str(self.result)[:2000],
            "is_error": self.is_error,
            "step_index": self.step_index,
        }


@dataclass(slots=True)
class AgentStatusChunk(AgentStreamChunk):
    """Agent 状态变更事件

    用于向前端 / 调用方报告当前正在做什么，例如：
    "正在规划...", "正在搜索...", "正在反思..."

    Attributes:
        status: 状态标识(如 "planning", "acting", "reflecting")
        message: 人类可读的状态描述
        step_index: 当前步序号
    """

    status: str
    message: str = ""
    step_index: int = 0
    event_type: AgentEventType = field(default=AgentEventType.AGENT_STATUS, init=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "status": self.status,
            "message": self.message,
            "step_index": self.step_index,
        }




@dataclass(slots=True)
class AgentSummary(AgentEvent, ABC):
    """汇总事件的抽象基类

    所有汇总事件是 Runner 产出的最终(或阶段性最终)结果，
    包含完整的回复内容、用量信息等
    """


@dataclass(slots=True)
class StepSummary(AgentSummary):
    """单步汇总 — step() 的最终产出，也是 run() 中每一步的阶段性结果

    Attributes:
        content: 本步完整回复文本
        reasoning_content: 完整思考过程(推理模型)
        tool_calls: 本步中调用的工具及结果列表
        usage: token 用量信息
        finish_reason: 结束原因("stop", "tool_calls", "length" 等)
        step_index: 步序号(单步模式固定为 0)
        is_final: 是否是多步运行的最终步
        metadata: 额外的元数据
    """

    content: str = ""
    reasoning_content: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    step_index: int = 0
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_type: AgentEventType = field(default=AgentEventType.STEP_SUMMARY, init=False)

    @property
    def has_content(self) -> bool:
        """是否有文本回复内容"""
        return bool(self.content)

    @property
    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return bool(self.tool_calls)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "content": self.content,
            "reasoning_content": self.reasoning_content,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "finish_reason": self.finish_reason,
            "step_index": self.step_index,
            "is_final": self.is_final,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class RunSummary(AgentSummary):
    """多步汇总 — run() 的最终产出

    Attributes:
        steps: 所有步骤的 StepSummary 列表
        total_content: 合并后的完整回复文本(所有步骤 content 拼接)
        total_reasoning: 合并后的完整思考过程
        total_usage: 总计 token 用量(prompt_tokens / completion_tokens / total_tokens)
        finish_reason: 最终结束原因
                        - "completed": 正常完成
                        - "max_turns": 达到最大轮次
                        - "error": 出错终止
                        - "stopped": 主动停止
        metadata: 额外元数据
    """

    steps: List[StepSummary] = field(default_factory=list)
    total_content: str = ""
    total_reasoning: Optional[str] = None
    total_usage: Optional[Dict[str, Any]] = None
    finish_reason: str = "completed"
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_type: AgentEventType = field(default=AgentEventType.RUN_SUMMARY, init=False)

    @property
    def step_count(self) -> int:
        """总步数"""
        return len(self.steps)

    @property
    def last_step(self) -> Optional[StepSummary]:
        """最后一步的汇总(便捷访问)"""
        return self.steps[-1] if self.steps else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "step_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
            "total_content": self.total_content,
            "total_reasoning": self.total_reasoning,
            "total_usage": self.total_usage,
            "finish_reason": self.finish_reason,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class AgentError(AgentSummary):
    """Agent 运行时错误汇总

    Attributes:
        error_message: 错误描述
        exception_type: 异常类型名
        partial_summary: 出错前已产出的部分结果(StepSummary 或 RunSummary)
        step_index: 错误发生在第几步
    """

    error_message: str
    exception_type: str = ""
    partial_summary: Optional[StepSummary | RunSummary] = None
    step_index: int = -1
    event_type: AgentEventType = field(default=AgentEventType.ERROR, init=False)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "event_type": self.event_type.name,
            "error_message": self.error_message,
            "exception_type": self.exception_type,
            "step_index": self.step_index,
        }
        if self.partial_summary is not None:
            result["partial_summary"] = self.partial_summary.to_dict()
        return result



def text_delta(delta: str, step_index: int = 0) -> TextDeltaChunk:
    """创建文本增量事件"""
    return TextDeltaChunk(delta=delta, step_index=step_index)


def reasoning_delta(delta: str, step_index: int = 0) -> ReasoningDeltaChunk:
    """创建思考增量事件"""
    return ReasoningDeltaChunk(delta=delta, step_index=step_index)


def tool_call_start(
    tool_name: str,
    tool_call_id: str,
    arguments: Optional[Dict[str, Any]] = None,
    step_index: int = 0,
) -> ToolCallStartChunk:
    """创建工具调用开始事件"""
    return ToolCallStartChunk(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        arguments=arguments or {},
        step_index=step_index,
    )


def tool_call_result(
    tool_name: str,
    tool_call_id: str,
    result: Any,
    is_error: bool = False,
    step_index: int = 0,
) -> ToolCallResultChunk:
    """创建工具调用结果事件"""
    return ToolCallResultChunk(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        result=result,
        is_error=is_error,
        step_index=step_index,
    )


def agent_status(status: str, message: str = "", step_index: int = 0) -> AgentStatusChunk:
    """创建 Agent 状态变更事件"""
    return AgentStatusChunk(status=status, message=message, step_index=step_index)


def step_summary(
    content: str = "",
    reasoning_content: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    usage: Optional[Dict[str, Any]] = None,
    finish_reason: Optional[str] = None,
    step_index: int = 0,
    is_final: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> StepSummary:
    """创建单步汇总事件"""
    return StepSummary(
        content=content,
        reasoning_content=reasoning_content,
        tool_calls=tool_calls or [],
        usage=usage,
        finish_reason=finish_reason,
        step_index=step_index,
        is_final=is_final,
        metadata=metadata or {},
    )


def run_summary(
    steps: Optional[List[StepSummary]] = None,
    total_content: str = "",
    total_reasoning: Optional[str] = None,
    total_usage: Optional[Dict[str, Any]] = None,
    finish_reason: str = "completed",
    metadata: Optional[Dict[str, Any]] = None,
) -> RunSummary:
    """创建多步最终汇总事件"""
    return RunSummary(
        steps=steps or [],
        total_content=total_content,
        total_reasoning=total_reasoning,
        total_usage=total_usage,
        finish_reason=finish_reason,
        metadata=metadata or {},
    )


def agent_error(
    error_message: str,
    exception_type: str = "",
    partial_summary: Optional[StepSummary | RunSummary] = None,
    step_index: int = -1,
) -> AgentError:
    """创建错误汇总事件"""
    return AgentError(
        error_message=error_message,
        exception_type=exception_type,
        partial_summary=partial_summary,
        step_index=step_index,
    )



def generation_response_to_step_summary(
    gen: GenerationResponse,
    step_index: int = 0,
    is_final: bool = False,
) -> StepSummary:
    """将 LLMCoordinator 的 GenerationResponse 转换为 Agent StepSummary

    用于在 Agent Runner 内部调用 LLMCoordinator.step() / run() 后，
    桥接 LLM 层的返回值到 Agent 事件体系

    Args:
        gen: LLM 层返回的 GenerationResponse
        step_index: 当前步序号
        is_final: 是否为最终步

    Returns:
        StepSummary: Agent 层的单步汇总
    """
    # 合并 reply_text 列表为完整回复
    content = "".join(gen.reply_text) if gen.reply_text else ""

    # 合并 reasoning_content 列表
    reasoning = "".join(gen.reasoning_content) if gen.reasoning_content else None

    # 从新增上下文中提取工具调用信息
    tool_calls: List[Dict[str, Any]] = []
    for msg in gen.messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": tc.get("function", {}).get("name", ""),
                    "arguments": tc.get("function", {}).get("arguments", ""),
                })
        elif msg.get("role") == "tool":
            # 找到对应的 tool call 条目并附加 result
            tool_call_id = msg.get("tool_call_id", "")
            content_str = msg.get("content", "")
            for tc in tool_calls:
                if tc["id"] == tool_call_id:
                    tc["result"] = content_str
                    tc["is_error"] = False
                    break
            else:
                tool_calls.append({
                    "id": tool_call_id,
                    "name": msg.get("name", ""),
                    "result": content_str,
                    "is_error": False,
                })

    return StepSummary(
        content=content,
        reasoning_content=reasoning,
        tool_calls=tool_calls,
        usage=gen.metadata if gen.metadata else None,
        finish_reason=gen.metadata.get("finish_reason") if gen.metadata else None,
        step_index=step_index,
        is_final=is_final,
    )



__all__ = [
    # 枚举
    "AgentEventType",
    # 基类
    "AgentEvent",
    "AgentStreamChunk",
    "AgentSummary",
    # 流式中间事件
    "TextDeltaChunk",
    "ReasoningDeltaChunk",
    "ToolCallStartChunk",
    "ToolCallResultChunk",
    "AgentStatusChunk",
    # 汇总事件
    "StepSummary",
    "RunSummary",
    "AgentError",
    # 工厂方法
    "text_delta",
    "reasoning_delta",
    "tool_call_start",
    "tool_call_result",
    "agent_status",
    "step_summary",
    "run_summary",
    "agent_error",
    # 桥接
    "generation_response_to_step_summary",
]
