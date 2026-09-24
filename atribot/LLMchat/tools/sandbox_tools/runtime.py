"""沙盒依赖工具的共享运行时

集中为 4 个沙盒依赖工具(``run_python_code`` / ``run_command`` / ``send_file`` /
``add_file``)提供统一的环境探测与沙盒获取入口。

设计要点：

- **惰性获取**：模块导入期绝不调用 ``container.get("SandBox")``。工具模块被
  ``ToolRegistry`` 以 ``exec_module`` 方式加载，任何导入期异常都会导致工具整体
  消失；沙盒未注册时工具仍应留在注册表中(由 ``active`` 决定是否暴露给模型)。
- **描述基座**：后端标识、宿主平台、shell 方言等事实统一在此采集，供
  :mod:`atribot.LLMchat.tools.sandbox_tools.env` 生成提示词文案。
"""

import os
import sys
import uuid
from typing import TYPE_CHECKING

from atribot.core.service_container import container

if TYPE_CHECKING:
    from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase

# 后端标识常量
BACKEND_MISSING = "none"
"""沙盒服务不存在"""
BACKEND_LOCAL = "local"
"""本机直执行后端(no-sandbox，无隔离)"""

DEFAULT_CONTAINER_WORK_DIR = "/workspace"
"""隔离后端(容器)内的工作区根目录兜底值"""


def get_sandbox() -> "SandBoxBase | None":
    """获取当前沙盒实例

    Returns:
        已注册的沙盒实例；未注册或获取失败时返回 ``None``(不抛异常)
    """
    try:
        return container.get("SandBox")
    except Exception:
        return None


def require_sandbox() -> "SandBoxBase":
    """获取当前沙盒实例，缺失时抛异常

    供工具执行入口使用：即使 ``active`` 已被关闭，模型仍可能因为历史上下文
    调用到旧工具，此时应给出明确错误而不是 AttributeError。

    Raises:
        RuntimeError: 沙盒服务不存在

    Returns:
        已注册的沙盒实例
    """
    sand_box = get_sandbox()
    if sand_box is None:
        raise RuntimeError(
            "沙盒未初始化(容器中不存在 SandBox 服务)，请检查 config.json 的 sand_box 配置"
        )
    return sand_box


def sandbox_ready() -> bool:
    """沙盒服务是否已注册"""
    return get_sandbox() is not None


def is_local_sandbox() -> bool:
    """当前沙盒是否为本地直执行后端(no-sandbox)"""
    from atribot.LLMchat.sandbox.no_sandbox import NoSandbox

    return isinstance(get_sandbox(), NoSandbox)


def sandbox_backend() -> str:
    """当前沙盒后端标识

    Returns:
        ``"local"``(本机直执行)/ ``"docker"`` / ``"e2b"`` / 其他后端自定义值；
        沙盒缺失时为 ``"none"``
    """
    sand_box = get_sandbox()
    if sand_box is None:
        return BACKEND_MISSING
    if is_local_sandbox():
        return BACKEND_LOCAL
    return str(getattr(sand_box, "backend", "unknown"))


def sandbox_display() -> str:
    """当前沙盒的展示名(用于日志与提示词)"""
    sand_box = get_sandbox()
    if sand_box is None:
        return "无(未初始化)"
    return str(getattr(sand_box, "backend_display", sandbox_backend()))


def host_platform() -> str:
    """宿主平台标识：``"windows"`` / ``"linux"`` 等(``sys.platform`` 简化值)"""
    if os.name == "nt":
        return "windows"
    return "linux" if sys.platform.startswith("linux") else sys.platform


def shell_kind() -> str:
    """当前命令执行所用的 shell 方言：``sh`` / ``bash`` / ``cmd`` / ``powershell``"""
    sand_box = get_sandbox()
    if sand_box is None:
        return "sh"
    return str(getattr(sand_box, "shell_kind", "sh"))


def work_dir() -> str:
    """当前沙盒的工作区根目录(沙盒缺失或后端未声明时返回容器默认值)"""
    sand_box = get_sandbox()
    if sand_box is None:
        return DEFAULT_CONTAINER_WORK_DIR
    value = getattr(sand_box, "work_dir", None)
    return str(value) if value else DEFAULT_CONTAINER_WORK_DIR


def new_run_id() -> str:
    """生成一次执行/访问的随机标识(用于临时目录命名)"""
    return uuid.uuid4().hex