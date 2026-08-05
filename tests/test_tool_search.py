"""tool_search 工具与 ToolPresetManager 加载逻辑的单元测试"""

from logging import getLogger

import pytest

from atribot.core.type.context_types import ToolSearchRequested
from atribot.LLMchat.MCP.tool_calls import (
    ToolCalls,
    ToolPresetManager,
    score_tool,
)
from atribot.LLMchat.MCP.tool_model import LocalTool, ToolSet
from atribot.LLMchat.tools.tool_search import main as tool_search_main


class _FakeRegistry:
    """极简工具注册表替身，支持按名称查找与全量列表"""

    def __init__(self, tools):
        self.func_list = tools
        self._tools = {t.name: t for t in tools}

    def get_func(self, name):
        return self._tools.get(name)


def _make_tool(name: str, description: str = "描述"):
    async def handler():
        return "ok"

    return LocalTool(name=name, description=description, handler=handler)


def _make_manager() -> ToolPresetManager:
    return ToolPresetManager(getLogger("test_tool_search"))


# ---------- score_tool 评分函数 ----------


def test_score_exact_name():
    exact = score_tool("web_search", "搜索网页", "web_search")
    contains = score_tool("web_search", "搜索网页", "web")
    assert exact > 0
    assert exact > contains


def test_score_prefix_beats_unrelated():
    prefixed = score_tool("web_search", "描述", "web")
    unrelated = score_tool("send_file", "描述", "web")
    assert prefixed > 0
    assert unrelated == 0


def test_score_name_contains():
    assert score_tool("memory_search", "描述", "search") > 0
    assert score_tool("get_user_info", "描述", "memory") == 0


def test_score_description_contains():
    assert score_tool("foo_bar", "可以搜索群消息", "搜索") > 0
    assert score_tool("foo_bar", "可以搜索群消息", "无关词") == 0


def test_score_case_insensitive():
    assert score_tool("Web_Search", "描述", "WEB_SEARCH") == score_tool(
        "web_search", "描述", "web_search"
    )


def test_score_multiple_words_partial():
    full = score_tool("run_python_code", "描述", "run python")
    partial = score_tool("run_python_code", "描述", "run xyz")
    assert full > partial


def test_score_empty_query():
    assert score_tool("web_search", "描述", "") == 0
    assert score_tool("web_search", "描述", "   ") == 0


def test_score_exact_beats_prefix():
    exact = score_tool("run_python_code", "描述", "run_python_code")
    prefix = score_tool("run_python_code", "描述", "run")
    assert exact > prefix


# ---------- ToolPresetManager 加载逻辑 ----------


def test_load_preset_list_form():
    registry = _FakeRegistry(
        [_make_tool("web_search"), _make_tool("run_command"), _make_tool("tool_search")]
    )
    mgr = _make_manager()
    mgr.load_presets_from_config(
        {"group_chat": ["web_search", "run_command"]}, registry
    )

    assert mgr.presets["group_chat"].names() == ["web_search", "run_command"]
    assert mgr.deferred == {}


def test_load_preset_dict_form():
    registry = _FakeRegistry([_make_tool("web_search"), _make_tool("run_command")])
    mgr = _make_manager()
    mgr.load_presets_from_config(
        {"group_chat": {"default": ["web_search"], "deferred": ["run_command"]}},
        registry,
    )

    assert mgr.presets["group_chat"].names() == ["web_search"]
    assert mgr.deferred == {"group_chat": ["run_command"]}


def test_load_preset_skip_unregistered():
    registry = _FakeRegistry([_make_tool("web_search")])
    mgr = _make_manager()
    mgr.load_presets_from_config(
        {"group_chat": ["web_search", "missing_tool"]}, registry
    )

    assert mgr.presets["group_chat"].names() == ["web_search"]


def test_load_preset_reset_deferred_on_reload():
    registry = _FakeRegistry([_make_tool("web_search"), _make_tool("run_command")])
    mgr = _make_manager()
    mgr.load_presets_from_config(
        {"group_chat": {"default": ["web_search"], "deferred": ["run_command"]}},
        registry,
    )
    # 重载为 list 形式后，deferred 应被清空
    mgr.load_presets_from_config({"group_chat": ["web_search"]}, registry)

    assert mgr.deferred == {}
    assert mgr.presets["group_chat"].names() == ["web_search"]


# ---------- tool_search.main 抛约定错误 ----------


async def test_tool_search_main_raises_request():
    with pytest.raises(ToolSearchRequested) as exc_info:
        await tool_search_main("run", limit=3)
    assert exc_info.value.query == "run"
    assert exc_info.value.limit == 3


async def test_tool_search_main_default_limit():
    with pytest.raises(ToolSearchRequested) as exc_info:
        await tool_search_main("run")
    assert exc_info.value.limit == 5


async def test_tool_search_main_invalid_limit():
    with pytest.raises(ToolSearchRequested) as exc_info:
        await tool_search_main("run", limit=0)
    assert exc_info.value.limit == 1


# ---------- ToolCalls.enable_deferred_tools ----------


def _make_tool_calls_with(preset_manager: ToolPresetManager, registry) -> ToolCalls:
    """用 __new__ 绕过 __init__ 构造轻量 ToolCalls 以测试公开方法"""
    tc = ToolCalls.__new__(ToolCalls)
    tc._deferred_prompt_cache = {}
    tc._registry = registry
    tc._preset_manager = preset_manager
    return tc


def test_enable_deferred_tools_adds_matches():
    registry = _FakeRegistry(
        [
            _make_tool("run_python_code", "运行Python代码"),
            _make_tool("run_command", "运行Shell命令"),
        ]
    )
    mgr = _make_manager()
    mgr.load_presets_from_config(
        {
            "group_chat": {
                "default": ["web_search"],
                "deferred": ["run_python_code", "run_command"],
            }
        },
        registry,
    )
    tc = _make_tool_calls_with(mgr, registry)

    round_toolset = ToolSet()
    round_toolset.add_tool(_make_tool("web_search", "搜索网页"))

    matched = tc.enable_deferred_tools(
        query="run", limit=5, target_toolset=round_toolset, preset_name="group_chat"
    )

    assert {t.name for t in matched} == {"run_python_code", "run_command"}
    assert "run_python_code" in round_toolset.names()
    assert "run_command" in round_toolset.names()
    assert "web_search" in round_toolset.names()


def test_enable_deferred_tools_excludes_current():
    registry = _FakeRegistry([_make_tool("run_python_code", "运行Python代码")])
    mgr = _make_manager()
    mgr.load_presets_from_config(
        {
            "group_chat": {
                "default": ["web_search"],
                "deferred": ["run_python_code"],
            }
        },
        registry,
    )
    tc = _make_tool_calls_with(mgr, registry)

    round_toolset = ToolSet()
    round_toolset.add_tool(_make_tool("web_search", "搜索网页"))
    round_toolset.add_tool(_make_tool("run_python_code", "运行Python代码"))

    matched = tc.enable_deferred_tools(
        query="run", limit=5, target_toolset=round_toolset, preset_name="group_chat"
    )
    assert matched == []
    assert round_toolset.names() == ["web_search", "run_python_code"]


def test_enable_deferred_tools_no_match_keeps_target():
    registry = _FakeRegistry([_make_tool("run_python_code", "运行Python代码")])
    mgr = _make_manager()
    mgr.load_presets_from_config(
        {
            "group_chat": {
                "default": ["web_search"],
                "deferred": ["run_python_code"],
            }
        },
        registry,
    )
    tc = _make_tool_calls_with(mgr, registry)

    round_toolset = ToolSet()
    round_toolset.add_tool(_make_tool("web_search", "搜索网页"))

    matched = tc.enable_deferred_tools(
        query="zzzz", limit=5, target_toolset=round_toolset, preset_name="group_chat"
    )
    assert matched == []
    assert round_toolset.names() == ["web_search"]


def test_enable_deferred_tools_fallback_full_without_preset():
    registry = _FakeRegistry(
        [_make_tool("web_search", "搜索网页"), _make_tool("run_command", "运行命令")]
    )
    mgr = _make_manager()
    mgr.load_presets_from_config({"group_chat": ["web_search"]}, registry)
    tc = _make_tool_calls_with(mgr, registry)

    round_toolset = ToolSet()
    round_toolset.add_tool(_make_tool("web_search", "搜索网页"))

    matched = tc.enable_deferred_tools(
        query="run", limit=5, target_toolset=round_toolset, preset_name=""
    )
    assert [t.name for t in matched] == ["run_command"]
    assert "run_command" in round_toolset.names()


# ---------- ToolSet.name ----------


def test_toolset_copy_preserves_name():
    ts = ToolSet(name="group_chat")
    ts.add_tool(_make_tool("web_search", "搜索网页"))
    copied = ts.copy()
    assert copied.name == "group_chat"
    assert copied.names() == ["web_search"]
    copied.add_tool(_make_tool("run_command", "运行命令"))
    assert ts.names() == ["web_search"]


def test_register_preset_sets_name():
    registry = _FakeRegistry([_make_tool("web_search", "搜索网页")])
    mgr = _make_manager()
    mgr.load_presets_from_config({"group_chat": ["web_search"]}, registry)
    assert mgr.presets["group_chat"].name == "group_chat"


# ---------- LLMCoordinator._handle_tool_search_request ----------


def test_handle_tool_search_request_enables_into_round_toolset():
    from atribot.LLMchat.LLM_supervisor import (
        GenerationRequestSimplify,
        LLMCoordinator,
    )

    registry = _FakeRegistry(
        [
            _make_tool("web_search", "搜索网页"),
            _make_tool("run_python_code", "运行Python代码"),
        ]
    )
    mgr = _make_manager()
    mgr.load_presets_from_config(
        {
            "group_chat": {
                "default": ["web_search"],
                "deferred": ["run_python_code"],
            }
        },
        registry,
    )
    tool_management = _make_tool_calls_with(mgr, registry)

    coord = LLMCoordinator.__new__(LLMCoordinator)
    coord.tool_management = tool_management
    coord.log = getLogger("test")

    request = GenerationRequestSimplify(model="m", messages=[])
    request.tool_json = tool_management.resolve_toolset(preset="group_chat").copy()

    result = coord._handle_tool_search_request(
        request, ToolSearchRequested(query="run", limit=5)
    )

    assert "run_python_code" in result
    assert "run_python_code" in request.tool_json.names()
    assert "web_search" in request.tool_json.names()
