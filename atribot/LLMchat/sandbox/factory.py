"""根据 sand_box 配置构建沙盒实例

新增后端时在此登记 type → 类的映射(保持 import 惰性，避免可选依赖拖垮启动)。
"""

from pathlib import Path

from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase

# 归一化后的后端类型：本地直执行(无隔离)
LOCAL_SANDBOX_TYPES = ("none", "no_sandbox", "nosandbox", "local")

# 本地后端工作区在 document 下的默认子目录
DOCUMENT_WORK_SUBDIR = "work"


def normalize_sandbox_type(sandbox_type: str | None) -> str:
    """把配置中的 type 归一化成后端标识

    Args:
        sandbox_type: 配置里的 ``sand_box.type``，为空时视为 ``docker``

    Returns:
        ``"local"`` / ``"e2b"`` / ``"docker"`` 之一
    """
    value = str(sandbox_type or "docker").strip().lower()
    if value in LOCAL_SANDBOX_TYPES:
        return "local"
    if value == "e2b":
        return "e2b"
    return "docker"


def resolve_sandbox_config(
    config: dict | None,
    document_root: Path | str | None = None,
) -> dict:
    """补齐沙盒配置中的默认值

    本地(no-sandbox)后端直接在宿主机执行，其工作区默认放到
    ``document/work`` 下（群聊 / 私聊各自子目录由工具层划分），方便统一管理；
    docker / e2b 等隔离后端不受影响（容器内固定为 ``/workspace`` 或云端路径）。

    Args:
        config: 原始 ``sand_box`` 配置
        document_root: document 根目录，用于推导本地后端工作区（为空则保持后端默认值）

    Returns:
        补齐后的新配置字典
    """
    resolved: dict = dict(config or {})
    if document_root and normalize_sandbox_type(resolved.get("type")) == "local":
        if not resolved.get("work_dir"):
            resolved["work_dir"] = str(Path(document_root) / DOCUMENT_WORK_SUBDIR)
    return resolved


def create_sandbox(config: dict | None) -> SandBoxBase:
    """按 sand_box.type 构建(但不启动)沙盒实例

    - docker(默认): Docker 容器沙盒
    - none/no_sandbox/nosandbox/local: 本机直执行(无隔离)
    - e2b: E2B 云端沙盒
    """
    cfg = config or {}
    sandbox_type = normalize_sandbox_type(cfg.get("type"))

    if sandbox_type == "local":
        from atribot.LLMchat.sandbox.no_sandbox import NoSandbox

        return NoSandbox(config=cfg)
    if sandbox_type == "e2b":
        from atribot.LLMchat.sandbox.E2B_sandbox import E2BSandbox

        return E2BSandbox(config=cfg)

    from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox

    return DockerSandbox(config=cfg)
