import asyncio
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from atribot.LLMchat.agent.agent_data import AgentData


class BaseAgentRunner(ABC):
    """异步基础 Agent 执行器

    所有输出操作（无论流式还是块级）统一由内部实现决定，通过异步生成器对外暴露
    具备并发保护锁，确保同个实例不会被重复激活，同时提供受控条件下的强制中断

    Attributes:
        agent_data (AgentData): 运行器绑定的状态载体
        _is_interrupted (bool): 收到了外部中断请求的标记
        _is_running (bool): 标记当下模型是否正处在运行请求或处理工具中
        _run_lock (asyncio.Lock): 保证运行状态不被并发破坏的互斥锁
    """

    def __init__(self, agent_data: AgentData):
        """初始化基础执行器

        Args:
            agent_data (AgentData): Agent 的静态和运行时核心数据
        """
        self.agent_data = agent_data
        self._is_interrupted = False
        self._is_running = False
        self._run_lock = asyncio.Lock()

    @abstractmethod
    async def step(self) -> AsyncGenerator[Any, None]:
        """执行单一推进步骤（单次模型思考或单次工具调用）

        子类需要实现该函数它负责对接真实的 LLM 调用并进行 Token / Action 的 yield 回传
        
        Yields:
            Any: 部分生成的 Token 字符串，或结构化的执行进度对象
        """
        yield None

    async def run(self, max_turns: int = 5) -> AsyncGenerator[Any, None]:
        """完整运行 Agent 逻辑直到任务完结或受阻

        Args:
            max_turns (int): 允许此 Agent 连续进行的最大独立步骤数

        Yields:
            Any: 从 `step()` 抛出的实时产出
        """
        async with self._run_lock:
            self._is_running = True
            self._is_interrupted = False

            try:
                for turn in range(max_turns):
                    if self._is_interrupted:
                        break
                        
                    # 标识单步是否已表示最终结束（例如无需调用 tool 了）
                    # 具体实现可以在 step() 迭代中抛出特定标志对象来修改这个状态
                    is_final = True  
                    
                    async for chunk in self.step():
                        if self._is_interrupted:
                            break

                        yield chunk

                    if is_final:
                        break
            finally:
                self._is_running = False

    def guide(self, prompt: str) -> None:
        """提供一段指导性上下文给模型
        多步的时候在这一次响应执行完成后，发送一条消息进行引导

        Args:
            prompt (str): 下达给执行器的内部纠偏或强制性引导文本
        """
        pass
