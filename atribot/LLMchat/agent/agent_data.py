from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List

from atribot.LLMchat.agent.context.context import AgentContext
from atribot.LLMchat.model_api.model_api_basics import model_api_basics

if TYPE_CHECKING:
    from atribot.LLMchat.agent.hooks import BaseAgentHooks


@dataclass
class AgentData:
    """Agent 运行时的数据与配置载体

    承载了单次/多轮对话模型执行时所需的所有基础状态及配置

    Attributes:
        context (AgentContext): Agent 的对话上下文
        model_name (str): 驱动此 Agent 的模型名称
        supplier (model_api_basics): 提供大模型的服务商
        tools (List[str]): 提供给 Agent 调用的工具名称列表
        kwargs (Dict[str, Any]): 额外运行时控制参数
        hooks (List[BaseAgentHooks]): 挂载到此 Agent 的生命周期钩子列表
    """

    context: AgentContext
    model_name: str
    supplier: model_api_basics
    tools: List[str] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(
        default_factory=lambda:{
            "temperature":0.0,
            "top_p":0.90,
            "max_tokens": 65536,
            "stream":False,
            "tool_choice": "auto"
        }
    )
    hooks: List[BaseAgentHooks] = field(default_factory=list)
