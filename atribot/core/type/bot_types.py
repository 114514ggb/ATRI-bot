import asyncio
import bisect
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, Iterable, List

from atribot.core.type.chat_message_type import ChatMessage


class ToolCallsStopIteration(Exception):
    """结束工具调用异常"""
    def __init__(self, message:str = ""):
        if message:
            super().__init__(f"'tool_calls_end': {message}")
        else:
            super().__init__("end tool call")


@dataclass(slots=True)
class RichData():
    """一般处理消息"""
    primeval:dict
    """原始消息"""
    text:str = ""
    """解析过的qq的文本"""
    pure_text:str = ""
    """消息的文本部分"""
    user_id:int|None = None
    """发送者id"""
    group_id:int|None = None
    """群号"""
    
    
class MessageBuilder:
    """链式消息构建器，支持多模态内容自动合并相邻文本块"""
    __slots__ = ['_role', '_parts']

    def __init__(self, role: str = "user"):
        self._role = role
        self._parts: list = []
    
    def _last_is_text(self) -> bool:
        return bool(self._parts) and self._parts[-1]["type"] == "text"
    
    def add_text(self, text: str) -> "MessageBuilder":
        """添加文本，与前一个文本块自动合并"""
        if self._last_is_text():
            self._parts[-1]["text"] += text
        else:
            self._parts.append({"type": "text", "text": text})
        return self
    
    def add_image(self, url: str, detail: str = "auto") -> "MessageBuilder":
        """添加图片 URL"""
        self._parts.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": detail}
        })
        return self
    
    def add_image_base64(self, data: str, mime: str = "image/png") -> "MessageBuilder":
        """添加 base64 图片"""
        self._parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{data}"}
        })
        return self
    
    def add_audio(self, data: str, fmt: str = "wav") -> "MessageBuilder":
        """添加 base64 音频"""
        self._parts.append({
            "type": "input_audio",
            "input_audio": {"data": data, "format": fmt}
        })
        return self
    
    def add_video(self, url: str) -> "MessageBuilder":
        """添加视频 URL（部分模型支持）"""
        self._parts.append({
            "type": "video_url",
            "video_url": {"url": url}
        })
        return self
    
    def add_file(self, url: str, mime: str = "") -> "MessageBuilder":
        """添加文件（如 PDF 等，部分模型支持）"""
        self._parts.append({
            "type": "file",
            "file": {"url": url, **({"mime_type": mime} if mime else {})}
        })
        return self
    
    def merge(self, other: "MessageBuilder") -> "MessageBuilder":
        """和另一个构建合并"""
        if not other._parts:
            return self
        
        first = other._parts[0]
        
        start = 0
        if first["type"] == "text":
            self.add_text(first["text"])
            start = 1
        
        self._parts.extend(other._parts[start:])
        return self
    
    def build(self) -> Dict[str, Any]:
        """构建消息 dict"""
        # if not self._parts:
        #     raise ValueError("MessageBuilder: 内容为空")
        if len(self._parts) == 1 and self._parts[0]["type"] == "text":
            return {"role": self._role, "content": self._parts[0]["text"]}
        return {"role": self._role, "content": list(self._parts)}
    
    def build_and_add(self, ctx: "Context") -> None:
        """构建并直接追加到 Context"""
        ctx.append(self.build())

    @classmethod
    def user(cls) -> "MessageBuilder":
        return cls("user")
    
    @classmethod
    def assistant(cls) -> "MessageBuilder":
        return cls("assistant")
    
    @classmethod
    def system(cls) -> "MessageBuilder":
        return cls("system")
    
    
@dataclass(slots=True)
class Context():
    """对话上下文"""
    messages: List[Dict[str, Any]] = None
    """原始的上下文"""
    user_max_record: int = 20
    """user最多消息条数限制"""
    user_max_token: int = 40000 #一般模型的上下文是128K的token
    """user消息token限制"""
    play_role:str = ""
    """模型人物提示词"""
    total_tokens:int = 0
    """上一轮api响应中给出的上下文token"""
    async_lock:asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """异步锁"""

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
    
    # def builder(self, role: str = "user") -> "MessageBuilder":
    #     """返回一个绑定到本 Context 的 MessageBuilder"""
    #     b = MessageBuilder(role)
    #     b.build_and_add = lambda: MessageBuilder.build_and_add(b, self)
    #     return b
    
    def get_messages(self, inject_text:str = "")->List[Dict[str, str]]:
        """获取当前的上下文List
        
        Args:
            inject_text (str): 要注入到人设后面的提示词.如果没有Play_role会在开头新建一个system

        Returns:
            List[Dict[str, Any]]: 上下文list
        """
        if parts := [p for p in (self.play_role, inject_text) if p]:
            return [{"role": "system", "content": "\n\n".join(parts)}, *self.messages]
        
        return self.messages
        
    
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
    
    def add_assistant_message(self, content: str|None, reasoning_content:str|None= None) -> None:
        """添加助手消息"""
        assistant_message = {
            "role": "assistant",
            "content" : content
        }
    
        if reasoning_content:
            assistant_message["reasoning_content"] = reasoning_content
        
        self.messages.append(assistant_message)
        
    def add_assistant_message_flexible(self, assistant_message:Dict):
        """灵活的添加user消息

        Args:
            assistant_message (Dict): 模型返回原始消息字段
        """
        self.messages.append(assistant_message)
        
    def add_assistant_tool_message(self, content: str|None, tool_calls:List[Dict], reasoning_content:str|None = None, ) -> None:
        """添加助手调用工具消息"""
        tool_message = {
            "role": "assistant",
            "tool_calls": tool_calls
        }
        
        if content:
            tool_message["content"] = content
        if reasoning_content:
            tool_message["reasoning_content"] = reasoning_content
        
        self.messages.append(tool_message)
        
    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        self.messages.append({"role": "system", "content": content})
        
    def add_tool_message(self, naem:str ,tool_call_id:str , content: str) -> None:
        """添加工具消息"""
        self.messages.append({
            "role": "tool",
            "name": naem, 
            "tool_call_id": tool_call_id,
            "content": content
        })

    def clear(self)->None:
        """清除上下文"""
        self.messages.clear()
        

    def record_validity_check(self) -> list:
        """
        针对消息条数的验证，需要显式调用
        如果 user 消息数超过限制，会截取到总长度为 user_max_record
        并确保最后一条消息是 user 消息（向下取整）
        如果token到达一定值也会触发
        
        Returns:
            list: 被截取掉的消息列表,如果有的话
        """
        user_count = sum(1 for msg in self.messages if msg["role"] == "user")
        
        if user_count > self.user_max_record or self.total_tokens > self.user_max_token:
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
        
    def _estimate_string_tokens(self, text: str) -> float:
        """
        辅助方法：估算纯文本的 Token 数
        利用 UTF-8 字节长度快速区分 ASCII (英文/数字) 和 非ASCII (中文)
        """
        if not text:
            return 0
        
        length = len(text)
        # ASCII占1byte，常用汉字占3bytes
        # 通过字节差值估算非ASCII字符数量
        
        non_ascii_count = (len(text.encode('utf-8')) - length) // 2
        ascii_count = length - non_ascii_count
        
        return (ascii_count * 0.25) + (non_ascii_count * 0.7)

    def get_context_forecast_token(self) -> int:
        """
        获取上下文 Token 估算值 (保守估计，区分中英文)
        """
        total_tokens = 0
        messages = self.get_messages() 
        
        for msg in messages:
            total_tokens += 5 
            
            content = msg.get("content")
            if content:
                if isinstance(content, str):
                    total_tokens += self._estimate_string_tokens(content)
                elif isinstance(content, list):
                    for item in content:
                        item:Dict
                        if item.get("type") == "text":
                            total_tokens += self._estimate_string_tokens(item.get("text", ""))
                        elif item.get("type") == "image_url":
                            total_tokens += 1000
            
            if "tool_calls" in msg and msg["tool_calls"]:
                total_tokens += self._estimate_string_tokens(str(msg["tool_calls"]))
                
        return int(total_tokens)


@dataclass(slots=True)
class ContextDeque:
    """对话上下文 (优化版),不是很确定实战效果使用了双端队列来实现"""
    
    messages: Deque[Dict[str, Any]] = field(default_factory=deque)
    """原始的上下文"""
    
    user_max_record: int = 20
    """user最多消息条数限制"""
    
    play_role: str = ""
    """模型人物提示词"""
    
    async_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """异步锁"""

    def __post_init__(self):
        if self.messages is None:
            self.messages = deque()
        elif isinstance(self.messages, list):
            self.messages = deque(self.messages)
    
    def __getitem__(self, index):
        return self.messages[index]
    
    def __len__(self):
        return len(self.messages)
    
    def __iter__(self):
        return iter(self.messages)
    
    def __contains__(self, item):
        return item in self.messages
    
    def __reversed__(self):
        return reversed(self.messages)
    
    def __str__(self):
        return str(list(self.messages))
    
    def __repr__(self):
        return repr(list(self.messages))

    def append(self, data: Dict[str, Any]) -> None:
        """添加内容"""
        self.messages.append(data)
        
    def extend(self, iterable: Iterable) -> None:
        """扩展列表"""
        self.messages.extend(iterable)
    
    def get_messages(self, inject_text: str = "") -> List[Dict[str, str]]:
        """获取当前的上下文 List"""
        system_content = "\n\n".join(filter(None, [self.play_role, inject_text]))
        system_msg = [{"role": "system", "content": system_content}] if system_content else []
        
        return system_msg + list(self.messages)
    
    def clear(self) -> None:
        """清除上下文"""
        self.messages.clear()


    def record_validity_check(self) -> List[Dict[str, Any]]:
        """
        针对消息条数的验证。
        优化后：使用 popleft() 移除头部元素，避免了列表切片的内存拷贝和移动。
        """
        removed_messages = []

        user_count = sum(1 for msg in self.messages if msg["role"] == "user")
        
        if user_count <= self.user_max_record:
            return None
        
        while user_count > self.user_max_record and self.messages:
            msg = self.messages.popleft()
            removed_messages.append(msg)
            if msg["role"] == "user":
                user_count -= 1
        
        while self.messages and self.messages[0]["role"] != "user":
            msg = self.messages.popleft()
            removed_messages.append(msg)
            
        return removed_messages

    
    def add_message(self, role: str, content: str | list, tool_call_id: int = None) -> None:
        if tool_call_id:
            self.messages.append({
                "role": role, 
                "content": content,
                "tool_call_id": tool_call_id
            })
            return
        self.messages.append({"role": role, "content": content})
        
    def add_img_message(self, role: str, text: str, image_urls: list) -> None:
        self.messages.append({
            "role": role,
            "content": [{"type": "image_url", "image_url": {"url": url}} for url in image_urls] + [{"type": "text", "text": text}]
        })
    
    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        
    def add_assistant_message(self, content: str | None) -> None:
        self.messages.append({"role": "assistant", "content": content})
        
    def add_assistant_message_flexible(self, assistant_message: Dict):
        self.messages.append(assistant_message)
        
    def add_assistant_tool_message(self, content: str | None, tool_calls: List[Dict] = None) -> None:
        msg = {"role": "assistant", "tool_calls": tool_calls}
        if content:
            msg["content"] = content
        self.messages.append(msg)
        
    def add_system_message(self, content: str) -> None:
        self.messages.append({"role": "system", "content": content})
        
    def add_tool_message(self, name: str, tool_call_id: str, content: str) -> None:
        self.messages.append({
            "role": "tool",
            "name": name, 
            "tool_call_id": tool_call_id,
            "content": content
        })

    def _estimate_string_tokens(self, text: str) -> float:
        if not text:
            return 0
        length = len(text)
        non_ascii_count = (len(text.encode('utf-8')) - length) // 2
        ascii_count = length - non_ascii_count
        return (ascii_count * 0.25) + (non_ascii_count * 0.7)

    def get_context_forecast_token(self) -> int:
        total_tokens = 0
        for msg in self.messages:
            total_tokens += 5 
            content = msg.get("content")
            if content:
                if isinstance(content, str):
                    total_tokens += self._estimate_string_tokens(content)
                elif isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            total_tokens += self._estimate_string_tokens(item.get("text", ""))
                        elif item.get("type") == "image_url":
                            total_tokens += 1000
            if "tool_calls" in msg and msg["tool_calls"]:
                total_tokens += self._estimate_string_tokens(str(msg["tool_calls"]))
        return int(total_tokens)
    

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
    """定义一个时间窗口，用于统计一段时间内的消息数量
        作为衡量一些东西在一段时间内的跃度参考
    """
    __slots__ = ('window_seconds', 'events')
    
    window_seconds: int
    """当前窗口的统计时间，单位秒"""
    events: deque
    """存储在当前窗口时间内的有效时间戳,顺序：[旧 -> 新]"""
    
    def __init__(self, window_seconds: int = 60):
        """初始化时间窗口。
        
        Args:
            window_seconds: 时间窗口的大小，单位秒。必须为正整数。
            
        Raises:
            ValueError: 如果 window_seconds 不是正整数
        """
        if not isinstance(window_seconds, int) or window_seconds <= 0:
            raise ValueError("window_seconds 必须为正整数")
        self.window_seconds = window_seconds
        self.events = deque()
    
    def _clean_expired(self, now: float):
        """清理过期数据：移除所有早于 (now - window) 的时间戳"""
        cutoff = now - self.window_seconds
        while self.events and self.events[0] < cutoff:
            self.events.popleft()
    
    def add(self):
        """添加一条当前时间的计数,time.monotonic()时间"""
        now = time.monotonic()
        self.events.append(now)
        self._clean_expired(now)
    
    def add_time(self,now):
        """添加一条时间的计数,时间单位秒级别的时间戳"""
        self.events.append(now)
        self._clean_expired(now)
    
    def get(self) -> int:
        """返回当前有效的消息数量"""
        self._clean_expired(time.monotonic())
        return len(self.events)
    
    def clear(self):
        """清空所有计数"""
        self.events.clear()
    
    def get_sub_window(self, sub_seconds: int) -> 'TimeWindow':
        """
        创建一个更短时间的子窗口，并继承当前窗口内的有效数据。
        
        Args:
            sub_seconds: 子窗口的时间长度（秒）。必须小于等于当前窗口长度。
        """
        if sub_seconds > self.window_seconds:
            raise ValueError("子窗口时间不能大于父窗口时间")
        
        sub_win = TimeWindow(sub_seconds)
        now = time.monotonic()
        self._clean_expired(now) 
        
        count = len(self.events)
        if count == 0:
            return sub_win
            
        cutoff = now - sub_seconds

        if sub_seconds / self.window_seconds < 0.15:
            temp = []
            for t in reversed(self.events):
                if t < cutoff:
                    break
                temp.append(t)
            sub_win.events.extend(reversed(temp))

        else:
            events_list = list(self.events)
            idx = bisect.bisect_left(events_list, cutoff)
            sub_win.events.extend(events_list[idx:])
            
        return sub_win
    
    @property
    def size(self) -> int:
        """返回当前队列大小（不触发清理）"""
        return len(self.events)

    def get_messages_per_second(self)->float:
        """获取总平均每秒消息数量

        Returns:
            float: 当前有效消息数量/窗口统计秒数
        """
        return self.get() / self.window_seconds

    def get_padded_avg_interval(
        self, 
        sample_count: int = 5,
        default_interval: float = 1.1
    ) -> float:
        """获取最近几条消息的平均时间间隔
        
        用于判断瞬时流量密度。如果返回的时间极短，说明发生了突发流量
        
        Args:
            sample_count: 采样数量。默认为5，即计算最近5条消息（4个间隔）的平均值
            default_interval: 缺省时的补偿间隔（秒）
        
        Returns:
            float: 平均间隔秒数。
                   如果消息不足2条，返回 float('inf')
        """
        real_count = len(self.events)
        
        if real_count < 2:
            return float('inf')
        
        calc_count = real_count if real_count < sample_count else sample_count
        real_duration = self.events[-1] - self.events[-calc_count]
        real_intervals = calc_count - 1
        target_intervals = sample_count - 1
        
        if real_intervals < target_intervals:
            return (real_duration + (target_intervals - real_intervals) * default_interval) / target_intervals
        else:
            return real_duration / real_intervals


    def get_recent_avg_interval(self, sample_count: int = 5) -> float:
        """获取最近几条消息的真实平均时间间隔（高效率版）
        
        直接计算采样范围内的时间跨度除以间隔数，不进行任何填充。
        能够最快地反映出当前的瞬时流量密度。
        
        Args:
            sample_count: 采样数量（即计算最近 N 条消息的跨度）
            
        Returns:
            float: 平均间隔秒数。如果消息不足 2 条，返回 float('inf')
        """
        real_count = len(self.events)
        
        if real_count < 2:
            return float('inf')
        
        calc_count = sample_count if real_count >= sample_count else real_count

        return (self.events[-1] - self.events[-calc_count]) / (calc_count - 1)

        
        
class LLMGroupChatCondition:
    """群用LLM发言的一些参数记录,用于决策的参考"""
    
    __slots__ = ('last_msg_at', 'last_trigger_user_id', 'last_trigger_user_time', 'time_window', 'turns_since_last_llm', '_lock')
    
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




@dataclass(slots=True)
class GroupContext:
    """群组上下文"""
    
    group_id:int
    """群号"""
    messages:deque[ChatMessage] = field(init=False)
    """消息列表"""
    group_max_record:int
    """群维持的消息数量"""
    last_msg_at:float = field(default=time.time(), init=False)
    """群最后一次添加消息的时间"""
    
    chat_context:Context
    """群LLM聊天上下文"""
    play_roles:str
    """当前LLM聊天人设名称"""
    IS_SUMMARIZING:bool = field(default=False, init=False)
    """是否在总结"""
    summarize_message_count:int = field(default=0, init=False)
    """未总结的计数"""
    time_window: TimeWindow = field(init=False)
    """统计群近期消息数量的窗口对象"""
    LLM_chat_decision_parameters:LLMGroupChatCondition = field(init=False)
    """LLM聊天决策使用的一些参数"""
    async_summarize_lock:asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """群异步总结锁"""
    async_lock:asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """群异步锁"""
    initiative_chat:bool = field(default=False)
    """是否启用主动加入聊天"""
    information_extraction:bool = field(default=False)
    """是否启用群信息提取"""

    def __post_init__(self, window_time: int = 60):
        self.messages = deque(maxlen=self.group_max_record)
        self.time_window = TimeWindow(window_time)
        self.LLM_chat_decision_parameters = LLMGroupChatCondition(window_time)
    
    def __iter__(self):
        return iter(self.messages)
    
    def update_time(self):
        """更新私聊类的最新使用时间"""
        self.last_msg_at = time.time()

    def _record_validity_check(self)->List[str]|None:
        """针对群聊天消息条数的验证

        Returns:
            List[str]: 要总结的原始消息列表(如果达到阈值)
        """
        if self.summarize_message_count >= self.group_max_record:
            self.summarize_message_count = 0
            return self.build_context()
        
        return None

    def build_context(self) -> str:
        """返回构建的LLM文本上下文"""
        return "\n".join(msg.llm_formatted_message for msg in self.messages)

    async def add_group_chat_message(self, message:ChatMessage)->tuple[List[str], "GroupContext"]|None:
        """添加群消息,然后做有效性验证

        Args:
            message (str): 添加的消息

        Returns:
            tuple[List[str], GroupContext]|None:  如果需要总结,返回 (消息列表, 上下文对象)
        """
        
        async with self.async_lock:
            self.last_msg_at = time.time() #更新群最后处理时间
            self.messages.append(message.llm_formatted_message)
            self.summarize_message_count += 1
            messages_to_summarize = self._record_validity_check()
            
            if self.information_extraction and messages_to_summarize is not None:
                return (messages_to_summarize, self)
        
        return None
    
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




@dataclass(slots=True)
class PrivateContext:
    
    user_id: int
    """user的qq号"""
    chat_context: Context
    """群LLM聊天上下文"""
    play_roles: str
    """当前LLM聊天人设名称"""
    
    async_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """异步锁"""
    last_msg_at: float = field(default=time.monotonic(), init=False)
    """最后一次消息的使用时间"""
    time_window: TimeWindow = field(init=False)
    """统计群近期消息数量的窗口对象"""
    
    def __post_init__(self, window_time:int = 60):
        self.time_window = TimeWindow(window_time)

    def update_time(self):
        """更新私聊类的最新使用时间"""
        self.last_msg_at = time.time()



@dataclass(slots=True)
class MessageBase():
    """基础消息类"""
    
    message_id:int
    """消息id"""
    user_id:int
    """发送者id"""
    nickname:str
    """发送者账户名"""
    user_message:str
    """消息有效的文本内容"""
    # message:Dict = field(default_factory=dict)
    # """原始格式化消息内容"""
    message_time:str = field(default_factory=lambda: time.strftime('%Y-%m-%d %H:%M:%S'))
    """创建的时间"""

    # def __post_init__(self):
    #     """在 dataclass 初始化后调用"""
    #     self.user_message = self.get_user_message_str()
    
    def to_dict(self,extend_dict:dict = {}) -> dict:
        """获取自己属性的字典"""
        return {
            "message_id": self.message_id,
            "time": self.message_time,
            "user_id": self.user_id,
            "nickname": self.nickname,
            "user_message": self.user_message
        } | extend_dict
    
    # @abstractmethod
    # def get_user_message_str() -> str:
    #     """获取纯文本的user消息"""
    #     pass
    
    def __str__(self):
        return str(self.to_dict())
    
    def __repr__(self):
        return str(self.to_dict())
    
    def __getitem__(self, item):
        return getattr(self, item)
    
    def get(self, item, default=None):
        return getattr(self, item, default)


@dataclass(slots=True)
class GroupMessage(MessageBase):
    """群消息"""

@dataclass(slots=True)  
class PrivateMessage(MessageBase):
    """私聊消息"""