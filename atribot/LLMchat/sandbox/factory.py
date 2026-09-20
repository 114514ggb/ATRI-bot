"""根据 sand_box 配置构建沙盒实例

新增后端时在此登记 type → 类的映射（保持 import 惰性，避免可选依赖拖垮启动）。
"""

from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase


def create_sandbox(config: dict | None) -> SandBoxBase:
    """按 sand_box.type 构建（但不启动）沙盒实例

    - docker（默认）: Docker 容器沙盒
    - none/no_sandbox/nosandbox/local: 本机直执行（无隔离）
    - e2b: E2B 云端沙盒
    """
    cfg = config or {}
    sandbox_type = str(cfg.get("type", "docker")).strip().lower()

    if sandbox_type in ("none", "no_sandbox", "nosandbox", "local"):
        from atribot.LLMchat.sandbox.no_sandbox import NoSandbox

        return NoSandbox(config=cfg)
    if sandbox_type == "e2b":
        from atribot.LLMchat.sandbox.E2B_sandbox import E2BSandbox

        return E2BSandbox(config=cfg)

    from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox

    return DockerSandbox(config=cfg)
