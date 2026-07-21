from logging import Logger
from typing import TYPE_CHECKING

from atribot.core.platform.manager import PlatformManager
from atribot.core.service_container import ServiceBase, container

from .loader import PluginLoader
from .registry import clear as _clear_registry
from .types import PluginMetadata

if TYPE_CHECKING:
    from atribot.core.atri_config import atriConfig
    from atribot.plugins.plugin import Plugin


class PluginManager(ServiceBase):
    """插件管理器服务

    职责仅限于启动、停止、重启插件，不干涉插件的具体行为
    """

    def __init__(self, config: atriConfig, log: Logger) -> None:
        self._config: atriConfig = config
        self._log: Logger = log.getChild("PluginManager")
        self._loader: PluginLoader | None = None

    async def initialize(self) -> None:
        """发现并加载所有插件"""
        try:
            pm = container.get_by_type(PlatformManager)
            event_bus = pm.event_bus
        except (ValueError, Exception) as exc:
            self._log.warning(
                "未找到 PlatformManager 实例 (%s)，无法启动插件管理器",
                exc,
            )
            return

        plugins_dir = self._config.file_path.plugins
        self._loader = PluginLoader(
            plugins_dir=plugins_dir,
            event_bus=event_bus,
            pipeline=pm.pipeline,
        )

        self._loader.discover()
        await self._loader.load_all()
        self._log.info(
            "插件管理器就绪: %d 个插件已加载", self._loader.plugin_count
        )

    async def cleanup(self) -> None:
        """清理：卸载所有插件并清空注册表"""
        if self._loader is not None:
            await self._loader.unload_all()
        _clear_registry()
        self._log.info("插件管理器已关闭")

    async def load_plugin(self, module_path: str) -> Plugin:
        """加载插件

        Args:
            module_path: 模块路径，如 "atribot.plugins.my_plugin.plugin"

        Returns:
            插件实例
        """
        if self._loader is None:
            raise RuntimeError("PluginManager 尚未初始化")
        return await self._loader.load_plugin(module_path)

    async def unload_plugin(self, module_path: str) -> None:
        """卸载插件

        Args:
            module_path: 模块路径
        """
        if self._loader is None:
            raise RuntimeError("PluginManager 尚未初始化")
        await self._loader.unload_plugin(module_path)

    async def reload_plugin(self, module_path: str) -> Plugin:
        """热重载插件

        Args:
            module_path: 模块路径

        Returns:
            重载后的插件实例
        """
        if self._loader is None:
            raise RuntimeError("PluginManager 尚未初始化")
        return await self._loader.reload_plugin(module_path)

    def get_plugin(self, module_path: str) -> Plugin | None:
        """获取已加载的插件实例

        Args:
            module_path: 模块路径

        Returns:
            插件实例，未加载返回 None
        """
        if self._loader is None:
            return None
        return self._loader.loaded_plugins.get(module_path)

    def list_plugins(self) -> list[PluginMetadata]:
        """列出所有已发现的插件元数据"""
        from .registry import get_all

        return get_all()

    @property
    def loaded_plugins(self) -> dict[str, Plugin]:
        """已加载的插件映射 {module_path: Plugin}"""
        if self._loader is None:
            return {}
        return self._loader.loaded_plugins
