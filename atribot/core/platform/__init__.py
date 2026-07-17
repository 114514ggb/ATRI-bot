from atribot.core.platform.base import PlatformAdapter
from atribot.core.platform.event_bus import EventBus
from atribot.core.platform.message_queue import MessageQueue

_ADAPTER_REGISTRY: dict[str, type[PlatformAdapter]] = {}
"""适配器类型注册表: {适配器名称: 适配器类}"""


def register_adapter(name: str):
    """装饰器：将适配器类注册到全局注册表

    用法:
        @register_adapter("onebot")
        class OneBotAdapter(PlatformAdapter):
            ...

    Args:
        name: 适配器类型名称，配置文件中 adapter 字段与此匹配
    """
    if not name or not isinstance(name, str):
        raise ValueError(f"适配器名称必须是非空字符串，收到: {name!r}")

    def decorator(cls: type[PlatformAdapter]) -> type[PlatformAdapter]:
        if name in _ADAPTER_REGISTRY:
            import logging
            logging.getLogger("Platform").warning(
                f"适配器类型 '{name}' 被重复注册: "
                f"旧={_ADAPTER_REGISTRY[name].__name__}, 新={cls.__name__}"
            )
        _ADAPTER_REGISTRY[name] = cls
        return cls

    return decorator


def get_adapter_class(name: str) -> type[PlatformAdapter] | None:
    """按名称查找已注册的适配器类

    Args:
        name: 适配器类型名称

    Returns:
        适配器类，未找到返回 None
    """
    return _ADAPTER_REGISTRY.get(name)


def get_registered_adapters() -> dict[str, type[PlatformAdapter]]:
    """获取所有已注册的适配器类型"""
    return dict(_ADAPTER_REGISTRY)


__all__ = [
    "PlatformAdapter",
    "MessageQueue",
    "EventBus",
    "register_adapter",
    "get_adapter_class",
    "get_registered_adapters",
]
