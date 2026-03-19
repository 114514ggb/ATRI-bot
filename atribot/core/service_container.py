from inspect import isawaitable
from typing import Any, Awaitable, Callable, Dict

from atribot.core.logger import Logger


class DIContainer:
    """全局容器"""
    
    _instance = None
    _services: Dict[str, Any] = None
    _cleanup_handlers: dict[str, Callable[[], Any | Awaitable[Any]]]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._services = {}
            cls._instance._cleanup_handlers = {}
            cls._instance._services["log"] = Logger().get_logger()
        return cls._instance

    def register(
        self,
        name: str,
        service: Any,
        cleanup: Callable[[], Any | Awaitable[Any]] | None = None,
    ) -> None:
        """注册服务"""
        self._services[name] = service
        if cleanup is not None:
            self.register_cleanup(name, cleanup)

    def register_cleanup(
        self,
        name: str,
        handler: Callable[[], Any | Awaitable[Any]],
    ) -> None:
        """注册回收函数"""
        if name in self._cleanup_handlers:
            raise ValueError(f"清理函数已注册: {name}")
        self._cleanup_handlers[name] = handler

    def get(self, name: str) -> Any:
        """获取服务"""
        if name not in self._services:
            raise ValueError(f"Service {name} not found")
        return self._services[name]

    def exists(self, name: str) -> bool:
        """检查服务是否存在"""
        return name in self._services

    async def shutdown(self) -> None:
        """按注册逆序执行所有回收函数"""
        log:Logger = self._services["log"]
        for name, handler in reversed(list(self._cleanup_handlers.items())):
            try:
                result = handler()
                if isawaitable(result):
                    await result
                log.debug(f"资源已关闭: {name}")
            except Exception as e:
                log.exception(f"关闭资源失败 [{name}]: {e}")


container = DIContainer()
