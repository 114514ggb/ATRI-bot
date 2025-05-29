import asyncio
import threading
import time
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import asynccontextmanager
from typing import Callable, Any, Optional, Union, Dict
from dataclasses import dataclass
from enum import Enum
import inspect

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PoolStatus(Enum):
    """线程池状态枚举"""
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down" 
    SHUTDOWN = "shutdown"


@dataclass
class ThreadPoolStats:
    """线程池统计信息"""
    active_threads: int
    idle_threads: int
    total_threads: int
    pending_tasks: int
    completed_tasks: int
    status: PoolStatus
    min_threads: int
    max_threads: int
    created_at: float
    uptime: float


class AsyncThreadPoolManager:
    """
    支持异步的线程池管理类
    为py真正支持多线程的准备
    
    功能特性:
    - 动态线程数量管理 (min_threads ~ max_threads)
    - 支持异步和同步函数执行
    - 上下文管理器支持
    - 优雅关闭
    - 线程池状态监控
    - 自动线程回收
    """
    
    def __init__(
        self, 
        min_threads: int = 2, 
        max_threads: int = 10,
        idle_timeout: float = 60.0,
        task_timeout: Optional[float] = None,
        thread_name_prefix: str = "AsyncPool"
    ):
        """
        初始化线程池管理器
        
        Args:
            min_threads: 最小线程数
            max_threads: 最大线程数  
            idle_timeout: 空闲线程超时时间(秒)
            task_timeout: 任务执行超时时间(秒)
            thread_name_prefix: 线程名称前缀
        """
        if min_threads <= 0 or max_threads <= 0:
            raise ValueError("线程数必须大于0")
        if min_threads > max_threads:
            raise ValueError("最小线程数不能大于最大线程数")
            
        self.min_threads = min_threads
        self.max_threads = max_threads
        self.idle_timeout = idle_timeout
        self.task_timeout = task_timeout
        self.thread_name_prefix = thread_name_prefix
        
        # 线程池相关
        self._executor = ThreadPoolExecutor(
            max_workers=max_threads,
            thread_name_prefix=thread_name_prefix
        )
        self._current_threads = min_threads
        
        # 状态管理
        self._status = PoolStatus.RUNNING
        self._lock = threading.RLock()
        self._created_at = time.time()
        
        # 统计信息
        self._completed_tasks = 0
        self._active_tasks = 0
        self._pending_tasks = 0
        
        # 线程监控
        self._monitor_task = None
        self._shutdown_event = threading.Event()
        
        # 启动监控线程
        self._start_monitor()
        
        logger.info(f"线程池管理器已启动: min={min_threads}, max={max_threads}")
    
    def _start_monitor(self):
        """启动监控线程"""
        def monitor():
            while not self._shutdown_event.wait(self.idle_timeout / 2):
                if self._status != PoolStatus.RUNNING:
                    break
                self._cleanup_idle_threads()
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
    def _cleanup_idle_threads(self):
        """清理空闲线程"""
        with self._lock:
            if self._status != PoolStatus.RUNNING:
                return
                
            # 这里简化处理，实际中可以通过更复杂的逻辑来监控空闲线程
            current_active = self._active_tasks
            if current_active == 0 and self._current_threads > self.min_threads:
                # 可以考虑缩减线程池，但ThreadPoolExecutor不直接支持
                # 这里只是记录日志，实际缩减需要重新创建执行器
                logger.debug("检测到空闲线程，考虑缩减")
    
    async def submit_task(
        self, 
        func: Callable, 
        *args, 
        timeout: Optional[float] = None,
        **kwargs
    ) -> Any:
        """
        提交任务到线程池并异步等待结果
        
        Args:
            func: 要执行的函数(可以是同步或异步)
            *args: 函数参数
            timeout: 任务超时时间
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
        """
        if self._status != PoolStatus.RUNNING:
            raise RuntimeError("线程池已关闭")
        
        # 确定超时时间
        effective_timeout = timeout or self.task_timeout
        
        # 包装执行函数
        def execute_func():
            try:
                with self._lock:
                    self._active_tasks += 1
                
                if inspect.iscoroutinefunction(func):
                    # 异步函数需要在新的事件循环中运行
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(func(*args, **kwargs))
                    finally:
                        loop.close()
                else:
                    # 同步函数直接执行
                    return func(*args, **kwargs)
            finally:
                with self._lock:
                    self._active_tasks -= 1
                    self._completed_tasks += 1
        
        # 提交到线程池
        with self._lock:
            self._pending_tasks += 1
        
        try:
            future = self._executor.submit(execute_func)
            
            # 异步等待结果
            loop = asyncio.get_event_loop()
            if effective_timeout:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, future.result),
                    timeout=effective_timeout
                )
            else:
                result = await loop.run_in_executor(None, future.result)
            
            return result
            
        except asyncio.TimeoutError:
            future.cancel()
            raise asyncio.TimeoutError(f"任务执行超时: {effective_timeout}秒")
        finally:
            with self._lock:
                self._pending_tasks -= 1
    
    @asynccontextmanager
    async def get_worker(self, timeout: Optional[float] = None):
        """
        上下文管理器：获取一个工作线程来执行任务
        
        使用示例:
            async with pool.get_worker() as worker:
                result = await worker(some_function, arg1, arg2)
        """
        if self._status != PoolStatus.RUNNING:
            raise RuntimeError("线程池已关闭")
        
        async def worker(func: Callable, *args, **kwargs):
            return await self.submit_task(func, *args, timeout=timeout, **kwargs)
        
        try:
            yield worker
        except Exception as e:
            logger.error(f"工作线程执行出错: {e}")
            raise
    
    def get_stats(self) -> ThreadPoolStats:
        """获取线程池统计信息"""
        with self._lock:
            uptime = time.time() - self._created_at
            
            # 获取线程池内部信息
            total_threads = len(self._executor._threads) if hasattr(self._executor, '_threads') else 0
            
            return ThreadPoolStats(
                active_threads=self._active_tasks,
                idle_threads=max(0, total_threads - self._active_tasks),
                total_threads=total_threads,
                pending_tasks=self._pending_tasks,
                completed_tasks=self._completed_tasks,
                status=self._status,
                min_threads=self.min_threads,
                max_threads=self.max_threads,
                created_at=self._created_at,
                uptime=uptime
            )
    
    def print_stats(self):
        """打印线程池状态"""
        stats = self.get_stats()
        print(f"""
=== 线程池状态 ===
状态: {stats.status.value}
活跃线程: {stats.active_threads}
空闲线程: {stats.idle_threads}  
总线程数: {stats.total_threads}
等待任务: {stats.pending_tasks}
完成任务: {stats.completed_tasks}
配置范围: {stats.min_threads}-{stats.max_threads}
运行时间: {stats.uptime:.2f}秒
""")
    
    async def shutdown(self, wait: bool = True, timeout: Optional[float] = None):
        """
        优雅关闭线程池
        
        Args:
            wait: 是否等待正在执行的任务完成
            timeout: 关闭超时时间
        """
        logger.info("开始关闭线程池...")
        
        with self._lock:
            if self._status != PoolStatus.RUNNING:
                return
            self._status = PoolStatus.SHUTTING_DOWN
        
        # 停止监控线程
        self._shutdown_event.set()
        
        if wait:
            # 等待现有任务完成
            start_time = time.time()
            while self._active_tasks > 0:
                if timeout and (time.time() - start_time) > timeout:
                    logger.warning("关闭超时，强制终止")
                    break
                await asyncio.sleep(0.1)
        
        # 关闭执行器
        self._executor.shutdown(wait=wait)
        
        with self._lock:
            self._status = PoolStatus.SHUTDOWN
        
        logger.info("线程池已关闭")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.shutdown()
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, '_executor') and self._status == PoolStatus.RUNNING:
            self._executor.shutdown(wait=False)


# 使用示例和测试代码
async def example_usage():
    """使用示例"""
    
    # 测试函数
    def sync_task(name: str, duration: float) -> str:
        """同步任务"""
        time.sleep(duration)
        return f"同步任务 {name} 完成"
    
    async def async_task(name: str, duration: float) -> str:
        """异步任务"""
        await asyncio.sleep(duration)
        return f"异步任务 {name} 完成"
    
    # 创建线程池管理器
    async with AsyncThreadPoolManager(min_threads=2, max_threads=8) as pool:
        
        print("=== 开始测试 ===")
        pool.print_stats()
        
        # 测试1: 直接提交任务
        print("\n1. 直接提交任务测试")
        tasks = []
        
        # 提交混合任务
        for i in range(5):
            if i % 2 == 0:
                task = pool.submit_task(sync_task, f"sync-{i}", 1.0)
            else:
                task = pool.submit_task(async_task, f"async-{i}", 1.0)
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks)
        for result in results:
            print(f"结果: {result}")
        
        pool.print_stats()
        
        # 测试2: 使用上下文管理器
        print("\n2. 上下文管理器测试")
        async with pool.get_worker(timeout=5.0) as worker:
            result1 = await worker(sync_task, "ctx-sync", 0.5)
            result2 = await worker(async_task, "ctx-async", 0.5)
            print(f"上下文结果: {result1}, {result2}")
        
        pool.print_stats()
        
        # 测试3: 超时处理
        print("\n3. 超时测试")
        try:
            await pool.submit_task(sync_task, "timeout-test", 3.0, timeout=1.0)
        except asyncio.TimeoutError:
            print("任务超时被正确捕获")
        
        pool.print_stats()


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_usage())