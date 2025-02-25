import signal
import asyncio
import logging
import sys
from typing import Callable, Awaitable, Optional

class graceful_exiter:
    """退出保存类"""
    def __init__(self, exit_code: int = 0 ,timeout: int = 10):
        self.async_handlers: list[Callable[[], Awaitable[None]]] = []
        self.sync_handlers: list[Callable[[], None]] = []
        self._shutting_down = False # 防止重复调用
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
        try:
            for handler in self.sync_handlers:
                try:
                    handler()
                except Exception as e:
                    logging.exception(f"同步清理失败: {e}")
            
            
            loop: Optional[asyncio.AbstractEventLoop] = None
            
            if self.async_handlers:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._run_async_handlers(loop)
                
        finally:
            if loop and not loop.is_closed():
                    loop.close()
            sys.exit(self.exit_code)

    def _run_async_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        """执行异步处理器"""
        async def _gather_tasks():
            return await asyncio.gather(
                *[handler() for handler in self.async_handlers],
                return_exceptions=True
            )

        try:
            loop.run_until_complete(
                asyncio.wait_for(_gather_tasks(), timeout=self.timeout)
            )
        except asyncio.TimeoutError:
            logging.error(f"异步清理超时 (最长等待 {self.timeout}s)")
        
    def register_async(self, func: Callable[[], Awaitable[None]]) -> None:
        """注册异步清理函数"""
        self.async_handlers.append(func)

    def register_sync(self, func: Callable[[], None]) -> None:
        """注册同步清理函数"""
        self.sync_handlers.append(func)