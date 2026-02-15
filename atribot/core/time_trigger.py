import asyncio
import heapq
from dataclasses import dataclass, field
from datetime import datetime
from logging import Logger
from typing import Any, Callable, Dict, List, Optional

from croniter import croniter

from atribot.core.service_container import container


@dataclass(order=True, slots=True)
class TimedTask:
    """定时任务对象实体。
    用于封装调度任务所需的元数据。
    """

    trigger_timestamp: float
    """触发的时间戳（基于 loop.time() 的单调时间），排序的第一关键字"""

    priority: int
    """任务优先级，数值越小优先级越高（同时间戳下优先执行），排序的第二关键字"""

    task_id: int = field(compare=False)
    """任务的唯一标识符，不参与排序"""

    func: Callable = field(compare=False)
    """触发时执行的可调用对象（支持 async 协程或普通函数），不参与排序"""

    kwargs: Dict[str, Any] = field(compare=False, default_factory=dict)
    """传递给执行函数的关键字参数，不参与排序"""

    interval: float = field(compare=False, default=0.0)
    """循环执行的间隔时间（秒）。0.0 表示一次性任务，不参与排序"""

    cron_expression: Optional[str] = field(compare=False, default=None)
    """Cron 表达式字符串。如果设置，将忽略 interval"""

    remarks: str = field(compare=False, default="")
    """任务备注信息，用于日志或调试，不参与排序"""
    
    cancelled: bool = field(compare=False, default=False)
    """任务取消标记，用于惰性删除（Lazy Deletion），不参与排序"""


class TimeTriggerSupervisor:
    """基于 asyncio 和最小堆的高效时间调度器。

    使用 asyncio.Event 实现精确的睡眠唤醒机制，避免了轮询（busy loop）
    支持一次性任务和周期性任务的调度
    """

    def __init__(self):
        self.logger:Logger = container.get("log")
        self._queue: List[TimedTask] = []
        """任务最小堆：存储 TimedTask 对象，堆顶永远是最近需要执行的任务"""
        self._task_map: Dict[int, TimedTask] = {}
        """任务索引表：用于通过 task_id 快速查找任务（O(1)），主要用于取消任务"""
        self._wakeup_event = asyncio.Event()
        """唤醒事件：当有新任务插入且比堆顶任务更早执行时，用于唤醒主循环"""
        self._running = False
        """调度器运行状态标记"""
        self._main_task: Optional[asyncio.Task] = None
        """调度器的主循环协程任务对象"""

    def now(self) -> float:
        """获取当前的单调时间。

        Returns:
            float: 当前事件循环的时间戳（秒）。
        """
        return asyncio.get_running_loop().time()

    def _calc_cron_delay(self, cron_exp: str) -> float:
        """计算 Cron 表达式距离下一次执行的秒数差。

        利用 croniter 根据当前系统时间（墙上时间）计算下一次触发的时间点，
        并返回该时间点距离现在的秒数。

        Args:
            cron_exp (str): 标准的 Cron 表达式字符串 (例如 "*/5 * * * *")。

        Returns:
            float: 距离下一次执行的秒数 (delay)。
        """
        now_dt = datetime.now()
        delay = (croniter(cron_exp, now_dt).get_next(datetime) - now_dt).total_seconds()
        if delay > 0:
            return delay
        else:
            return 0

    def add_task(
        self, 
        task_id: int, 
        func: Callable, 
        trigger_delta: float, 
        priority: int = 10,
        interval: float = 0.0, 
        kwargs: Optional[dict] = None, 
        remarks: str = ""
    ):
        """添加一个新的定时任务到调度器。

        如果 task_id 已存在，旧任务将被标记取消并被新任务替换。

        Args:
            task_id (int): 任务的唯一标识 ID
            func (Callable): 任务触发时执行的函数
            trigger_delta (float): 延迟多少秒后执行（相对于当前时间）
            priority(int): 任务的优先级,越小越高
            interval (float, optional): 循环执行间隔。默认为 0.0（一次性任务）
            kwargs (dict, optional): 传递给 func 的参数字典。默认为 None
            remarks (str, optional): 任务备注信息。默认为空字符串
        """
        self._add_task_internal(
            task_id, func, trigger_delta, priority, interval, None, kwargs, remarks
        )

    def add_cron_task(
        self,
        task_id: int,
        func: Callable,
        cron_expression: str,
        priority: int = 10,
        kwargs: Optional[dict] = None,
        remarks: str = ""
    ):
        """添加一个基于 Cron 表达式调度的定时任务。

        该方法会校验 Cron 表达式的合法性，计算首次执行的延迟时间，并将任务加入调度队列。
        任务执行后会根据 Cron 规则自动重新调度。

        Args:
            task_id (int): 任务的唯一标识 ID。如果 ID 已存在，旧任务将被替换。
            func (Callable): 任务触发时执行的可调用对象（支持协程或普通函数）。
            cron_expression (str): Cron 调度表达式 (例如 "30 8 * * 1" 表示每周一 08:30)。
                支持 croniter 允许的 5 位或 6 位（含秒）格式。
            priority (int, optional): 任务优先级，数值越小优先级越高。默认为 10。
            kwargs (dict, optional): 传递给 func 的关键字参数字典。默认为 None。
            remarks (str, optional): 任务备注信息，用于日志或调试。默认为空字符串。

        Raises:
            ValueError: 如果提供的 `cron_expression` 格式无效。
        """
        if not croniter.is_valid(cron_expression):
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        now_dt = datetime.now()
        next_dt = croniter(cron_expression, now_dt).get_next(datetime)
        delay = (next_dt - now_dt).total_seconds()
        delay = delay if delay > 0 else 0
        
        self._add_task_internal(
            task_id, func, delay, priority, 0.0, cron_expression, kwargs, remarks
        )
    
    def _add_task_internal(
        self, 
        task_id: int, 
        func: Callable, 
        trigger_delta: float, 
        priority: int, 
        interval: float, 
        cron_expression: Optional[str], 
        kwargs: Optional[Dict[str, Any]], 
        remarks: str
    ) -> None:
        """内部辅助方法：统一处理任务对象的创建与入队逻辑。

        负责封装 TimedTask 对象，更新任务索引表，将任务推入最小堆，
        并触发唤醒事件以通知主循环重新计算休眠时间。

        Args:
            task_id (int): 任务的唯一标识 ID。
            func (Callable): 任务触发时执行的可调用对象（支持协程或普通函数）。
            trigger_delta (float): 距离触发的延迟秒数（相对于当前 loop 时间）。
            priority (int): 任务优先级，数值越小优先级越高。
            interval (float): 固定循环执行的间隔时间（秒）。0.0 表示非周期性任务。
            cron_expression (Optional[str]): 标准 Cron 表达式字符串（例如 "*/5 * * * *"）。
                如果提供了此参数，任务将被视为 Cron 任务，interval 参数将被忽略。
            kwargs (Optional[Dict[str, Any]]): 传递给 func 的关键字参数字典。
            remarks (str): 任务备注信息，用于日志记录或调试。
        """
        if kwargs is None: 
            kwargs = {}
        
        if task_id in self._task_map:
            self.remove_task(task_id)

        trigger_time = self.now() + trigger_delta
        
        task = TimedTask(
            trigger_timestamp=trigger_time,
            priority=priority,
            task_id=task_id,
            func=func,
            kwargs=kwargs,
            interval=interval,
            cron_expression=cron_expression,
            remarks=remarks
        )
        
        self._task_map[task_id] = task
        heapq.heappush(self._queue, task)
        
        self.logger.debug(f"添加任务 {task_id} [{f"Cron({cron_expression})" if cron_expression else f"Delay({trigger_delta:.2f}s)"}], 将在 {trigger_delta:.2f}s 后执行")
        
        self._wakeup_event.set()

    def remove_task(self, task_id: int) -> bool:
        """移除指定的任务

        采用逻辑删除（Lazy Deletion）：只在 map 中移除并标记 cancelled，
        堆中的残留对象将在弹出时被丢弃。

        Args:
            task_id (int): 要移除的任务 ID。

        Returns:
            bool: 如果任务存在并被移除返回 True，否则返回 False。
        """
        if task_id in self._task_map:
            task = self._task_map.pop(task_id)
            task.cancelled = True
            self.logger.debug(f"移除任务 {task_id}")
            return True
        return False

    async def start(self):
        """启动调度器主循环。"""
        if self._running: 
            return
        self._running = True
        self._main_task = asyncio.create_task(self._loop())
        self.logger.info("调度器启动")

    async def stop(self):
        """停止调度器并等待主循环结束。"""
        self._running = False
        self._wakeup_event.set()
        if self._main_task:
            await self._main_task

    async def _loop(self):
        """调度器的主事件循环。
        
        负责监控堆顶任务、处理休眠等待、执行任务以及重新调度周期性任务。
        """
        while self._running:
            # 1. 清除事件信号，准备进入等待
            self._wakeup_event.clear()
            
            now = self.now()
            
            # 2. 处理所有已到期的任务
            while self._queue:
                # 偷看堆顶任务
                task = self._queue[0]
                
                # 清理已取消的任务
                if task.cancelled:
                    heapq.heappop(self._queue)
                    continue
                
                # 如果堆顶任务还没到时间，停止处理
                if task.trigger_timestamp > now:
                    break
                
                # 弹出并执行任务
                task = heapq.heappop(self._queue)
                
                # 再次检查取消标记（防止并发边缘情况）
                if not task.cancelled:
                    asyncio.create_task(self._execute_safe(task))
                    self._reschedule_task(task)
                else:
                    # 如果被取消了，从 map 中彻底移除（虽然 remove_task 已经 pop 了，这里是兜底）
                    self._task_map.pop(task.task_id, None)

            # 3. 计算下一次唤醒的休眠时间
            sleep_time = None
            
            # 清理堆顶可能的已取消任务，确保计算准确
            while self._queue and self._queue[0].cancelled:
                heapq.heappop(self._queue)

            if self._queue:
                # 还有任务：计算距离最近任务的时间差
                next_task = self._queue[0]
                sleep_time = next_task.trigger_timestamp - self.now()
                # 确保 sleep_time 不为负数
                if sleep_time < 0:
                    sleep_time = 0
            
            # 4. 等待：要么超时（时间到了），要么被新任务唤醒
            try:
                if sleep_time is None:
                    self.logger.info("没有任务time调度器无限等待!")
                    await self._wakeup_event.wait()
                else:
                    # 等待指定时间，或者被新任务打断
                    await asyncio.wait_for(self._wakeup_event.wait(), timeout=sleep_time)
            except asyncio.TimeoutError:
                # 超时意味着时间到了，进入下一次循环处理任务
                pass
            except asyncio.CancelledError:
                self.logger.info("调度器停止!")
                break

    def _reschedule_task(self, task: TimedTask):
        """处理周期性任务的重新调度逻辑。

        根据任务配置（Cron 表达式或固定间隔）计算下一次触发的时间戳，
        并将任务重新推入调度队列（最小堆）。如果任务是一次性的（非周期任务），
        则从任务索引表（_task_map）中彻底移除。

        Args:
            task (TimedTask): 刚刚被弹出并提交执行的任务对象。
        """
        reschedule = False
        
        if task.cron_expression:
            # Cron 任务：基于当前系统时间计算下一次
            current_dt = datetime.now()
            try:
                # 创建新的 croniter 对象以避免状态漂移，并基于当前时间计算
                next_dt = croniter(task.cron_expression, current_dt).get_next(datetime)
                delay = (next_dt - current_dt).total_seconds()
                task.trigger_timestamp = self.now() + delay
                reschedule = True
                self.logger.debug(f"Cron[{task.task_id}] 下次: {next_dt} (+{delay:.1f}s)")
            except Exception as e:
                self.logger.error(f"Cron 计算错误 task {task.task_id}: {e}")
                
        elif task.interval > 0:
            # 普通周期任务：基于上次理论触发时间累加，防止漂移
            task.trigger_timestamp += task.interval
            
            # 如果落后当前时间太多（例如系统休眠后），重置为当前时间+间隔
            if task.trigger_timestamp < self.now():
                task.trigger_timestamp = self.now() + task.interval
                
            reschedule = True

        if reschedule:
            heapq.heappush(self._queue, task)
        else:
            # 一次性任务，执行完后从索引表移除
            self._task_map.pop(task.task_id, None)
                        
    async def _execute_safe(self, task: TimedTask):
        """安全执行任务，捕获并记录异常。

        Args:
            task (TimedTask): 要执行的任务对象。
        """
        try:
            if asyncio.iscoroutinefunction(task.func):
                await task.func(**task.kwargs)
            else:
                # 如果是同步阻塞函数，放到线程池中运行，避免阻塞事件循环
                await asyncio.to_thread(task.func, **task.kwargs)
        except Exception as e:
            self.logger.error(f"任务 {task.task_id} 执行异常: {e}", exc_info=True)
            

