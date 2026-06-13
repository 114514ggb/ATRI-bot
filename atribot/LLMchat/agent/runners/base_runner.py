from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING, AsyncGenerator

from atribot.LLMchat.agent.agent_data import AgentData

if TYPE_CHECKING:
    from atribot.LLMchat.agent.runners.response import AgentEvent


class AgentState(Enum):
    """Agent 运行状态"""

    IDLE = auto()
    RUNNING = auto()
    ERROR = auto()


class BaseAgentRunner(ABC):
    """异步基础 Agent 执行器

    Attributes:
        agent_data (AgentData): 运行器绑定的状态载体
        state (AgentState): 当前 Agent 的运行状态
        stream (bool): 是否输出流式中间事件
    """

    def __init__(self, agent_data: AgentData):
        """初始化基础执行器

        Args:
            agent_data (AgentData): Agent 的静态和运行时核心数据
        """
        self.agent_data = agent_data
        self.state = AgentState.IDLE

    @property
    def stream(self) -> bool:
        """是否启用流式输出，从 agent_data.kwargs 中读取

        Returns:
            bool: 流式开关，默认 False
        """
        return bool(self.agent_data.kwargs.get("stream", False))

    def update_state(self, new_state: AgentState) -> None:
        """更新 Agent 运行状态

        Args:
            new_state (AgentState): 新状态
        """
        self.state = new_state


    @abstractmethod
    async def step(self) -> AsyncGenerator[AgentEvent, None]:
        """执行单一推进步骤

        单次 LLM 交互（内部可能包含工具调用循环）

        Yields:
            AgentEvent: stream=True 时依次产出流式中间事件，最后产出 StepSummary
                        stream=False 时仅产出 StepSummary
        """
        ...

    @abstractmethod
    async def run(self, max_turns: int = 20) -> AsyncGenerator[AgentEvent, None]:
        """完整运行 Agent 逻辑直到任务完结或受阻

        Yields:
            AgentEvent: stream=True 时每步产出流式中间事件 + StepSummary
                        最后产出 RunSummary
                        stream=False 时仅产出 RunSummary
        """
        ...
