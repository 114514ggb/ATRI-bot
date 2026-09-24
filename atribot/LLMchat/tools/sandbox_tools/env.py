"""沙盒依赖工具的环境探测与提示词(tool_json)构建

同一条工具在不同环境下需要不同的描述：隔离容器里预装了固定依赖，而本机
直执行(no-sandbox)时依赖、PATH、shell 方言都随宿主环境变化。本模块把
这些差异收敛成一套模板：

```
description = 内置模板(后端 X 平台 X shell) + sand_box.tool_prompts.<工具名>
active      = 沙盒已注册(且未被 sand_box.tools.<工具名> 显式禁用)
```

:func:`build_tool_json` 在工具加载/重载时被调用一次，生成描述与启用状态；
沙盒环境变化时由 ``ToolCalls.reload_local_tools()`` 全量重载本地工具生效。
"""

from typing import Any, Callable, Dict

from atribot.core.service_container import container
from atribot.LLMchat.tools.sandbox_tools import runtime

MAX_OUTPUT_CHARS = 3000


def _sandbox_config() -> dict:
    """读取 config.json 的 ``sand_box`` 配置块(失败时返回空字典)"""
    try:
        config = container.get("config")
        value = getattr(config, "sand_box", None)
        return dict(value) if value else {}
    except Exception:
        return {}


def env_facts() -> dict:
    """采集当前沙盒环境事实(供描述模板与面板展示使用)"""
    backend = runtime.sandbox_backend()
    return {
        "backend": backend,
        "display": runtime.sandbox_display(),
        "platform": runtime.host_platform(),
        "shell": runtime.shell_kind(),
        "work_dir": runtime.work_dir(),
        "ready": runtime.sandbox_ready(),
        "container": backend not in (runtime.BACKEND_MISSING, runtime.BACKEND_LOCAL),
    }


def sandbox_active(tool_name: str | None = None) -> bool:
    """计算工具是否应暴露给模型

    沙盒服务不存在时所有沙盒依赖工具一并禁用；``sand_box.tools`` 可用
    ``{"工具名": false}`` 显式关闭某个工具。

    Args:
        tool_name: 工具名，用于读取显式禁用配置

    Returns:
        是否启用
    """
    if not runtime.sandbox_ready():
        return False
    if tool_name:
        overrides = _sandbox_config().get("tools")
        if isinstance(overrides, dict) and tool_name in overrides:
            return bool(overrides[tool_name])
    return True




def _runtime_desc(facts: dict) -> str:
    """执行环境一句话：在哪执行、什么环境"""
    backend = facts["backend"]
    if backend == runtime.BACKEND_MISSING:
        return "沙盒当前不可用(未初始化或启动失败)"
    if backend == runtime.BACKEND_LOCAL:
        platform_name = "Windows" if facts["platform"] == "windows" else "Linux"
        return (
            f"在本机 {platform_name} 环境直接执行(没有沙盒隔离,"
            f"PATH 与文件系统就是本机环境,与 bot 进程同一套运行环境)"
        )
    if backend == "e2b":
        return "在 E2B 云端沙盒中执行(环境取决于所用云端模板)"
    return "在沙盒容器中执行(环境是 Python3.12-slim 预装 ffmpeg)"


def _python_libs_desc(facts: dict) -> str:
    """Python 可用依赖说明"""
    backend = facts["backend"]
    if backend == runtime.BACKEND_LOCAL:
        return "可用库取决于本机 Python 环境"
    if backend == "e2b":
        return "可用库取决于云端模板"
    return (
        "可用库:numpy,pandas,matplotlib,seaborn,pillow,opencv-python-headless"
        "图表如需显示中文,linux安装了fonts-wqy-zenhei字体,环境还有ffmpeg"
    )


def _shell_hint(facts: dict) -> str:
    """shell 方言提示(命令写法差异)"""
    if facts["backend"] == runtime.BACKEND_LOCAL and facts["platform"] == "windows":
        shell = facts["shell"]
        if shell == "cmd":
            return (
                "命令由 cmd.exe 执行,请使用 Windows 原生命令"
                "(如 dir/type/findstr),不要使用 ls/rm/mkdir -p 等 POSIX 语法"
            )
        if shell == "powershell":
            return (
                "命令由 PowerShell 执行,请使用 PowerShell 语法"
                "(如 Get-ChildItem/Remove-Item),不要使用 ls/rm 等 POSIX 命令"
            )
        return (
            "命令由 Git Bash 执行,支持 mkdir -p、rm -rf 等 POSIX 语法,"
            "请勿使用 cmd 专有命令"
        )
    return "命令由 /bin/sh 执行"


def _workspace_desc(facts: dict, *, env_exports: bool) -> str:
    """工作区说明：路径根目录 + 会话隔离规则"""
    scope = "本机" if facts["backend"] == runtime.BACKEND_LOCAL else "沙盒内"
    text = (
        f"每个会话(群聊按群/私聊按用户)拥有独立持久化工作区,"
        f"目录位于{scope} {facts['work_dir']} 下,跨次调用保留文件"
    )
    if env_exports:
        text += (
            ",可通过 os.environ 访问:"
            "SESSION_WORKSPACE=当前会话持久目录, SHARED_DIR=共享目录"
        )
    return text



def _build_run_python_code(facts: dict) -> str:
    """run_python_code 的描述"""
    return (
        f"执行 Python 代码,可传入输入文件并返回执行结果与新生成文件。"
        f"{_runtime_desc(facts)},"
        f"{_python_libs_desc(facts)}。"
        f"{_workspace_desc(facts, env_exports=True)};"
        f"生成文件直接写在脚本同级目录且不超过 20MB 时会自动发送给你"
    )


def _build_run_command(facts: dict) -> str:
    """run_command 的描述"""
    return (
        f"执行 Shell 命令。"
        f"{_runtime_desc(facts)},"
        f"{_shell_hint(facts)}。"
        f"{_workspace_desc(facts, env_exports=False)},"
        f"不填 path 时默认在会话持久化目录中执行;"
        f"输出超过限制时仅返回末尾部分,返回值包含退出码,可据此判断命令是否执行成功"
    )


def _build_send_file(facts: dict) -> str:
    """send_file 的描述"""
    scope = "本机" if facts["backend"] == runtime.BACKEND_LOCAL else "沙盒内"
    return (
        f"将{scope}生成的文件发送给用户(图片会直接发送,其他类型作为文件发送)。"
        f"path 使用{scope}文件的绝对路径,目录根为 {facts['work_dir']}"
    )


def _build_add_file(facts: dict) -> str:
    """add_file 的描述"""
    scope = "本机" if facts["backend"] == runtime.BACKEND_LOCAL else "沙盒内"
    return (
        f"将聊天上下文中的文件上传到{scope}指定路径,自动在聊天历史中查找匹配文件名的文件。"
        f"dest 为{scope}目标绝对路径,默认放在 {facts['work_dir']}/<文件名>"
    )


_BUILDERS: Dict[str, Callable[[dict], str]] = {
    "run_python_code": _build_run_python_code,
    "run_command": _build_run_command,
    "send_file": _build_send_file,
    "add_file": _build_add_file,
}

SANDBOX_TOOL_NAMES: tuple[str, ...] = tuple(_BUILDERS)

_UNAVAILABLE_NOTE = (
    "沙盒当前不可用(未初始化或启动失败),该工具已被禁用。"
    "请检查 config.json 的 sand_box 配置或联系管理员"
)
"""沙盒不可用时的统一描述(此时工具 active=False，不会进入模型可见的 schema)"""


def _tool_prompt_override(tool_name: str) -> tuple[str | None, str]:
    """读取 ``sand_box.tool_prompts`` 中对该工具的定制

    Args:
        tool_name: 工具名

    Returns:
        tuple: (整体覆盖的 description 或 None, 追加文本)
    """
    prompts = _sandbox_config().get("tool_prompts")
    if not isinstance(prompts, dict):
        return None, ""
    value = prompts.get(tool_name)
    if value is None:
        return None, ""
    if isinstance(value, str):
        return None, value
    if isinstance(value, dict):
        full = value.get("description")
        append = value.get("append") or ""
        return (str(full) if full else None), str(append)
    return None, ""


def build_tool_json(
    tool_name: str,
    properties: Dict[str, Any],
    defaults: Dict[str, Any] | None = None,
) -> dict:
    """构建沙盒依赖工具的 tool_json

    Args:
        tool_name: 工具名(同时也是 :data:`_BUILDERS` 的键)
        properties: 参数 properties 的 JSON Schema
        defaults: 附加字段(如 ``concurrent`` / ``background`` / ``chat_scope``)

    Returns:
        可直接供 ``ToolRegistry`` 读取的 tool_json

    Raises:
        KeyError: 未登记的沙盒工具名
    """
    builder = _BUILDERS[tool_name]
    facts = env_facts()
    if facts["backend"] == runtime.BACKEND_MISSING:
        # 沙盒不可用时工具不会暴露给模型，描述只保留"为什么不可用"的说明
        description = _UNAVAILABLE_NOTE
    else:
        description = builder(facts)

    override, append = _tool_prompt_override(tool_name)
    if override:
        description = override
    if append:
        description = f"{description}\n{append}"

    tool_json: Dict[str, Any] = dict(defaults or {})
    tool_json.update(
        {
            "name": tool_name,
            "description": description,
            "properties": properties,
            "active": sandbox_active(tool_name),
        }
    )
    return tool_json