from abc import ABC
from typing import Any, Dict

from atribot.LLMchat.agent.agent_data import AgentData


class BaseAgentHooks(ABC):
    """Agent 执行周期的生命钩子抽象基类"""

    async def before_run(self, agent_data: AgentData) -> None:
        """在运行前触发"""
        pass

    async def after_run(self, agent_data: AgentData, response: Any) -> None:
        """在一次运行结束后触发"""
        pass

    async def on_tool_call(self, agent_data: AgentData, tool_name: str, arguments: Dict[str, Any]) -> None:
        """在模型提出要调用具体某工具，且参数解析完成，正要执行前触发"""
        pass

    async def on_tool_return(self, agent_data: AgentData, tool_name: str, result: Any) -> None:
        """在本地工具方法刚刚执行完成，准备将结果抛回给上下文或直接拼装时触发"""
        pass

    async def on_error(self, agent_data: AgentData, error: Exception) -> None:
        """在整个执行周期中爆发未捕获的错误导致流程溃散时触发"""
        pass
