from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atribot.plugins.types import PluginMetadata

plugin_map: dict[str, PluginMetadata] = {}
"""模块路径 → PluginMetadata 的映射，是注册表的主索引

key = module_path,如 "atribot.plugins.my_plugin.plugin"
"""

plugin_list: list[PluginMetadata] = []
"""按注册顺序排列的列表，保持顺序稳定"""


def register(metadata: PluginMetadata) -> None:
    """将元数据写入注册表

    若 module_path 已存在则更新（热重载场景）
    """
    existing = plugin_map.get(metadata.module_path)
    if existing is None:
        plugin_map[metadata.module_path] = metadata
        plugin_list.append(metadata)
    else:
        # 更新已有条目（热重载时替换类引用等信息）
        existing.plugin_cls = metadata.plugin_cls
        existing.name = metadata.name
        existing.version = metadata.version
        existing.description = metadata.description
        existing.author = metadata.author


def unregister(module_path: str) -> PluginMetadata | None:
    """从注册表中移除指定模块路径的条目

    Returns:
        被移除的元数据，未找到返回 None
    """
    metadata = plugin_map.pop(module_path, None)
    if metadata is not None:
        try:
            plugin_list.remove(metadata)
        except ValueError:
            pass
    return metadata


def get(module_path: str) -> PluginMetadata | None:
    """按模块路径查询插件元数据"""
    return plugin_map.get(module_path)


def get_all() -> list[PluginMetadata]:
    """返回所有已注册插件元数据的副本"""
    return list(plugin_list)


def clear() -> None:
    """清空注册表"""
    plugin_map.clear()
    plugin_list.clear()
