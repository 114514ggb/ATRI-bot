from dataclasses import dataclass, field
from typing import Any, Dict, List

from atribot.LLMchat.agent.context import AgentContext
from atribot.LLMchat.agent.hooks import BaseAgentHooks


@dataclass
class AgentData:
    """Agent 运行时的数据与配置载体

    承载了单次/多轮对话模型执行时所需的所有基础状态及配置

    Attributes:
        context (AgentContext): Agent 的对话上下文
        model_name (str): 驱动此 Agent 的模型名称（如 "glm-4", "gpt-4o"）
        supplier (str): 提供大模型的服务商名称，用于请求路由
        tools (List[str]): 提供给 Agent 调用的工具名称列表
        kwargs (Dict[str, Any]): 额外运行时控制参数
        hooks (List[BaseAgentHooks]): 挂载到此 Agent 的生命周期钩子列表
    """

    context: AgentContext
    model_name: str
    supplier: str = ""
    tools: List[str] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    hooks: List['BaseAgentHooks'] = field(default_factory=list)
