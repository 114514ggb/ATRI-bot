import asyncio
import json
from dataclasses import dataclass
from logging import Logger
from typing import Any, Callable

from mcp.types import CallToolResult

from atribot.core.type.bot_types import atriMessageEvent
from atribot.LLMchat.MCP.tool_model import FunctionTool
from atribot.LLMchat.model_api.llm_types import ToolCall


@dataclass
class ToolCallResult:
    """单个工具执行结果

    Attributes:
        tool_name: 工具名称
        tool_call_id: 工具调用 ID
        result: 执行返回的原始结果
        is_error: 是否执行出错
    """
    tool_name: str
    tool_call_id: str
    result: Any
    is_error: bool = False


class ToolExecutionEngine:
    """统一工具执行引擎"""

    def __init__(self, logger: Logger) -> None:
        self.log = logger.getChild("ToolExecEngine")
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _get_semaphore(self, tool_name: str) -> asyncio.Semaphore:
        """获取或创建 per-tool 全局信号量

        用于 ``concurrent=False`` 的工具，确保跨 Agent 实例也只有一个执行实例
        """
        if tool_name not in self._semaphores:
            self._semaphores[tool_name] = asyncio.Semaphore(3)
        return self._semaphores[tool_name]

    async def execute_batch(
        self,
        tool_calls: list[ToolCall],
        get_func: Callable[[str], FunctionTool | None],
        message_data: atriMessageEvent,
    ) -> list[ToolCallResult]:
        """执行一批工具调用

        Args:
            tool_calls: LLM 返回的工具调用列表
            get_func: 按名称获取 :class:`FunctionTool` 的回调
            message_data: 聊天消息事件上下文

        Returns:
            所有工具的执行结果列表
        """
        results: list[ToolCallResult] = []

        concurrent_items: list[tuple[FunctionTool, str, dict, str]] = []
        sequential_items: list[tuple[FunctionTool, str, dict, str]] = []

        for tc in tool_calls:
            function = tc.get("function", {})
            tool_name: str = function.get("name", "")
            tool_input_str: str = function.get("arguments", "{}")
            tool_call_id: str = tc.get("id", tool_name)

            func_tool = get_func(tool_name)
            if func_tool is None:
                results.append(ToolCallResult(
                    tool_name, tool_call_id,
                    f"工具 {tool_name} 未找到",
                    is_error=True,
                ))
                continue

            try:
                args: dict = json.loads(tool_input_str)
            except (json.JSONDecodeError, TypeError):
                args = {}
                self.log.warning(f"工具 {tool_name} 参数解析失败: {tool_input_str[:200]}")

            item = (func_tool, tool_name, args, tool_call_id)

            if func_tool.concurrent or func_tool.background:
                concurrent_items.append(item)
            else:
                sequential_items.append(item)

        if concurrent_items:
            async def _run_one(
                item: tuple[FunctionTool, str, dict, str],
            ) -> ToolCallResult:
                _func_tool, _name, _args, _tid = item
                try:
                    raw: str | CallToolResult = await _func_tool.execute(message_data=message_data, **_args)
                    return ToolCallResult(_name, _tid, raw)
                except Exception as e:
                    self.log.error(f"工具 {_name} 执行失败: {e}", exc_info=True)
                    return ToolCallResult(
                        _name, _tid,
                        f"调用工具发生错误\nErrors:{e}",
                        is_error=True,
                    )

            gathered: list[ToolCallResult] = await asyncio.gather(
                *[_run_one(i) for i in concurrent_items],
            )
            results.extend(gathered)

        for func_tool, tool_name, args, tool_call_id in sequential_items:
            async with self._get_semaphore(tool_name):
                try:
                    raw = await func_tool.execute(message_data=message_data, **args)
                    results.append(ToolCallResult(tool_name, tool_call_id, raw))
                except Exception as e:
                    self.log.error(f"工具 {tool_name} 执行失败: {e}", exc_info=True)
                    results.append(ToolCallResult(
                        tool_name, tool_call_id,
                        f"调用工具发生错误\nErrors:{e}",
                        is_error=True,
                    ))

        return results

