import contextvars
import inspect
import threading
import warnings
from inspect import isawaitable
from logging import Logger as Log
from typing import Any, Awaitable, Callable, Optional, TypeVar, get_type_hints

from atribot.core.logger import Logger

T = TypeVar("T")


class ServiceBase:
    """服务基类，不强制继承"""

    @classmethod
    def factory(cls, **kwargs: Any) -> Any:
        """默认工厂，子类可重写以转换容器依赖到 __init__ 参数"""
        return cls(**kwargs)

    async def initialize(self) -> None:
        """初始化"""
        pass

    async def cleanup(self) -> None:
        """回收"""
        pass



class DIContainer:
    """全局容器（线程安全单例）"""

    _instance: Optional["DIContainer"] = None
    _lock: threading.Lock = threading.Lock()

    _type_map: dict[type, str]
    """将服务类型映射到其对应的服务名称"""
    _services: dict[str, Any]
    """存储所有已注册的服务实例典"""
    _cleanup_handlers: dict[str, Callable[[], Any | Awaitable[Any]]]
    """存储服务名称对应的清理回调函数（支持同步或异步方法）"""
    _resolving_local: contextvars.ContextVar[frozenset[type]]
    """用于在同一协程上下文中追踪正在解析的依赖类型"""
    _factories: dict[type, Callable[..., Any]]
    """存储各类型的制造工厂函数或构造器"""


    def __new__(cls) -> "DIContainer":
        """创建单例实例。

        Returns:
            DIContainer: DI容器的单例实例。
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._services = {}
                    inst._cleanup_handlers = {}
                    inst._resolving_local = contextvars.ContextVar("resolving_stack", default=frozenset())
                    inst._factories = {}
                    inst._type_map = {}

                    logger_wrapper = Logger()
                    logger_instance = logger_wrapper.get_logger()
                    inst._services["log"] = logger_instance
                    inst._type_map[type(logger_instance)] = "log"
                    inst._services["Logger"] = logger_wrapper
                    inst._type_map[Logger] = "Logger"

                    cls._instance = inst
        return cls._instance


    @staticmethod
    def _make_key(cls: type) -> str:
        """获取默认的键名字"""
        # return f"{cls.__module__}.{cls.__qualname__}"
        return cls.__name__

    def register(
        self,
        name: str,
        service: Any,
        cleanup: Optional[Callable[[], Any | Awaitable[Any]]] = None,
    ) -> None:
        """注册服务,同名重复注册会发出警告但允许覆盖

        Args:
            name (str): 服务的名称标识
            service (Any): 服务实例本身
            cleanup (Optional[Callable[[], Any | Awaitable[Any]]], optional): 清理服务的可选回调函数。默认为 None
        """
        if name in self._services:
            warnings.warn(
                f"服务 '{name}' 已存在，将被覆盖。若有意为之请先调用 unregister()",
                stacklevel=2,
            )

        self._services[name] = service

        svc_type = type(service)
        if svc_type in self._type_map and self._type_map[svc_type] != name:
            warnings.warn(
                f"类型 {svc_type} 已映射到服务 '{self._type_map[svc_type]}',"
                f"将被新服务 '{name}' 覆盖,get_by_type() 将返回新服务",
                stacklevel=2,
            )
        self._type_map[svc_type] = name

        if cleanup is not None:
            self.register_cleanup(name, cleanup)

    def register_cleanup(
        self,
        name: str,
        handler: Callable[[], Any | Awaitable[Any]],
    ) -> None:
        """注册回收函数。同名重复注册抛异常

        Args:
            name (str): 要注册的回调函数对应的服务名称
            handler (Callable[[], Any | Awaitable[Any]]): 会被调用的无参回调函数，可以是同步或异步的

        Raises:
            ValueError: 如果该名称的清理函数已存在
        """
        if name in self._cleanup_handlers:
            raise ValueError(f"清理函数已注册: {name}")
        self._cleanup_handlers[name] = handler

    def unregister(self, name: str) -> None:
        """注销服务及其回收函数

        Args:
            name (str): 要注销的服务名称
        """
        self._services.pop(name, None)
        self._cleanup_handlers.pop(name, None)
        self._type_map = {k: v for k, v in self._type_map.items() if v != name}

    def register_factory(
        self, cls: type[T], 
        factory: Callable[..., Any], 
        name: Optional[str] = None
    ) -> None:
        """注册某个类型的工厂函数

        Args:
            cls (type[T]): 需要工厂注册的类型
            factory (Callable[..., Any]): 返回该类型实例的工厂函数
            name (Optional[str], optional): 自定义服务名称，默认使用类型全限定名
        """
        self._factories[cls] = factory
        if name is not None:
            self._type_map[cls] = name

    def register_class(
        self, 
        cls: type[T], 
        name: Optional[str] = None
    ) -> None:
        """注册一个可通过类型解析依赖并实例化的类

        Args:
            cls (type[T]): 需要注册的类类型
            name (Optional[str], optional): 自定义服务名称，默认使用类型全限定名
        """
        self._factories[cls] = cls
        if name is not None:
            self._type_map[cls] = name

    def get(self, name: str) -> Any:
        """按名称获取服务

        Args:
            name (str): 服务的名称

        Raises:
            ValueError: 若服务未找到，则抛出该异常

        Returns:
            Any: 返回服务实例
        """
        if name not in self._services:
            raise ValueError(f"Service '{name}' not found")
        return self._services[name]

    def exists(self, name: str) -> bool:
        """检查服务是否存在

        Args:
            name (str): 服务的名称

        Returns:
            bool: 若服务存在返回 True,否则返回 False
        """
        return name in self._services

    def get_by_type(self, cls: type[T]) -> T:
        """按类型获取服务（精确匹配优先，其次查找 isinstance)

        Args:
            cls (type[T]): 要查找的服务类型

        Raises:
            ValueError: 若没找到匹配类型的服务，则抛出异常

        Returns:
            T: 该类型的服务实例
        """
        if cls in self._type_map and self._type_map[cls] in self._services:
            return self._services[self._type_map[cls]]

        # 兼容基类 / 协议查询
        for srv in self._services.values():
            if isinstance(srv, cls):
                return srv

        raise ValueError(f"Service of type {cls} not found")

    async def resolve(self, cls: type[T]) -> T:
        """
        按类型解析服务实例（自动注入依赖并执行初始化）
        同一协程内检测循环依赖；并发调用各自维护独立的解析栈

        Args:
            cls (type[T]): 需要解析的类型

        Raises:
            RecursionError: 当检测到循环依赖时抛出。
            ValueError: 当既找不到对应的工厂,cls也不是一个有效类时抛出

        Returns:
            T: 解析后的服务实例
        """
        try:
            return self.get_by_type(cls)
        except ValueError:
            pass

        current_resolving = self._resolving_local.get()
        if cls in current_resolving:
            raise RecursionError(f"检测到循环依赖: {cls}")

        token = self._resolving_local.set(current_resolving | {cls})
        try:
            factory = self._factories.get(cls)
            if factory is None:
                if not inspect.isclass(cls):
                    raise ValueError(f"未找到 {cls} 的工厂函数，且它不是一个类")
                factory = cls

            if inspect.isclass(factory) and issubclass(factory, ServiceBase):
                overridden_factory = self._extract_overridden_method(
                    factory, "factory", ServiceBase.factory
                )
                if overridden_factory is not None:
                    factory = overridden_factory

            kwargs = await self._resolve_kwargs(factory, cls)
            instance = factory(**kwargs)
            if isawaitable(instance):
                instance = await instance

            cleanup: Optional[Callable] = None
            if isinstance(instance, ServiceBase):
                init_func = self._extract_overridden_method(
                    instance, "initialize", ServiceBase.initialize
                )
                if init_func is not None:
                    init_kwargs = await self._resolve_kwargs(init_func, type(instance))
                    result = init_func(**init_kwargs)
                    if isawaitable(result):
                        await result

                cleanup = self._extract_overridden_method(
                    instance, "cleanup", ServiceBase.cleanup
                )

            name = self._type_map.get(cls, self._make_key(cls))
            self.register(name, instance, cleanup=cleanup)

            return instance
        finally:
            self._resolving_local.reset(token)

    async def _resolve_kwargs(
        self, factory: Callable[..., Any], owner_cls: type
    ) -> dict[str, Any]:
        """解析工厂函数所需的所有参数

        Args:
            factory (Callable[..., Any]): 需要解析依赖参数的工厂方法或构造函数
            owner_cls (type): 拥有该工厂函数的类

        Raises:
            TypeError: 类型注解解析失败
            ValueError: 缺少必要参数的类型注解

        Returns:
            dict[str, Any]: 包含已解析参数的字典
        """
        func = factory.__init__ if inspect.isclass(factory) else factory

        sig = inspect.signature(func)
        try:
            hints = get_type_hints(func)
        except NameError as e:
            raise TypeError(
                f"解析 {owner_cls} 的类型注解失败(可能存在未导入的 forward reference): {e}"
            ) from e

        kwargs: dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            if param_name in ("self", "cls"):
                continue

            has_default = param.default is not inspect.Parameter.empty
            param_type = hints.get(param_name)

            if param_type is None or param_type is inspect.Parameter.empty:
                if has_default:
                    continue
                raise ValueError(
                    f"无法解析 {owner_cls.__name__}.{param_name}：缺少类型注解且无默认值"
                )

            try:
                kwargs[param_name] = await self.resolve(param_type)
            except (ValueError, RecursionError):
                if has_default:
                    continue  # 容器无法提供，保留默认值
                raise ValueError(
                    f"无法解析 {owner_cls.__name__}.{param_name}:"
                    f"类型 {param_type} 未注册且无默认值"
                ) from None

        return kwargs

    @staticmethod
    def _extract_overridden_method(
        target: Any,
        method_name: str,
        base_method: Optional[Any] = None,
    ) -> Optional[Callable]:
        """
        提取已被重写的方法。若与基类实现相同（未覆写），返回 None
        target 可以是类或实例
        """
        method = getattr(target, method_name, None)
        if method is None or not (callable(method) or inspect.isroutine(method)):
            return None
        if base_method is not None:
            method_func = getattr(method, "__func__", method)
            base_func = getattr(base_method, "__func__", base_method)
            if method_func is base_func:
                return None
        return method

    @staticmethod
    def _extract_method(
        instance: Any,
        method_name: str,
        base_method: Optional[Any] = None,
    ) -> Optional[Callable]:
        """
        提取实例方法。若该方法与基类方法是同一个函数对象（未被覆写），返回 None

        Args:
            instance (Any): 要检查的实例对象
            method_name (str): 要提取的方法名
            base_method (Optional[Any]): 用于比较基类原始方法的对象如果未继承则传None

        Returns:
            Optional[Callable]: 若该方法已被重载，则返回被调用的方法对象本身；否则返回 None
        """
        method = getattr(instance, method_name, None)
        if method is None or not inspect.isroutine(method):
            return None
        # 通过比较底层函数对象判断是否为基类的空实现
        if base_method is not None and getattr(method, "__func__", method) is base_method:
            return None
        return method

    async def shutdown(self) -> None:
        """按注册逆序执行所有回收函数"""
        log:Log = self.get("log")

        for name, handler in reversed(list(self._cleanup_handlers.items())):
            try:
                result = handler()
                if isawaitable(result):
                    await result
                log.debug(f"资源已关闭: {name}")
            except Exception as e:
                log.exception(f"关闭资源失败 [{name}]: {e}")


container = DIContainer()