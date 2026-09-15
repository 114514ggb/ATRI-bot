import asyncio
import bisect
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Hashable, List

from atribot.core.type.context_types import Context

if TYPE_CHECKING:
    from atribot.core.type.bot_types import atriMessageEvent
    from atribot.core.type.onebot_event_types import MessageEvent

_logger = logging.getLogger(__name__)


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


class WindowCloseReason(Enum):
    """聚合窗口关闭的原因"""

    TIMEOUT = "timeout"
    """窗口时间内无新消息,认为输入已结束"""
    CAPACITY = "capacity"
    """缓冲条数达到上限,提前触发"""
    MANUAL = "manual"
    """外部手动触发"""


@dataclass(slots=True)
class _AggregationSlot[T]:
    """单个 key 的聚合缓冲状态"""

    buffer: list[T]
    """已累积的消息列表,按时间升序"""
    timer: asyncio.TimerHandle | None = None
    """当前计时的定时器句柄,新消息到达时会被替换"""
    draining: bool = False
    """是否有串行消费者在处理该 key 的批次"""


class MessageAggregationWindow[T]:
    """按键聚合的消息缓冲窗口

    同一 key 的消息持续到达会不断重置计时窗口并被累积;
    超过 window_seconds 无新消息、缓冲达到 max_buffer_size
    或被手动 flush 时,把整批消息连同关闭原因交给 on_flush 回调。
    回调执行期间该 key 新到的消息会并入缓冲,等回调完成后立即
    作为下一轮整批处理——同一 key 的回调始终串行,不会并发

    Usage:
        需在事件循环内调用 add();回调在独立的内部任务中执行,
        不会阻塞其他 key 的窗口计时
    """

    __slots__ = ("window_seconds", "max_buffer_size", "on_flush", "_flushing_tasks", "_slots")

    window_seconds: float
    """无新消息多久后关闭窗口,单位秒"""
    max_buffer_size: int | None
    """单批条数上限,达到后立即触发;None 表示不限制"""
    on_flush: Callable[[Hashable, list[T], WindowCloseReason], Coroutine[Any, Any, None]]
    """窗口关闭回调,接收 (key, 整批消息, 关闭原因)"""
    _flushing_tasks: set[asyncio.Task]
    """进行中的回调任务强引用集(防止GC回收)"""
    _slots: dict[Hashable, _AggregationSlot[T]]
    """各 key 的缓冲状态表"""

    def __init__(
        self,
        *,
        on_flush: Callable[[Hashable, list[T], WindowCloseReason], Coroutine[Any, Any, None]],
        window_seconds: float = 7.0,
        max_buffer_size: int | None = None,
    ) -> None:
        """初始化聚合窗口

        Args:
            on_flush: 窗口关闭回调,接收 (key, 整批消息, 关闭原因)
            window_seconds: 无新消息多久后关闭窗口,单位秒,必须为正数
            max_buffer_size: 单批条数上限,达到后立即触发;None 表示不限制

        Raises:
            ValueError: window_seconds 非正数,或 max_buffer_size 非正整数
        """
        self.window_seconds = window_seconds
        self.max_buffer_size = max_buffer_size
        self.on_flush = on_flush
        self._flushing_tasks = set()
        self._slots = {}

    def add(self, key: Hashable, item: T) -> None:
        """向指定 key 的缓冲追加一条消息,并重置该 key 的计时窗口

        Args:
            key: 聚合键
            item: 消息对象
        """
        slot = self._slots.get(key)
        if slot is None:
            slot = _AggregationSlot(buffer=[])
            self._slots[key] = slot

        slot.buffer.append(item)

        if slot.draining:
            return

        if self.max_buffer_size is not None and len(slot.buffer) >= self.max_buffer_size:
            self._start_drain(key, slot, WindowCloseReason.CAPACITY)
            return

        if slot.timer is not None:
            slot.timer.cancel()
        slot.timer = asyncio.get_running_loop().call_later(
            self.window_seconds, self._on_window_elapsed, key, slot
        )

    def flush(self, key: Hashable, reason: WindowCloseReason = WindowCloseReason.MANUAL) -> list[T] | None:
        """立即触发指定 key 的窗口,把缓冲整批交给回调处理

        Args:
            key: 聚合键
            reason: 触发原因,默认 MANUAL

        Returns:
            调用时刻的缓冲快照(即将被处理);key 不存在、缓冲为空或正在消费中返回 None
        """
        slot = self._slots.get(key)
        if slot is None or slot.draining or not slot.buffer:
            return None
        snapshot = list(slot.buffer)
        self._start_drain(key, slot, reason)
        return snapshot

    def cancel(self, key: Hashable) -> list[T] | None:
        """丢弃指定 key 的缓冲,不触发回调

        Returns:
            被丢弃的整批消息;key 不存在或缓冲为空时返回 None
        """
        slot = self._slots.pop(key, None)
        if slot is None:
            return None
        if slot.timer is not None:
            slot.timer.cancel()
        return slot.buffer if slot.buffer else None

    def pending(self, key: Hashable) -> int:
        """返回指定 key 当前缓冲的消息条数"""
        slot = self._slots.get(key)
        return len(slot.buffer) if slot else 0

    def close(self) -> None:
        """清理全部缓冲"""
        for key in list(self._slots):
            self.cancel(key)

    def _on_window_elapsed(self, key: Hashable, slot: _AggregationSlot[T]) -> None:
        """单 key 计时到期,启动串行消费(陈旧防护统一在 _start_drain 入口)"""
        slot.timer = None
        self._start_drain(key, slot, WindowCloseReason.TIMEOUT)

    def _start_drain(self, key: Hashable, slot: _AggregationSlot[T], reason: WindowCloseReason) -> None:
        """串行消费者"""
        if self._slots.get(key) is not slot or slot.draining:
            return
        slot.draining = True
        if slot.timer is not None:
            slot.timer.cancel()
            slot.timer = None
        task = asyncio.get_running_loop().create_task(self._drain_routine(key, slot, reason))
        self._flushing_tasks.add(task)
        task.add_done_callback(self._flushing_tasks.discard)

    async def _drain_routine(self, key: Hashable, slot: _AggregationSlot[T], reason: WindowCloseReason) -> None:
        """串行消费该key的批次"""
        try:
            while self._slots.get(key) is slot:
                if not slot.buffer:
                    del self._slots[key]
                    return
                batch = slot.buffer
                slot.buffer = []
                try:
                    await self.on_flush(key, batch, reason)
                except Exception:
                    #一批失败不中断循环,后续批次照常处理
                    _logger.exception("聚合窗口 on_flush 回调执行失败(key=%r, 批次大小=%d)", key, len(batch))
        finally:
            slot.draining = False
