"""沙盒依赖工具的共享包与统一定义

本包**不是**一个工具目录(不导出 ``main``/``tool_json``，目录扫描器不会把它
注册为工具)，而是 4 个沙盒依赖工具(``run_python_code`` /
``run_command`` / ``send_file`` / ``add_file``)的统一实现：

- :mod:`runtime`：沙盒实例的惰性获取、后端/平台/shell 探测
- :mod:`env`：按环境生成工具描述(提示词)与 ``active`` 的 ``tool_json`` 构建
- :mod:`workspace`：沙盒内会话工作区(群/私聊隔离)路径规则
- :mod:`execution`：沙盒内 Python 代码执行引擎
- :mod:`tools`：4 个工具的入口，通过 ``SANDBOX_TOOL_SPECS`` 供 :class:`ToolCalls` 显式注册

导入本包不触发任何注册（工具由 ``ToolCalls._load_sandbox_tools`` 显式加载）。
"""

from atribot.LLMchat.tools.sandbox_tools.env import (
    MAX_OUTPUT_CHARS,
    SANDBOX_TOOL_NAMES,
    build_tool_json,
    env_facts,
    sandbox_active,
)
from atribot.LLMchat.tools.sandbox_tools.runtime import (
    BACKEND_LOCAL,
    BACKEND_MISSING,
    DEFAULT_CONTAINER_WORK_DIR,
    get_sandbox,
    host_platform,
    is_local_sandbox,
    new_run_id,
    require_sandbox,
    sandbox_backend,
    sandbox_display,
    sandbox_ready,
    shell_kind,
    work_dir,
)
from atribot.LLMchat.tools.sandbox_tools.tools import (
    SANDBOX_TOOL_SPECS,
    add_file,
    run_command,
    run_python_code,
    send_file,
)
from atribot.LLMchat.tools.sandbox_tools.workspace import (
    session_dirs,
    session_tmp_dir,
    session_workspace,
)

__all__ = [
    # runtime
    "BACKEND_LOCAL",
    "BACKEND_MISSING",
    "DEFAULT_CONTAINER_WORK_DIR",
    "get_sandbox",
    "host_platform",
    "is_local_sandbox",
    "new_run_id",
    "require_sandbox",
    "sandbox_backend",
    "sandbox_display",
    "sandbox_ready",
    "shell_kind",
    "work_dir",
    # env
    "MAX_OUTPUT_CHARS",
    "SANDBOX_TOOL_NAMES",
    "build_tool_json",
    "env_facts",
    "sandbox_active",
    # workspace
    "session_dirs",
    "session_tmp_dir",
    "session_workspace",
    # tools(4 个沙盒工具处理函数)
    "SANDBOX_TOOL_SPECS",
    "add_file",
    "run_command",
    "run_python_code",
    "send_file",
]