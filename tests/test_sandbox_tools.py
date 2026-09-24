"""沙盒依赖工具统一初始化（sandbox_tools）与本地工具全量重载测试

覆盖：
- ``build_tool_json`` 按后端/平台生成描述与 active
- ``sand_box.tool_prompts`` 追加 / 整体替换
- ``ToolRegistry`` 静态 ``tool_json`` 目录扫描
- ``ToolCalls._load_sandbox_tools`` / ``reload_local_tools``（保留 MCP 工具）
- ``session_dirs`` 在不同后端下的工作区路径
"""

import logging

import pytest

from atribot.core.service_container import container
from atribot.LLMchat.sandbox.no_sandbox import NoSandbox
from atribot.LLMchat.tools import sandbox_tools
from atribot.LLMchat.tools.sandbox_tools import env as sandbox_env
from atribot.LLMchat.tools.sandbox_tools import runtime, workspace


class _FakeConfig:
    """最小 config 替身：只暴露 sand_box"""

    def __init__(self, sand_box: dict | None = None) -> None:
        self.sand_box = sand_box or {}


def _register_config(sand_box: dict | None = None) -> None:
    if container.exists("config"):
        container.unregister("config")
    container.register("config", _FakeConfig(sand_box))


def _register_sandbox(sand_box) -> None:
    if container.exists("SandBox"):
        container.unregister("SandBox")
    if sand_box is not None:
        container.register("SandBox", sand_box)


@pytest.fixture(autouse=True)
def _clean_container():
    """每个用例前后清空测试注册的服务，避免互相污染"""
    yield
    for name in ("config", "SandBox"):
        if container.exists(name):
            container.unregister(name)


# ---------------------------------------------------------------------------
# runtime
# ---------------------------------------------------------------------------

def test_runtime_without_sandbox():
    _register_sandbox(None)

    assert runtime.get_sandbox() is None
    assert runtime.sandbox_ready() is False
    assert runtime.sandbox_backend() == runtime.BACKEND_MISSING
    assert runtime.work_dir() == runtime.DEFAULT_CONTAINER_WORK_DIR
    with pytest.raises(RuntimeError):
        runtime.require_sandbox()


def test_runtime_with_local_sandbox(tmp_path):
    sb = NoSandbox(config={"work_dir": str(tmp_path)})
    _register_sandbox(sb)

    assert runtime.get_sandbox() is sb
    assert runtime.is_local_sandbox() is True
    assert runtime.sandbox_backend() == runtime.BACKEND_LOCAL
    assert runtime.work_dir() == tmp_path.resolve().as_posix()
    assert runtime.require_sandbox() is sb


# ---------------------------------------------------------------------------
# workspace
# ---------------------------------------------------------------------------

def test_session_dirs_group_and_private(tmp_path):
    sb = NoSandbox(config={"work_dir": str(tmp_path)})
    _register_sandbox(sb)
    root = tmp_path.resolve().as_posix()

    data_dir, shared_dir, session_type, session_id = workspace.session_dirs(123456, None)
    assert (data_dir, shared_dir, session_type, session_id) == (
        f"{root}/groups/123456/data",
        f"{root}/shared",
        "group",
        "123456",
    )
    assert workspace.session_workspace(123456) == data_dir
    assert workspace.session_tmp_dir(123456) == f"{root}/groups/123456/tmp"

    data_dir, _, session_type, session_id = workspace.session_dirs(None, 987)
    assert (data_dir, session_type, session_id) == (f"{root}/private/987/data", "private", "987")


# ---------------------------------------------------------------------------
# env：描述与 active
# ---------------------------------------------------------------------------

def _build(name: str, facts_backend: str | None = None) -> dict:
    """便捷构建 tool_json（可选强制某个后端事实）"""
    if facts_backend is None:
        return sandbox_env.build_tool_json(name, {"p": {"type": "string"}})
    original = sandbox_env.env_facts
    sandbox_env.env_facts = lambda: {  # type: ignore[assignment]
        "backend": facts_backend,
        "display": facts_backend,
        "platform": "windows",
        "shell": "bash",
        "work_dir": "/tmp/ws",
        "ready": facts_backend != runtime.BACKEND_MISSING,
        "container": facts_backend not in (runtime.BACKEND_MISSING, runtime.BACKEND_LOCAL),
    }
    try:
        return sandbox_env.build_tool_json(name, {"p": {"type": "string"}})
    finally:
        sandbox_env.env_facts = original  # type: ignore[assignment]


def test_build_tool_json_all_sandbox_tools():
    _register_config({})
    _register_sandbox(None)

    for name in sandbox_tools.SANDBOX_TOOL_NAMES:
        tool_json = _build(name)
        assert tool_json["name"] == name
        assert tool_json["description"]
        assert tool_json["active"] is False  # 无沙盒 → 全部禁用


def test_build_tool_json_with_sandbox_enables_tools(tmp_path):
    _register_config({})
    sb = NoSandbox(config={"work_dir": str(tmp_path)})
    _register_sandbox(sb)

    tool_json = _build("run_command", "local")
    assert tool_json["active"] is True
    assert "本机" in tool_json["description"]
    assert "每个会话" in tool_json["description"]


def test_description_differs_between_backends():
    local_desc = _build("run_python_code", "local")["description"]
    docker_desc = _build("run_python_code", "docker")["description"]

    assert "本机" in local_desc
    assert "numpy" not in local_desc
    assert "numpy" in docker_desc
    assert "Python3.12-slim" in docker_desc


def test_shell_hint_adapts_to_windows_shell():
    _register_config({})
    sb = NoSandbox(config={"work_dir": "unused"})
    _register_sandbox(sb)

    original = sandbox_env.env_facts
    sandbox_env.env_facts = lambda: {  # type: ignore[assignment]
        "backend": runtime.BACKEND_LOCAL,
        "display": "本机",
        "platform": "windows",
        "shell": "cmd",
        "work_dir": "/tmp/ws",
        "ready": True,
        "container": False,
    }
    try:
        desc = sandbox_env.build_tool_json("run_command", {})["description"]
    finally:
        sandbox_env.env_facts = original  # type: ignore[assignment]
    assert "cmd.exe" in desc
    assert "mkdir -p" in desc


def test_tool_prompts_string_appends():
    _register_config({"tool_prompts": {"run_command": "本项目请用 uv run python"}})
    sb = NoSandbox(config={"work_dir": "unused"})
    _register_sandbox(sb)

    desc = _build("run_command", "local")["description"]
    assert desc.endswith("本项目请用 uv run python")


def test_tool_prompts_dict_can_replace_description():
    _register_config(
        {"tool_prompts": {"send_file": {"description": "自定义发送说明", "append": "补充"}}}
    )
    sb = NoSandbox(config={"work_dir": "unused"})
    _register_sandbox(sb)

    desc = _build("send_file", "local")["description"]
    assert desc == "自定义发送说明\n补充"


def test_tools_config_can_disable_single_tool(tmp_path):
    _register_config({"tools": {"send_file": False}})
    sb = NoSandbox(config={"work_dir": str(tmp_path)})
    _register_sandbox(sb)

    assert sandbox_env.sandbox_active("send_file") is False
    assert sandbox_env.sandbox_active("run_command") is True
    assert _build("send_file", "local")["active"] is False


# ---------------------------------------------------------------------------
# ToolRegistry：目录扫描与本地工具重载
# ---------------------------------------------------------------------------

def _make_registry(tmp_path):
    from atribot.LLMchat.MCP.tool_calls import ToolRegistry

    log = logging.getLogger("test.sandbox_tools")
    log.addHandler(logging.NullHandler())
    return ToolRegistry(log)


def test_registry_loads_static_tool_json_and_skips_non_tool_dirs(tmp_path):
    """目录扫描应加载静态 tool_json，并跳过未导出 main 的共享包目录"""
    tool_dir = tmp_path / "demo_tool"
    tool_dir.mkdir()
    (tool_dir / "__init__.py").write_text(
        "tool_json = {'name': 'demo_tool', 'description': 'v1',"
        " 'properties': {'a': {'type': 'string'}}}\n"
        "async def main(a: str = ''):\n"
        "    return a\n",
        encoding="utf-8",
    )
    shared_dir = tmp_path / "sandbox_tools"
    shared_dir.mkdir()
    (shared_dir / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")

    registry = _make_registry(tmp_path)
    registry.get_files_in_folder(str(tmp_path))

    names = [t.name for t in registry.func_list]
    assert names == ["demo_tool"]
    assert registry.get_func("demo_tool").description == "v1"


def test_registry_skips_underscore_and_pycache_dirs(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "_shared").mkdir()
    (tmp_path / "_shared" / "__init__.py").write_text("X = 1\n", encoding="utf-8")

    registry = _make_registry(tmp_path)
    registry.get_files_in_folder(str(tmp_path))
    assert registry.func_list == []


def _make_tool_calls(tmp_path):
    from atribot.LLMchat.MCP.tool_calls import (
        ToolCalls,
        ToolPresetManager,
        ToolRegistry,
        ToolSchemaCache,
    )

    log = logging.getLogger("test.tool_calls")
    log.addHandler(logging.NullHandler())
    tc = ToolCalls.__new__(ToolCalls)
    tc.log = log
    tc._registry = ToolRegistry(log)
    tc._preset_manager = ToolPresetManager(log)
    tc._schema_cache = ToolSchemaCache(log)
    tc._deferred_prompt_cache = {}
    tc._tool_path = tmp_path
    return tc


def test_load_sandbox_tools_reflects_sandbox_state(tmp_path):
    """_load_sandbox_tools 应按沙盒状态注册 4 个工具并更新 active"""
    _register_config({})
    _register_sandbox(None)

    tc = _make_tool_calls(tmp_path)
    tc._load_sandbox_tools()

    names = {t.name for t in tc._registry.func_list}
    assert names == set(sandbox_tools.SANDBOX_TOOL_NAMES)
    assert all(t.active is False for t in tc._registry.func_list)

    # 注册沙盒后重载 → 全部启用
    sb = NoSandbox(config={"work_dir": str(tmp_path)})
    _register_sandbox(sb)
    tc._load_sandbox_tools()

    assert len(tc._registry.func_list) == len(sandbox_tools.SANDBOX_TOOL_NAMES)
    assert all(t.active is True for t in tc._registry.func_list)


def test_reload_local_tools_keeps_mcp_tools(tmp_path):
    """reload_local_tools 应保留 MCP 工具并重载本地工具"""
    from atribot.LLMchat.MCP.tool_model import MCPTool

    _register_config({})
    _register_sandbox(None)

    tc = _make_tool_calls(tmp_path)
    mcp_tool = MCPTool(
        name="fake_mcp",
        description="",
        parameters={},
        mcp_tool=None,
        mcp_client=None,
        mcp_server_name="fake",
    )
    tc._registry.func_list.append(mcp_tool)

    reloaded = tc.reload_local_tools()

    names = {t.name for t in tc._registry.func_list}
    assert "fake_mcp" in names
    assert set(sandbox_tools.SANDBOX_TOOL_NAMES) <= set(reloaded)