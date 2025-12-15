from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Dict,List,Any
from collections import deque
import asyncio
import time




class ToolCallsStopIteration(Exception):
    """结束工具调用异常"""
    def __init__(self, message:str = ""):
        if message:
            super().__init__(f"'tool_calls_end': {message}")
        else:
            super().__init__("end tool call")


@dataclass
class RichData():
    """一般处理消息"""
    primeval:dict
    """原始消息"""
    text:str = ""
    """解析过的qq的文本"""
    pure_text:str = ""
    """消息的文本部分"""
    
    
@dataclass
class Context():
    """对话上下文"""
    messages: List[Dict[str, Any]] = None
    """原始的上下文"""
    user_max_record: int = 20
    """user最多消息条数限制"""
    play_role:str = ""
    """模型人物提示词"""

    def __post_init__(self):
        if self.messages is None:
            self.messages = []
    
    def __getitem__(self, index):
        return self.get_messages()[index]
    
    def __len__(self):
        return len(self.get_messages())
    
    def __iter__(self):
        return iter(self.get_messages())
    
    def __contains__(self, item):
        return item in self.get_messages()
    
    def __reversed__(self):
        return reversed(self.get_messages())
    
    def __str__(self):
        return str(self.get_messages())
    
    def __repr__(self):
        return repr(self.get_messages())
    
    def append(self, dict:Dict[str, Any])->None:
        """添加内容"""
        self.messages.append(dict)
        
    def extend(self, Iterable:List)->None:
        """用可迭代对象来扩展列表"""
        self.messages.extend(Iterable)
    
    def get_messages(self, inject_text:str = "")->List[Dict[str, str]]:
        """获取当前的上下文List
        
        Args:
            inject_text (str): 要注入到人设后面的提示词.如果没有Play_role会在开头新建一个system

        Returns:
            List[Dict[str, Any]]: 上下文list
        """
        system_msg = [{"role": "system", "content": "\n\n".join(filter(None, [self.play_role, inject_text]))}]
        return system_msg + self.messages if system_msg[0]["content"] else self.messages
    
    def add_message(self, role:str, content:str|list, tool_call_id:int = None)->None:
        """添加消息

        Args:
            role (str): 消息枚举值"user", "assistant", "system", "tool"
            content (str): 内容
            tool_call_id (int): 工具id,当类型为tool时可能需要
        """
        if tool_call_id:
            self.messages.append({
                "role": role, 
                "content": content,
                "tool_call_id": tool_call_id
            })
            return
        
        self.messages.append({"role": role, "content": content})
        
    def add_img_message(self, role:str, text:str, image_urls: list)->None:
        """添加带图片消息

        Args:
            role (str): 消息枚举值"user", "assistant", "system", "tool"
            text (str): 文本内容
            image_urls (list): 图片的 URL 列表，每个 URL 都会被作为独立的图片项添加到 content 
        """
        self.messages.append({
            "role": role,
            "content": [{"type": "image_url", "image_url": {"url": url}} for url in image_urls] + [{"type": "text", "text": text}]
        })
    
    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})
        
    def add_assistant_message(self, content: str|None) -> None:
        """添加助手消息"""
        self.messages.append({"role": "assistant", "content": content})
        
    def add_assistant_tool_message(self, content: str|None,tool_calls:List[Dict] = None) -> None:
        """添加助手调用工具消息"""
        if content:
            self.messages.append({"role": "assistant","content": content,"tool_calls": tool_calls})
        else:
            self.messages.append({"role": "assistant","tool_calls": tool_calls})
        
    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        self.messages.append({"role": "system", "content": content})
        
    def add_tool_message(self, content: str, tool_call_id:int = None) -> None:
        """添加工具消息"""
        self.messages.append({"role": "tool", "content": content, "tool_call_id": tool_call_id})
        
    def record_validity_check(self) -> list:
        """
        针对消息条数的验证，需要显式调用。
        如果 user 消息数超过限制，会截取到总长度为 user_max_record，
        并确保最后一条消息是 user 消息（向下取整）。
        
        Returns:
            list: 被截取掉的消息列表,如果有的话
        """
        user_count = sum(1 for msg in self.messages if msg["role"] == "user")
        
        if user_count > self.user_max_record:
            # 先截取到总长度为 user_max_record
            kept_messages = self.messages[-self.user_max_record:]
            
            # 从后往前找到最后一个 user 消息的位置
            last_user_index = -1
            for i in range(0, len(kept_messages)):
                if kept_messages[i]["role"] == "user":
                    last_user_index = i
                    break
            
            # 截取到最近条 user 消息
            if last_user_index != -1:
                kept_messages = kept_messages[last_user_index:]
            else:
                import copy
                removed_messages = copy.copy(self.messages)
                self.messages.clear()
                return removed_messages
            
            # 计算被删除的消息
            removed_messages = self.messages[:len(self.messages) - len(kept_messages)]
            self.messages = kept_messages
            return removed_messages
        
        return None
        
    def clear(self)->None:
        """清除上下文"""
        self.messages.clear()

    def get_context_forecast_token(self)->int:
        """获取仅供参考的当前上下文的token(默认里面都是中文)

        Returns:
            int: 大概token数,误差应该挺大的
        """
        return int(len(str(self.get_messages()))*1.2)
    

class Message:
    """消息基础类，表示系统中的一个消息单元
    
    注：目前没有使用,或许在计划中后面这个有用
        对消息产生和接收到差值太多的消息只进行存储处理，不进行响应
        对处理过久的消息进行丢弃
    """

    create_time: float
    """消息产生时间"""
    receive_time:float
    """消息处理器首次接收到这次消息的时间"""
    process_time:float
    """到达当前处理节点的时间"""
    rich_data:"RichData"
    """具体的处理数据"""  
    
    def __init__(self, rich_data:RichData):
        self.create_time = rich_data.primeval['time']
        self.receive_time = self.process_time = time.time()
        self.rich_data:RichData = rich_data
        
    def update_process_time(self) -> None:
        """更新当前处理节点时间为当前时间戳"""
        self.process_time = time.time()


class TimeWindow:
    """定义一个时间窗口，用于统计一段时间内的消息数量，作为衡量群活跃度的参考。
    
    该类是线程安全的，可以在异步环境中并发调用。
    """
    
    windows_time: int
    """当前窗口的统计时间，单位秒"""
    windows_deque: deque
    """存储在当前窗口时间内的有效时间戳，按照时间降序排列（新->旧）"""
    _lock: asyncio.Lock
    """用于保护数据结构的异步锁"""
    
    def __init__(self, windows_time: int):
        """初始化时间窗口。
        
        Args:
            windows_time: 时间窗口的大小，单位秒。必须为正整数。
            
        Raises:
            ValueError: 如果 windows_time 不是正整数
        """
        if not isinstance(windows_time, int) or windows_time <= 0:
            raise ValueError("windows_time 必须为正整数")
        self.windows_time = windows_time
        self.windows_deque = deque()
        self._lock = asyncio.Lock()
    
    def _clean_expired(self, cutoff: float):
        """清理过期数据的内部方法，假设调用者已持有锁。
        
        Args:
            cutoff: 时间戳阈值，小于此值的数据将被移除
        """
        while self.windows_deque and self.windows_deque[-1] < cutoff:
            self.windows_deque.pop()
    
    async def add(self):
        """添加一条当前时间的计数"""
        now = time.time()
        async with self._lock:
            self.windows_deque.appendleft(now)
            # self._clean_expired(now - self.windows_time)
    
    async def get(self) -> int:
        """返回当前有效的消息数量"""
        async with self._lock:
            self._clean_expired(time.time() - self.windows_time)
            return len(self.windows_deque)
    
    async def get_timestamps(self) -> List[float]:
        """返回当前窗口内所有有效时间戳的副本
        
        Returns:
            按时间降序排列的时间戳列表
        """
        async with self._lock:
            self._clean_expired(time.time() - self.windows_time)
            return list(self.windows_deque)
    
    async def clear(self):
        """清空所有计数"""
        async with self._lock:
            self.windows_deque.clear()
    
    async def size(self) -> int:
        """返回当前队列大小，不清理过期数据"""
        async with self._lock:
            return len(self.windows_deque)


class LLMGroupChatCondition:
    """群用LLM发言的一些参数记录,用于决策的参考"""
    
    last_msg_at: float
    """LLM最近一次发言的时间"""
    last_trigger_user_id: int
    """最近一次触发@聊天的用户ID"""
    last_trigger_user_time: float
    """最近一次触发@聊天的用户时间"""
    time_window: TimeWindow
    """统计群近期bot消息数量的窗口"""
    turns_since_last_llm: int
    """距离上次触发发言次数"""
    
    def __init__(self, window_time:int = 60):
        """初始化时间窗口。
        
        Args:
            windows_time: 时间窗口的大小，单位秒。必须为正整数。
            
        Raises:
            ValueError: 如果 windows_time 不是正整数
        """
        self.time_window = TimeWindow(window_time)
        self.last_msg_at = self.last_trigger_user_time = time.time()
        self.last_trigger_user_id = 0
        self.turns_since_last_llm = 0
        self._lock = asyncio.Lock()
    
    async def update_last_time(self) -> None:
        """更新LLM最近一次发言时间戳"""
        async with self._lock:
            self.last_msg_at = time.time()
    
    async def update_trigger_user(self, user_id: int) -> None:
        """更新最近一次触发聊天的用户信息"""
        async with self._lock:
            self.last_trigger_user_id = user_id
            self.last_trigger_user_time = time.time()

    def get_seconds_since_llm_time(self) -> float:
        """获取距离上一次LLM发言时间(秒级)"""
        return time.time()-self.last_msg_at
    
    def get_seconds_since_user_time(self) -> float:
        """获取距离上一次user触发发言时间(秒级)"""
        return time.time()-self.last_trigger_user_time
    
    async def add_turns_since_last_llm(self) -> None:
        """增加距离上次触发发言次数计数"""
        async with self._lock:
            self.turns_since_last_llm += 1
        
    async def reset_turns_since_last_llm(self) -> None:
        """重置距离上次触发发言次数计数"""
        async with self._lock:
            self.turns_since_last_llm = 0




class GroupContext:
    """群组上下文"""
    
    group_id:int
    """群号"""
    async_lock:asyncio.Lock
    """群异步锁"""
    messages:deque
    """消息列表"""
    group_max_record:int
    """群维持的消息数量"""
    last_msg_at:float
    """群最后一次消息的处理时间"""
    
    
    chat_context:Context
    """群LLM聊天上下文"""
    # chat_img_url_cache:deque
    # """图像url缓存"""
    play_roles:str
    """当前LLM聊天人设名称"""
    IS_SUMMARIZING:bool = False
    """是否在总结"""
    async_summarize_lock:asyncio.Lock
    """群异步锁"""
    group_chat_summary:str = ""
    """群聊天的总结"""
    summarize_message_count:int = 0 
    """未总结的计数"""
    time_window: TimeWindow
    """统计群近期消息数量的窗口对象"""
    LLM_chat_decision_parameters:LLMGroupChatCondition
    """LLM聊天决策使用的一些参数"""

    def __init__(
        self,
        group_id: int,
        play_roles: str,
        chat_context: 'Context',
        group_max_record: int = 20,
        window_time: int = 60
    ):
        self.group_id = group_id
        self.play_roles =  play_roles
        self.chat_context = chat_context
        self.group_max_record = group_max_record
        # self.chat_img_url_cache = deque(maxlen=2) #接受2张图
        self.async_lock = asyncio.Lock()
        self.async_summarize_lock = asyncio.Lock()
        self.time_window = TimeWindow(window_time)
        self.LLM_chat_decision_parameters = LLMGroupChatCondition(window_time)
        self.last_msg_at = 0
        self.messages = deque(maxlen=group_max_record)
        
    
    def __iter__(self):
        return iter(self.messages)
    
    def _record_validity_check(self)->List[str]|None:
        """针对群聊天消息条数的验证

        Returns:
            List[str]: 要总结的原始消息列表(如果达到阈值)
        """
        if self.summarize_message_count >= self.group_max_record:
            self.summarize_message_count = 0
            return list(self.messages)
        
        return None

    async def add_group_chat_message(self,message:str)->tuple[List[str], "GroupContext"]|None:
        """添加群消息,然后做有效性验证

        Args:
            message (str): 添加的消息

        Returns:
            tuple[List[str], GroupContext]|None:  如果需要总结,返回 (消息列表, 上下文对象)
        """
        async with self.async_lock:
            self.last_msg_at = time.time() #更新群最后处理时间
            self.messages.append(message)
            await self.time_window.add()
            self.summarize_message_count += 1
            messages_to_summarize = self._record_validity_check()
            
            if messages_to_summarize is not None:
                return (messages_to_summarize, self)
        
        return None
    
    # def data_extract_img_url(self, data:Dict)->None:
    #     (message["data"]["url"] for message in data["message"] if message["type"] == "image")

    
    @asynccontextmanager
    async def summarizing(self):
        """
        如果上一轮总结还没跑完，会直接跳过（返回 None），
        否则把 IS_SUMMARIZING 置 True，退出块时自动复位。
        """
        if self.IS_SUMMARIZING:          
            yield None                  
            return

        async with self.async_summarize_lock:      
            if self.IS_SUMMARIZING:      
                yield None
                return
            self.IS_SUMMARIZING = True

        try:
            yield self                   
        finally:
            self.IS_SUMMARIZING = False