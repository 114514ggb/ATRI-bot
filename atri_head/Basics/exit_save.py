import signal
import asyncio
import logging
import sys
import threading
from typing import Callable, Awaitable

class graceful_exiter:
    """退出保存类"""
    def __init__(self, exit_code: int = 0 ,timeout: int = 10):
        """
        Args:
            exit_code:退出代码
            timeout:等待超时时间
        """
        self.async_handlers: list[Callable[[], Awaitable[None]]] = []
        self.sync_handlers: list[Callable[[], None]] = []
        self._shutting_down = False
        self.exit_code = exit_code
        self.timeout = timeout
        
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
    def handle_signal(self, signum, frame) -> None:
        """信号处理入口"""
        if self._shutting_down:
            return
        self._shutting_down = True
        print(f"\n捕获到信号 {signum}, 开始清理资源...")
        
        # 先执行同步清理
        self._run_sync_handlers()
        
        # 然后处理异步清理
        if self.async_handlers:
            self._handle_async_cleanup()
                    
        print(f"清理完成, 退出程序 (退出码: {self.exit_code})")
        sys.exit(self.exit_code)
        

    def _run_sync_handlers(self) -> None:
        """执行同步处理器"""
        for handler in self.sync_handlers:
            try:
                handler()
            except Exception as e:
                logging.exception(f"同步清理失败: {e}")
                
    def _handle_async_cleanup(self) -> None:
        """处理异步清理"""
        try:
            # 尝试获取当前事件循环
            asyncio.get_running_loop()
            # 如果在事件循环中，使用线程来运行异步清理
            self._run_async_in_thread()
        except RuntimeError:
            # 没有运行的事件循环，创建新的
            try:
                asyncio.run(self._run_async_handlers())
            except Exception as e:
                logging.exception(f"异步清理失败: {e}")
        
    def _run_async_in_thread(self) -> None:
        """在新线程中运行异步清理"""
        def run_in_thread():
            try:
                asyncio.run(self._run_async_handlers())
            except Exception as e:
                logging.exception(f"线程中异步清理失败: {e}")
        
        thread = threading.Thread(target=run_in_thread)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.timeout)
        
        if thread.is_alive():
            logging.warning(f"异步清理超时 ({self.timeout}s)，强制退出")        


    async def _run_async_handlers(self) -> None:
        """执行异步处理器"""
        tasks = []
        for handler in self.async_handlers:
            task = asyncio.create_task(handler())
            tasks.append(task)
        
        if not tasks:
            return
            
        try:
            # 等待所有任务完成或超时
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            logging.warning(f"异步清理超时 ({self.timeout}s)")
            # 取消所有未完成的任务
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # 等待取消完成
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception:
                pass


    def register_async(self, func: Callable[[], Awaitable[None]]) -> None:
        """注册异步清理函数"""
        self.async_handlers.append(func)

    def register_sync(self, func: Callable[[], None]) -> None:
        """注册同步清理函数"""
        self.sync_handlers.append(func)