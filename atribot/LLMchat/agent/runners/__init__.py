"""Agent Runner 与响应事件类型

提供 BaseAgentRunner 抽象基类及完整的 Agent 事件 / 响应类型体系。

Usage:
    from atribot.LLMchat.agent.runners import (
        BaseAgentRunner, AgentState,
        AgentEvent, AgentEventType,
        TextDeltaChunk, ReasoningDeltaChunk,
        ToolCallStartChunk, ToolCallResultChunk, AgentStatusChunk,
        StepSummary, RunSummary, AgentError,
        text_delta, step_summary, run_summary, agent_error,
        generation_response_to_step_summary,
    )
"""

from atribot.LLMchat.agent.runners.base_runner import AgentState, BaseAgentRunner
from atribot.LLMchat.agent.runners.response import (
    AgentError,
    AgentEvent,
    AgentEventType,
    AgentStatusChunk,
    AgentStreamChunk,
    AgentSummary,
    ReasoningDeltaChunk,
    RunSummary,
    StepSummary,
    TextDeltaChunk,
    ToolCallResultChunk,
    ToolCallStartChunk,
    agent_error,
    agent_status,
    generation_response_to_step_summary,
    reasoning_delta,
    run_summary,
    step_summary,
    text_delta,
    tool_call_result,
    tool_call_start,
)

__all__ = [
    # Runner
    "BaseAgentRunner",
    "AgentState",
    # 枚举
    "AgentEventType",
    # 基类
    "AgentEvent",
    "AgentStreamChunk",
    "AgentSummary",
    # 流式事件
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
