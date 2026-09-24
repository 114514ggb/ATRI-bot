"""工具预设相关：atriConfig.reload_section 内存同步、modify_preset_tools 备份、后端配置校验"""

import json
import logging

import pytest

from atribot.core.atri_config import atriConfig
from atribot.core.service_container import container
from atribot.LLMchat.MCP.tool_calls import ToolPresetManager, ToolRegistry
from atribot.web_panel.routes.config import _validate_tool_presets

LOG = logging.getLogger("test-tool-presets")


async def _noop(**kwargs):
    return None


def _write_config(path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    """atriConfig 会优先读 ATRI_CONFIG_PATH 环境变量，测试里必须清掉"""
    monkeypatch.delenv("ATRI_CONFIG_PATH", raising=False)
    yield
    container.unregister("config")


def _make_config(tmp_path, data) -> atriConfig:
    path = tmp_path / "config.json"
    _write_config(path, data)
    return atriConfig(str(path))


class TestReloadSection:
    """reload_section：_raw_config 与 _config(ConfigObject) 必须同时更新"""

    def test_syncs_both_copies_from_file(self, tmp_path):
        cfg = _make_config(tmp_path, {"tool_presets": {"a": ["x"]}})
        assert cfg.tool_presets["a"] == ["x"]

        # 模拟 web_panel 写盘后回读：文件内容已变，内存还是旧的
        new_presets = {"a": ["y"], "webui": {"default": ["tool_search"], "deferred": ["run_command"]}}
        _write_config(cfg.config_file_path, {"tool_presets": new_presets})

        value = cfg.reload_section("tool_presets")

        assert value == new_presets
        assert cfg._raw_config["tool_presets"] == new_presets  # 路由层直读的那份
        assert cfg.tool_presets["a"] == ["y"]  # __getattr__ 走的那份
        assert cfg.tool_presets.webui.deferred == ["run_command"]  # 嵌套仍是 ConfigObject

    def test_missing_section_is_none(self, tmp_path):
        cfg = _make_config(tmp_path, {})
        assert cfg.reload_section("tool_presets") is None
        assert cfg.tool_presets is None


class TestModifyPresetToolsBackup:
    """modify_preset_tools 写盘前必须生成 .bak（与 POST /api/config 行为一致）"""

    async def test_backup_and_write(self, tmp_path):
        original = {"tool_presets": {"webui": {"default": ["tool_search"], "deferred": ["run_command"]}}}
        cfg = _make_config(tmp_path, original)
        container.register("config", cfg)

        registry = ToolRegistry(LOG)
        for name in ("tool_search", "run_command", "web_search"):
            registry.add_func(name, {}, f"{name} desc", _noop)

        manager = ToolPresetManager(LOG)
        manager.load_presets_from_config(cfg.tool_presets, registry)
        assert manager.deferred["webui"] == ["run_command"]

        backup = cfg.config_file_path.with_suffix(".json.bak")
        assert not backup.exists()

        await manager.modify_preset_tools("webui", "add", ["web_search"])
        assert backup.exists(), "写盘前应生成 .bak"
        assert json.loads(backup.read_text(encoding="utf-8")) == original

        written = json.loads(cfg.config_file_path.read_text(encoding="utf-8"))
        assert set(written["tool_presets"]["webui"]["default"]) == {"tool_search", "web_search"}
        assert written["tool_presets"]["webui"]["deferred"] == ["run_command"]

    async def test_deferred_move_is_mutually_exclusive(self, tmp_path):
        original = {"tool_presets": {"webui": {"default": ["tool_search", "web_search"], "deferred": []}}}
        cfg = _make_config(tmp_path, original)
        container.register("config", cfg)

        registry = ToolRegistry(LOG)
        for name in ("tool_search", "web_search"):
            registry.add_func(name, {}, f"{name} desc", _noop)

        manager = ToolPresetManager(LOG)
        manager.load_presets_from_config(cfg.tool_presets, registry)

        # 已有 deferred 键时写回 dict 形态；把 web_search 移入待发现组应从默认组移除
        manager.deferred["webui"] = []
        await manager.modify_preset_tools("webui", "add", ["web_search"], group="deferred")

        written = json.loads(cfg.config_file_path.read_text(encoding="utf-8"))
        assert written["tool_presets"]["webui"]["deferred"] == ["web_search"]
        assert "web_search" not in written["tool_presets"]["webui"]["default"]

    async def test_unknown_preset_rejected(self, tmp_path):
        cfg = _make_config(tmp_path, {"tool_presets": {"webui": ["tool_search"]}})
        container.register("config", cfg)

        registry = ToolRegistry(LOG)
        registry.add_func("tool_search", {}, "search", _noop)
        manager = ToolPresetManager(LOG)
        manager.load_presets_from_config(cfg.tool_presets, registry)

        with pytest.raises(ValueError):
            await manager.modify_preset_tools("nope", "add", ["tool_search"])
        assert not cfg.config_file_path.with_suffix(".json.bak").exists()


class TestValidateToolPresets:
    """后端配置校验：tool_search 与 deferred 成对（与前端 validatePresetPairing 同规则）"""

    def test_valid_dual_list(self):
        assert _validate_tool_presets({"tool_presets": {"webui": {"default": ["tool_search"], "deferred": ["a"]}}}) == []

    def test_valid_plain_list(self):
        assert _validate_tool_presets({"tool_presets": {"webui": ["web_search"]}}) == []

    def test_valid_null(self):
        assert _validate_tool_presets({"tool_presets": {"webui": None}}) == []

    def test_missing_key_ok(self):
        assert _validate_tool_presets({}) == []

    def test_deferred_without_tool_search(self):
        errors = _validate_tool_presets({"tool_presets": {"webui": {"default": ["a"], "deferred": ["b"]}}})
        assert len(errors) == 1 and "tool_search" in errors[0]

    def test_tool_search_without_deferred(self):
        errors = _validate_tool_presets({"tool_presets": {"webui": {"default": ["tool_search"], "deferred": []}}})
        assert len(errors) == 1 and "deferred 为空" in errors[0]

    def test_plain_list_with_tool_search_rejected(self):
        errors = _validate_tool_presets({"tool_presets": {"webui": ["tool_search"]}})
        assert len(errors) == 1 and "deferred 为空" in errors[0]

    def test_bad_shapes(self):
        assert _validate_tool_presets({"tool_presets": []}) == ["tool_presets 必须是对象"]
        assert _validate_tool_presets({"tool_presets": {"a": 1}})
        errors = _validate_tool_presets({"tool_presets": {"a": {"default": "x"}}})
        assert any("字符串数组" in e for e in errors)
        errors = _validate_tool_presets({"tool_presets": {"a": {"default": [1]}}})
        assert any("字符串数组" in e for e in errors)
        errors = _validate_tool_presets({"tool_presets": {"a": {"default": [], "unknown": []}}})
        assert any("未知分组" in e for e in errors)
