import asyncio
import heapq
from dataclasses import dataclass, field
from datetime import datetime
from logging import Logger
from typing import Any, Callable, Dict, List, Optional, Set

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
    
    timeout: float = field(compare=False, default=5.0)
    """单次任务执行超时时间（秒），不参与排序"""
    
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
        """任务索引表：用于通过task_id快速查找任务，主要用于取消任务"""
        self._wakeup_event = asyncio.Event()
        """唤醒事件：当有新任务插入且比堆顶任务更早执行时，用于唤醒主循环"""
        self._running = False
        """调度器运行状态标记"""
        self._main_task: Optional[asyncio.Task] = None
        """调度器的主循环协程任务对象"""
        self._running_tasks: Set[asyncio.Task] = set()
        """当前正在执行的任务集合，用于关闭时统一等待或取消"""

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
        timeout: float = 5.0,
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
            timeout (float, optional): 单次执行超时时间（秒）。默认为 5.0。
            kwargs (dict, optional): 传递给 func 的参数字典。默认为 None
            remarks (str, optional): 任务备注信息。默认为空字符串
        """
        self._add_task_internal(
            task_id, func, trigger_delta, priority, interval, None, timeout, kwargs, remarks
        )

    def add_cron_task(
        self,
        task_id: int,
        func: Callable,
        cron_expression: str,
        priority: int = 10,
        timeout: float = 5.0,
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
            timeout (float, optional): 单次执行超时时间（秒）。默认为 5.0。
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
            task_id, func, delay, priority, 0.0, cron_expression, timeout, kwargs, remarks
        )
    
    def _add_task_internal(
        self, 
        task_id: int, 
        func: Callable, 
        trigger_delta: float, 
        priority: int, 
        interval: float, 
        cron_expression: Optional[str], 
        timeout: float,
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
            timeout (float): 单次任务执行超时时间（秒）。
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
            timeout=timeout,
            func=func,
            kwargs=kwargs,
            interval=interval,
            cron_expression=cron_expression,
            remarks=remarks
        )
        
        self._task_map[task_id] = task
        heapq.heappush(self._queue, task)
        mode = f"Cron({cron_expression})" if cron_expression else f"Delay({trigger_delta:.2f}s)"
        self.logger.debug(f"添加任务 {task_id} [{mode}], 将在 {trigger_delta:.2f}s 后执行，单次超时 {timeout:.2f}s")
        
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

    async def stop(self, timeout: float = 5.0):
        """停止调度器，并在超时后强制取消所有相关任务。"""
        self._running = False
        self._cancel_scheduled_tasks()
        self._wakeup_event.set()

        if self._main_task:
            try:
                await asyncio.wait_for(asyncio.shield(self._main_task), timeout=timeout)
            except asyncio.TimeoutError:
                self.logger.warning(f"调度器主循环在 {timeout:.1f}s 内未正常退出，开始强制取消")
                self._main_task.cancel()
                await asyncio.gather(self._main_task, return_exceptions=True)
            finally:
                self._main_task = None

        await self._stop_running_tasks(timeout)
        self.logger.info("调度器已停止")

    def _cancel_scheduled_tasks(self) -> None:
        """取消所有尚未开始执行的调度任务。"""
        for task in self._task_map.values():
            task.cancelled = True

        self._task_map.clear()
        self._queue.clear()

    async def _stop_running_tasks(self, timeout: float) -> None:
        """等待执行中任务结束，超时后统一取消。"""
        if not self._running_tasks:
            return

        done, pending = await asyncio.wait(list(self._running_tasks), timeout=timeout)

        for task in done:
            try:
                await task
            except (Exception, asyncio.CancelledError):
                pass

        if not pending:
            return

        self.logger.warning(f"有 {len(pending)} 个执行中任务在 {timeout:.1f}s 内未结束，开始强制取消")
        for task in pending:
            task.cancel()

        await asyncio.gather(*pending, return_exceptions=True)

    def _track_running_task(self, task: asyncio.Task) -> None:
        """记录执行中的任务，并在结束后自动移除。"""
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)

    async def _loop(self):
        """调度器的主事件循环。
        
        负责监控堆顶任务、处理休眠等待、执行任务以及重新调度周期性任务。
        """
        while self._running:
            # 1. 清除事件信号，准备进入等待
            self._wakeup_event.clear()

            # 缓存当前时间，同一轮次复用，避免多次调用 loop.time()
            now = self.now()

            # 2. 处理所有已到期的任务
            while self._queue:
                task = self._queue[0]

                # 清理堆顶已取消的任务（lazy deletion）
                if task.cancelled:
                    heapq.heappop(self._queue)
                    continue

                # 堆顶任务未到期，停止处理
                if task.trigger_timestamp > now:
                    break

                task = heapq.heappop(self._queue)

                if not task.cancelled:
                    execution_task = asyncio.create_task(self._execute_safe(task))
                    self._track_running_task(execution_task)
                    if self._running:
                        self._reschedule_task(task, now)
                    else:
                        self._task_map.pop(task.task_id, None)
                else:
                    self._task_map.pop(task.task_id, None)

            # 3. 计算下一次唤醒的休眠时间
            sleep_time: Optional[float] = None
            if self._queue:
                sleep_time = self._queue[0].trigger_timestamp - self.now()
                if sleep_time < 0:
                    sleep_time = 0

            # 4. 等待：要么超时（时间到），要么被新任务唤醒
            try:
                if sleep_time is None:
                    self.logger.info("没有任务，调度器无限等待...")
                    await self._wakeup_event.wait()
                else:
                    await asyncio.wait_for(self._wakeup_event.wait(), timeout=sleep_time)
            except asyncio.TimeoutError:
                # 超时即时间到，进入下一轮处理
                pass
            except asyncio.CancelledError:
                self.logger.info("调度器主循环被取消，退出")
                break

    def _reschedule_task(self, task: TimedTask, now: float):
        """处理周期性任务的重新调度逻辑。

        根据任务配置（Cron 表达式或固定间隔）计算下一次触发的时间戳，
        并将任务重新推入调度队列（最小堆）。如果任务是一次性的（非周期任务），
        则从任务索引表（_task_map）中彻底移除。

        Args:
            task (TimedTask): 刚刚被弹出并提交执行的任务对象
            now (float): 调用方缓存的当前单调时间
        """
        reschedule = False

        if task.cron_expression:
            current_dt = datetime.now()
            try:
                next_dt = croniter(task.cron_expression, current_dt).get_next(datetime)
                delay = (next_dt - current_dt).total_seconds()
                task.trigger_timestamp = now + delay
                reschedule = True
                self.logger.debug(f"Cron[{task.task_id}] 下次: {next_dt} (+{delay:.1f}s)")
            except Exception as e:
                self.logger.error(f"Cron 计算错误 task {task.task_id}: {e}")

        elif task.interval > 0:
            task.trigger_timestamp += task.interval
            # 防止系统休眠等场景导致时间戳严重落后
            if task.trigger_timestamp < now:
                task.trigger_timestamp = now + task.interval
            reschedule = True

        if reschedule:
            heapq.heappush(self._queue, task)
        else:
            self._task_map.pop(task.task_id, None)
                        
    async def _execute_safe(self, task: TimedTask):
        """安全执行任务，捕获并记录异常。

        Args:
            task (TimedTask): 要执行的任务对象。
        """
        try:
            if asyncio.iscoroutinefunction(task.func):
                execution = task.func(**task.kwargs)
            else:
                execution = asyncio.to_thread(task.func, **task.kwargs)

            if task.timeout > 0:
                await asyncio.wait_for(execution, timeout=task.timeout)
            else:
                await execution
        except asyncio.TimeoutError:
            remarks = f"，备注: {task.remarks}" if task.remarks else ""
            self.logger.warning(
                f"任务 {task.task_id} 执行超时，限制 {task.timeout:.2f}s{remarks}"
            )
            if not asyncio.iscoroutinefunction(task.func):
                self.logger.warning(f"任务 {task.task_id} 为同步任务，线程池中的实际执行可能仍会继续")
        except asyncio.CancelledError:
            self.logger.info(f"任务 {task.task_id} 在关闭过程中被取消")
            raise
        except Exception as e:
            self.logger.error(f"任务 {task.task_id} 执行异常: {e}", exc_info=True)
            

