"""工具预设 default/deferred 两组修改（modify_preset_tools group 参数）的单元测试

覆盖：deferred 增删、两组互斥（加入任一组自动移出另一组）、config.json 持久化往返、
非法分组/操作拒绝。
"""

import json

import pytest

from atribot.core.service_container import container
from atribot.LLMchat.MCP.tool_calls import ToolPresetManager, ToolRegistry


class _Log:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


async def _noop_handler(**kwargs):
    return "ok"


@pytest.fixture()
def preset_env(tmp_path):
    """临时 config.json + 注册了 a/b/c 三个工具的注册表，返回 (manager, config_path)"""
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "tool_presets": {
            "webui": {"default": ["a"], "deferred": ["b"]},
        }
    }), encoding="utf-8")

    class _FakeConfig:
        pass

    fake_cfg = _FakeConfig()
    fake_cfg.config_file_path = config_path
    original = container._services.get("config")
    container.register("config", fake_cfg)

    registry = ToolRegistry(_Log())
    for name in ("a", "b", "c"):
        registry.add_func(name, {}, f"tool {name}", _noop_handler)

    manager = ToolPresetManager(_Log())
    manager.load_presets_from_config(
        {"webui": {"default": ["a"], "deferred": ["b"]}}, registry
    )

    yield manager, config_path

    if original is None:
        container.unregister("config")
    else:
        container.register("config", original)


def _read_preset(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["tool_presets"]["webui"]


@pytest.mark.asyncio
async def test_deferred_add_moves_tool_out_of_default(preset_env):
    manager, path = preset_env

    await manager.modify_preset_tools("webui", "add", ["a"], group="deferred")

    # 互斥：a 从默认组移出，与 b 同在待发现组
    assert manager.presets["webui"].names() == []
    assert manager.deferred["webui"] == ["b", "a"]
    persisted = _read_preset(path)
    assert persisted == {"default": [], "deferred": ["b", "a"]}


@pytest.mark.asyncio
async def test_deferred_remove_keeps_default(preset_env):
    manager, path = preset_env

    await manager.modify_preset_tools("webui", "remove", ["b"], group="deferred")

    assert manager.presets["webui"].names() == ["a"]
    assert manager.deferred["webui"] == []
    assert _read_preset(path) == {"default": ["a"], "deferred": []}


@pytest.mark.asyncio
async def test_default_add_moves_tool_out_of_deferred(preset_env):
    manager, path = preset_env

    await manager.modify_preset_tools("webui", "add", ["b"], group="default")

    assert manager.presets["webui"].names() == ["a", "b"]
    assert manager.deferred["webui"] == []
    assert _read_preset(path) == {"default": ["a", "b"], "deferred": []}


@pytest.mark.asyncio
async def test_cross_group_roundtrip_via_full_sync(preset_env):
    """模拟路由层的全量同步：b 从待发现改为默认，a 从默认改为待发现"""
    manager, path = preset_env

    await manager.modify_preset_tools("webui", "remove", ["b"], group="deferred")
    await manager.modify_preset_tools("webui", "add", ["b"], group="default")
    await manager.modify_preset_tools("webui", "remove", ["a"], group="default")
    await manager.modify_preset_tools("webui", "add", ["a"], group="deferred")

    assert manager.presets["webui"].names() == ["b"]
    assert manager.deferred["webui"] == ["a"]
    assert _read_preset(path) == {"default": ["b"], "deferred": ["a"]}


@pytest.mark.asyncio
async def test_deferred_allows_unregistered_tool_name(preset_env):
    """待发现名单允许包含未注册工具（与 load 行为一致，仅列名提示模型）"""
    manager, path = preset_env

    await manager.modify_preset_tools("webui", "add", ["ghost_tool"], group="deferred")

    assert "ghost_tool" in manager.deferred["webui"]
    assert "ghost_tool" in _read_preset(path)["deferred"]


@pytest.mark.asyncio
async def test_invalid_group_and_op_rejected(preset_env):
    manager, _ = preset_env

    with pytest.raises(ValueError):
        await manager.modify_preset_tools("webui", "add", ["a"], group="unknown")
    with pytest.raises(ValueError):
        await manager.modify_preset_tools("webui", "frobnicate", ["a"], group="deferred")
    with pytest.raises(ValueError):
        await manager.modify_preset_tools("no_such_preset", "add", ["a"])


def test_load_presets_dict_and_list_forms(tmp_path):
    """dict 形态带 deferred、list 形态无 deferred 的加载兼容"""
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"tool_presets": {"list_preset": ["a"]}}), encoding="utf-8")

    registry = ToolRegistry(_Log())
    for name in ("a", "b"):
        registry.add_func(name, {}, f"tool {name}", _noop_handler)

    manager = ToolPresetManager(_Log())
    manager.load_presets_from_config(
        {
            "dict_preset": {"default": ["a"], "deferred": ["b"]},
            "list_preset": ["b"],
        },
        registry,
    )

    assert manager.presets["dict_preset"].names() == ["a"]
    assert manager.deferred["dict_preset"] == ["b"]
    assert manager.presets["list_preset"].names() == ["b"]
    assert "list_preset" not in manager.deferred
