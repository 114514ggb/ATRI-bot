import asyncio
import bisect
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from atribot.core.type.context_types import Context

if TYPE_CHECKING:
    from atribot.core.type.bot_types import atriMessageEvent
    from atribot.core.type.onebot_event_types import MessageEvent


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
        """初始化时间窗口

        Args:
            window_seconds: 时间窗口的大小，单位秒必须为正整数

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

    def add_time(self, now):
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
        创建一个更短时间的子窗口，并继承当前窗口内的有效数据

        Args:
            sub_seconds: 子窗口的时间长度（秒）必须小于等于当前窗口长度
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

    def get_messages_per_second(self) -> float:
        """获取总平均每秒消息数量

        Returns:
            float: 当前有效消息数量/窗口统计秒数
        """
        return self.get() / self.window_seconds

    def get_padded_avg_interval(
        self,
        sample_count: int = 5,
        default_interval: float = 3
    ) -> float:
        """获取最近几条消息的平均时间间隔

        用于判断瞬时流量密度如果返回的时间极短，说明发生了突发流量

        Args:
            sample_count: 采样数量默认为5，即计算最近5条消息（4个间隔）的平均值
            default_interval: 缺省时的补偿间隔（秒）

        Returns:
            float: 平均间隔秒数
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

        直接计算采样范围内的时间跨度除以间隔数，不进行任何填充
        能够最快地反映出当前的瞬时流量密度

        Args:
            sample_count: 采样数量（即计算最近 N 条消息的跨度）

        Returns:
            float: 平均间隔秒数如果消息不足 2 条，返回 float('inf')
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

    def __init__(self, window_time: int = 60):
        """初始化时间窗口

        Args:
            window_time: 时间窗口的大小，单位秒必须为正整数

        Raises:
            ValueError: 如果 window_time 不是正整数
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
        return time.time() - self.last_msg_at

    def get_seconds_since_user_time(self) -> float:
        """获取距离上一次user触发发言时间(秒级)"""
        return time.time() - self.last_trigger_user_time

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

    group_id: int
    """群号"""
    messages: deque[MessageEvent] = field(init=False)
    """消息列表"""
    group_max_record: int
    """群维持的消息数量"""
    last_msg_at: float = field(default=time.time(), init=False)
    """群最后一次添加消息的时间"""

    chat_context: Context
    """群LLM聊天上下文"""
    play_roles: str
    """当前LLM聊天人设名称"""
    IS_SUMMARIZING: bool = field(default=False, init=False)
    """是否在总结"""
    summarize_message_count: int = field(default=0, init=False)
    """未总结的计数"""
    time_window: TimeWindow = field(init=False)
    """统计群近期消息数量的窗口对象"""
    LLM_chat_decision_parameters: LLMGroupChatCondition = field(init=False)
    """LLM聊天决策使用的一些参数"""
    async_summarize_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """群异步总结锁"""
    async_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """群异步锁"""
    initiative_chat: bool = field(default=False)
    """是否启用主动加入聊天"""
    information_extraction: bool = field(default=False)
    """是否启用群信息提取"""

    def __post_init__(self, window_time: int = 60):
        self.messages = deque(maxlen=self.group_max_record)
        self.time_window = TimeWindow(window_time)
        self.LLM_chat_decision_parameters = LLMGroupChatCondition(window_time)

    def __iter__(self):
        return iter(self.messages)

    def update_time(self):
        """更新群组的最新使用时间"""
        self.last_msg_at = time.time()

    def _record_validity_check(self) -> List[str] | None:
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
        return "".join(ev.llm_formatted_message for ev in self.messages)

    async def add_group_chat_event(
        self, event: atriMessageEvent
    ) -> tuple[str, GroupContext] | None:
        """基于 atriMessageEvent 存储消息到群上下文

        将 event.event (OneBotEvent) 存入 messages 队列，
        达到阈值时触发记忆总结

        Args:
            event: 新系统的消息事件对象

        Returns:
            需要总结时返回 (消息文本, self)
        """
        async with self.async_lock:
            self.last_msg_at = time.time()
            self.messages.append(event.event)
            self.summarize_message_count += 1
            messages_to_summarize = self._record_validity_check()

            if self.information_extraction and messages_to_summarize is not None:
                return (messages_to_summarize, self)

        return None

    @asynccontextmanager
    async def summarizing(self):
        """
        如果上一轮总结还没跑完，会直接跳过（返回 None
        否则把 IS_SUMMARIZING 置 True 退出块时自动复位
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
    """私聊上下文"""

    user_id: int
    """user的qq号"""
    chat_context: Context
    """私聊LLM聊天上下文"""
    play_roles: str
    """当前LLM聊天人设名称"""
    max_record: int = 30
    """私聊维持的消息数量(默认30)"""

    messages: deque[MessageEvent] = field(init=False)
    """消息列表"""
    async_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """异步锁"""
    last_msg_at: float = field(default=time.monotonic(), init=False)
    """最后一次消息的使用时间"""
    time_window: TimeWindow = field(init=False)
    """统计近期消息数量的窗口对象"""
    IS_SUMMARIZING: bool = field(default=False, init=False)
    """是否在总结"""
    summarize_message_count: int = field(default=0, init=False)
    """未总结的计数"""
    async_summarize_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """私聊异步总结锁"""

    def __post_init__(self, window_time: int = 60):
        self.messages = deque(maxlen=self.max_record)
        self.time_window = TimeWindow(window_time)

    def update_time(self):
        """更新私聊类的最新使用时间"""
        self.last_msg_at = time.time()

    def build_context(self) -> str:
        """返回构建的LLM文本上下文"""
        return "".join(ev.llm_formatted_message for ev in self.messages)

    def _record_validity_check(self) -> List[str] | None:
        """针对私聊消息条数的验证

        Returns:
            List[str]: 要总结的原始消息列表(如果达到阈值)
        """
        if self.summarize_message_count >= self.max_record:
            self.summarize_message_count = 0
            return self.build_context()
        return None

    async def add_private_chat_event(
        self, event: atriMessageEvent
    ) -> tuple[str, PrivateContext] | None:
        """基于 atriMessageEvent 存储消息到私聊上下文

        Args:
            event: 新系统的消息事件对象

        Returns:
            需要总结时返回 (消息文本, self)
        """
        async with self.async_lock:
            self.last_msg_at = time.time()
            self.messages.append(event.event)
            self.summarize_message_count += 1
            messages_to_summarize = self._record_validity_check()

            if messages_to_summarize is not None:
                return (messages_to_summarize, self)

        return None

    @asynccontextmanager
    async def summarizing(self):
        """
        如果上一轮总结还没跑完，会直接跳过（返回 None
        否则把 IS_SUMMARIZING 置 True 退出块时自动复位
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
