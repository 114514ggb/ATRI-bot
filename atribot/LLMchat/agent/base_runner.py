from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, AsyncGenerator

from atribot.LLMchat.agent.agent_data import AgentData


class AgentState(Enum):
    """Agent 运行状态"""
    
    IDLE = auto()
    RUNNING = auto()
    INTERRUPTED = auto()
    ERROR = auto()


class BaseAgentRunner(ABC):
    """异步基础 Agent 执行器
    
    Attributes:
        agent_data (AgentData): 运行器绑定的状态载体
        state (AgentState): 当前 Agent 的运行状态
    """

    def __init__(self, agent_data: AgentData):
        """初始化基础执行器

        Args:
            agent_data (AgentData): Agent 的静态和运行时核心数据
        """
        self.agent_data = agent_data
        self.state = AgentState.IDLE

    def update_state(self, new_state: AgentState) -> None:
        """更新 Agent 运行状态

        Args:
            new_state (AgentState): 新状态
        """
        self.state = new_state

    @abstractmethod
    async def step(self) -> AsyncGenerator[Any, None]:
        """执行单一推进步骤"""
        ...

    async def run(self, max_turns: int = 10) -> AsyncGenerator[Any, None]:
        """完整运行 Agent 逻辑直到任务完结或受阻"""
        ...
