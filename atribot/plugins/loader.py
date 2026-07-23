import importlib
import pkgutil
import sys
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING

from atribot.core.service_container import container

from .registry import get, get_all, unregister
from .runtime import PluginRuntime
from .types import PluginMetadata

if TYPE_CHECKING:
    from atribot.core.event_bus.bus import EventBus
    from atribot.core.pipeline.pipeline import Pipeline
    from atribot.plugins.plugin import Plugin


class PluginLoader:
    """插件加载器"""

    _PLUGIN_PREFIX = "atribot.plugins."

    def __init__(
        self,
        plugins_dir: Path,
        event_bus: EventBus,
        pipeline: Pipeline,
    ) -> None:
        self._plugins_dir = plugins_dir
        self._event_bus = event_bus
        self._pipeline = pipeline
        self._log = container.get_by_type(Logger).getChild("PluginLoader")
        self._loaded_runtimes: dict[str, tuple[Plugin, PluginRuntime]] = {}
        """module_path → (plugin_instance, runtime) 的映射"""

    def discover(self) -> list[PluginMetadata]:
        """扫描 ``plugins_dir`` 下的子包，导入模块触发自动注册

        导入模块时 Python 解释器会执行模块代码，从而触发
        ``Plugin.__init_subclass__``，将插件信息写入 ``registry.plugin_map``

        Returns:
            本次发现的插件元数据列表
        """
        discovered: list[PluginMetadata] = []

        if not self._plugins_dir.is_dir():
            self._log.warning("插件目录不存在: %s", self._plugins_dir)
            return discovered

        for finder, name, is_pkg in pkgutil.iter_modules(
            [str(self._plugins_dir)]
        ):
            if not is_pkg:
                continue

            module_path = f"{self._PLUGIN_PREFIX}{name}"
            if get(module_path):
                self._log.debug("插件 '%s' 已注册，跳过发现", name)
                continue

            try:
                importlib.import_module(module_path)
                self._log.info("发现插件: %s (%s)", name, module_path)
            except Exception:
                self._log.exception("导入插件模块 '%s' 失败", module_path)
                continue

            meta = get(module_path)
            if meta is not None:
                discovered.append(meta)

        self._log.info(
            "插件发现完成: 共 %d 个已注册", len(get_all())
        )
        return discovered

    async def load_plugin(self, module_path: str) -> Plugin:
        """加载单个插件

        Args:
            module_path: 模块路径，如 "atribot.plugins.my_plugin.plugin"

        Returns:
            插件实例

        Raises:
            ValueError: 模块路径未注册
        """
        metadata = get(module_path)
        if metadata is None:
            raise ValueError(
                f"模块 '{module_path}' 未注册。"
                f"请确保该模块定义了 Plugin 子类且已被导入。"
            )

        if module_path in self._loaded_runtimes:
            instance, _ = self._loaded_runtimes[module_path]
            self._log.debug("插件 '%s' 已加载，跳过", metadata.name)
            return instance

        # 使用类定义时缓存的 PluginDefinition
        definition = metadata.plugin_cls._definition
        if definition is None:
            raise RuntimeError(
                f"插件类 '{metadata.plugin_cls.__name__}' 没有 PluginDefinition。"
                f"请确保该类定义了 Plugin 子类且 __init_subclass__ 已执行。"
            )

        instance = metadata.plugin_cls()

        # 创建运行时并注册 handlers/middlewares
        runtime = PluginRuntime(
            plugin=instance,
            definition=definition,
            event_bus=self._event_bus,
            pipeline=self._pipeline,
            log=self._log.getChild(f"Plugin.{metadata.name}"),
        )
        await runtime.setup()

        self._loaded_runtimes[module_path] = (instance, runtime)

        try:
            await instance.initialize()
        except Exception:
            self._log.exception("插件 '%s' initialize 失败", metadata.name)
            await runtime.unregister_all()
            del self._loaded_runtimes[module_path]
            raise

        self._log.info("插件已加载: %s v%s", metadata.name, metadata.version)
        return instance

    async def load_all(self, enabled_only: bool = True) -> list[Plugin]:
        """加载所有已注册的插件

        Args:
            enabled_only: 仅加载 ``enabled=True`` 的插件

        Returns:
            成功加载的插件实例列表
        """
        loaded: list[Plugin] = []
        for metadata in get_all():
            if enabled_only and not metadata.enabled:
                self._log.debug("插件 '%s' 已禁用，跳过", metadata.name)
                continue
            try:
                instance = await self.load_plugin(metadata.module_path)
                loaded.append(instance)
            except Exception:
                self._log.exception("加载插件 '%s' 失败", metadata.name)
        self._log.info("插件加载完成: %d/%d", len(loaded), len(get_all()))
        return loaded

    async def unload_plugin(self, module_path: str) -> None:
        """卸载单个插件,和清理插件残留
        
        Args:
            module_path: 模块路径
        """
        if module_path not in self._loaded_runtimes:
            self._log.debug("插件 '%s' 未加载，无需卸载", module_path)
            return

        instance, runtime = self._loaded_runtimes[module_path]

        try:
            await instance.cleanup()
        except Exception:
            self._log.exception("插件 '%s' cleanup 失败", instance.plugin_name)

        await runtime.unregister_all()
        del self._loaded_runtimes[module_path]

        self._log.info("插件已卸载: %s", instance.plugin_name)

    async def unload_all(self) -> None:
        """卸载所有已加载的插件"""
        for module_path in list(self._loaded_runtimes.keys()):
            await self.unload_plugin(module_path)

    async def reload_plugin(self, module_path: str) -> Plugin:
        """热重载插件

        Args:
            module_path: 模块路径

        Returns:
            重载后的插件实例
        """
        await self.unload_plugin(module_path)

        module_path.split(".")[0]
        keys_to_del = [
            key for key in sys.modules if key.startswith(module_path)
        ]

        parent_parts = module_path.split(".")
        for i in range(1, len(parent_parts)):
            parent = ".".join(parent_parts[:i])
            if parent in sys.modules:
                keys_to_del.append(parent)

        for key in sorted(set(keys_to_del), reverse=True):
            sys.modules.pop(key, None)

        unregister(module_path)

        try:
            importlib.import_module(module_path)
        except Exception:
            self._log.exception("重载时导入 '%s' 失败", module_path)
            raise

        instance = await self.load_plugin(module_path)
        self._log.info("插件已重载: %s", instance.plugin_name)
        return instance

    def is_loaded(self, module_path: str) -> bool:
        """检查插件是否已加载"""
        return module_path in self._loaded_runtimes

    @property
    def loaded_plugins(self) -> dict[str, Plugin]:
        """已加载的插件实例映射 {module_path: Plugin}"""
        return {path: inst for path, (inst, _) in self._loaded_runtimes.items()}

    @property
    def plugin_count(self) -> int:
        """已注册的插件总数"""
        return len(get_all())
