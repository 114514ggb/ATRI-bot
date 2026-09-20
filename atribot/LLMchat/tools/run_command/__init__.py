import shlex

from atribot.core.service_container import container
from atribot.core.type.bot_types import atriMessageEvent
from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase
from atribot.LLMchat.tools.run_python_code.run_code import is_local_sandbox, session_workspace

sand_box: SandBoxBase = container.get("SandBox")

_MAX_OUTPUT_CHARS = 3000

_env_desc = (
    "在本机直接执行Shell命令(没有沙盒隔离,PATH和文件系统就是本机环境)"
    if is_local_sandbox()
    else "在沙盒中执行中执行Shell命令,环境是Python3.12-slim预装ffmpeg"
)

tool_json = {
    "name": "run_command",
    "description": (
        _env_desc
        + f"拥有独立的持久化工作区：群聊为 {sand_box.work_dir}/groups/<群号>/data,"
        f"私聊为 {sand_box.work_dir}/private/<你的QQ号>/data,不填path时默认使用当前会话的持久化目录 "
        "输出超过限制时仅返回末尾部分,"
        "返回值包含退出码，可据此判断命令是否执行成功"
    ),
    "properties": {
        "command": {
            "type": "string",
            "description": "要执行的 Shell 命令",
        },
        "path": {
            "type": "string",
            "description": "执行命令的目录（容器内绝对路径）不填时默认使用当前会话(群聊按群/私聊按用户)的持久化目录",
        },
        "timeout": {
            "type": "integer",
            "description": "命令超时时间（秒），默认 30,最大 300下载、编译等耗时操作应适当增大",
            "default": 30,
            "minimum": 1,
            "maximum": 300,
        },
    },
    "required": ["command"],
}


async def main(command: str, message_data: atriMessageEvent, path: str | None = None, timeout: int = 30) -> str:
    if not sand_box.is_running:
        await sand_box.start()

    if path is None:
        path = session_workspace(message_data.group_id, message_data.user_id)

    # 确保工作目录存在
    await sand_box.run_command(f"mkdir -p {shlex.quote(path)}", timeout=10)

    timeout = max(1, min(timeout, 300))
    full_cmd = f"cd {shlex.quote(path)} && {command}"

    await message_data.deliver_merge_text(
        message=f"在 {path} 目录执行命令:\n{command}",
        source="执行Shell命令"
    )
    result = await sand_box.run_command(full_cmd, timeout=timeout)

    output = result.text.strip()
    if len(output) > _MAX_OUTPUT_CHARS:
        output = f"[输出过长，截取末尾 {_MAX_OUTPUT_CHARS} 字符]\n...{output[-_MAX_OUTPUT_CHARS:]}"

    status = "成功" if result.exit_code == 0 else f"失败(exit_code={result.exit_code})"
    return f"[{status}]\n{output}" if output else f"[{status}]\n(无输出)"
