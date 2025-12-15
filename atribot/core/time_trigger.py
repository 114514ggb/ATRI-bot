import asyncio
import time
import inspect
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional
from atribot.core.service_container import container




class TimeUnit:
    """触发器时间单位"""
    SECOND = 1
    MINUTE = 60 * SECOND
    HOUR = 60 * MINUTE
    DAY = 24 * HOUR
    WEEK = 7 * DAY

@dataclass
class TriggerTime:
    """周期性触发时间偏移配置"""
    seconds: float = 0.0
    
    def add(self, value: float, unit: int = TimeUnit.SECOND) -> None:
        self.seconds += value * unit
    
    def subtract(self, value: float, unit: int = TimeUnit.SECOND) -> None:
        self.seconds = max(0, self.seconds - value * unit)
    
    @classmethod
    def from_seconds(cls, count: float = 1) -> 'TriggerTime':
        return cls(count)
    
    @classmethod
    def from_minutes(cls, count: float = 1) -> 'TriggerTime':
        return cls(count * TimeUnit.MINUTE)

@dataclass
class TimedTask:
    """定时任务配置"""
    
    task_id: int
    """任务唯一标识"""
    trigger_time: float
    """触发时间戳，单位为秒"""
    func: Callable[..., Any]
    """触发时执行的函数 (支持 async 或 sync)"""
    kwargs: Dict[str, Any] = field(default_factory=dict)
    """传递给函数的关键字参数"""
    interval_time: Optional[TriggerTime] = None
    """触发间隔时间配置"""
    one_shot: bool = True
    """是否一次性任务"""
    remarks: str = ""
    """任务备注信息"""
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}
        if not self.one_shot and self.interval_time is None:
            raise ValueError("非一次性任务必须设置 interval_time")
    
    def get_distance_trigger_time(self) -> float:
        """获取距离下次触发的秒数，如果是周期任务会自动推进 trigger_time"""
        now = time.time()
        if self.one_shot:
            return -1.0 if self.trigger_time <= now else self.trigger_time - now
        else:
            # 如果当前时间已经超过触发时间，推进到未来最近的一个时间点
            while self.trigger_time <= now:
                self.trigger_time += self.interval_time.seconds
            return self.trigger_time - now

class TimeTriggerSupervisor:
    """
    异步时间触发管理器
    维护一个按时间排序的任务队列，每次只休眠到最近的一个任务触发点。
    """
    
    def __init__(self):
        self.logger:logging.Logger = container.get("log")
        self.trigger_tasks: Dict[float, List[TimedTask]] = {}
        """时间触发表，按时间戳分组存储任务"""
        self.task_map: Dict[int, TimedTask] = {}
        """任务 ID 映射表，方便通过 ID 快速查找和删除任务"""
        
        # 用于唤醒主循环的事件
        self._wakeup_event = asyncio.Event()
        self._running = False
        self._main_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._main_task = asyncio.create_task(self._loop())
        self.logger.info("时间触发器管理已启动!")
        
    async def stop(self):
        """停止调度器"""
        self._running = False
        self._wakeup_event.set() 
        if self._main_task:
            await self._main_task
        self.logger.info("时间触发器管理已关闭")

    def add_task(self, task: TimedTask):
        """
        添加任务
        如果 task_id 已存在，会先移除旧任务再添加新任务（覆盖）。
        """
        if task.task_id in self.task_map:
            self.logger.debug(f"Task ID {task.task_id} exists, updating task.")
            self.remove_task(task.task_id)

        if not task.one_shot and task.trigger_time <= time.time():
            task.get_distance_trigger_time()

        self.task_map[task.task_id] = task

        if task.trigger_time not in self.trigger_tasks:
            self.trigger_tasks[task.trigger_time] = []
        self.trigger_tasks[task.trigger_time].append(task)
        
        self.logger.debug(f"添加定时任务 [ID:{task.task_id}]: {task.func.__name__} 在 {task.trigger_time} 备注: {task.remarks}")

        self._wakeup_event.set()

    def remove_task(self, task_id: int) -> bool:
        """
        根据 task_id 删除任务
        :return: 是否成功删除
        """
        task = self.task_map.pop(task_id, None)
        if not task:
            return False
            
        ts = task.trigger_time
        if ts in self.trigger_tasks:
            if task in self.trigger_tasks[ts]:
                self.trigger_tasks[ts].remove(task)
                if not self.trigger_tasks[ts]:
                    del self.trigger_tasks[ts]
        
        self.logger.debug(f"移除定时任务 [ID:{task_id}]")
        self._wakeup_event.set()
        return True

    def get_task(self, task_id: int) -> Optional[TimedTask]:
        """获取任务信息"""
        return self.task_map.get(task_id)

    async def _loop(self):
        """主调度循环"""
        while self._running:
            self._wakeup_event.clear()
            
            now = time.time()
            next_wake_time = None
            
            sorted_timestamps = sorted(self.trigger_tasks.keys())
            
            tasks_to_run: List[TimedTask] = []
            timestamps_to_remove: List[float] = []
            
            for ts in sorted_timestamps:
                if ts <= now:
                    tasks_to_run.extend(self.trigger_tasks[ts])
                    timestamps_to_remove.append(ts)
                else:
                    next_wake_time = ts
                    break
            
            # 清理已过期的 key (注意：此时 task_map 中还保留着引用)
            for ts in timestamps_to_remove:
                del self.trigger_tasks[ts]
            
            # 执行任务
            for task in tasks_to_run:
                # 再次检查 task_map，防止在执行前一瞬间被 remove_task 删除了
                if task.task_id not in self.task_map:
                    continue

                # 异步执行
                asyncio.create_task(self._execute_task_safe(task))
                
                if task.one_shot:
                    # 一次性任务：执行完后从 map 中彻底移除
                    self.task_map.pop(task.task_id)
                else:
                    # 周期性任务：计算下次时间并重新添加
                    task.trigger_time += task.interval_time.seconds
                    self.add_task(task)

            if not self._running:
                break

            # 如果刚才有任务执行（特别是周期任务重新添加），立即进入下一次检查，不休眠
            if tasks_to_run:
                continue

            if next_wake_time is None:
                self.logger.debug("时间触发器没有任务,无限等待...")
                await self._wakeup_event.wait()
            else:
                delay = next_wake_time - time.time()
                if delay > 0:
                    try:
                        await asyncio.wait_for(self._wakeup_event.wait(), timeout=delay)
                    except asyncio.TimeoutError:
                        pass
                else:
                    pass

    async def _execute_task_safe(self, task: TimedTask):
        """安全执行任务，捕获异常"""
        try:
            if inspect.iscoroutinefunction(task.func):
                await task.func(**task.kwargs)
            else:
                await asyncio.to_thread(task.func, **task.kwargs)
        except Exception as e:
            self.logger.error(f"执行任务 [ID:{task.task_id}] {task.func.__name__} 时出错: {e}", exc_info=True)
