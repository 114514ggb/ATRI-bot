import shlex

from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox

sand_box: DockerSandbox = container.get("SandBox")
send_message:QQAPIClient = container.get("SendMessage")

_MAX_OUTPUT_CHARS = 3000

tool_json = {
    "name": "run_command",
    "description": (
        "在沙盒中执行中执行Shell命令,环境是Python3.12-slim预装ffmpeg"
        "拥有独立的持久化工作区：/workspace/groups/<群号>/data "
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
            "description": "工作目录（容器内绝对路径）不填时默认使用当前群的持久化目录 /workspace/groups/<群号>/data",
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


async def main(command: str, message_data: ChatMessage, path: str | None = None, timeout: int = 30) -> str:
    if not sand_box.is_running:
        await sand_box.start()

    if path is None:
        path = f"/workspace/groups/{message_data.group_id}/data"

    # 确保工作目录存在
    await sand_box.run_command(f"mkdir -p {shlex.quote(path)}", timeout=10)

    timeout = max(1, min(timeout, 300))
    full_cmd = f"cd {shlex.quote(path)} && {command}"

    await send_message.send_group_merge_text(
        group_id=message_data.group_id,
        message=f"在 {path} 目录执行命令:\n{command}",
        source="执行Shell命令"
    )
    result = await sand_box.run_command(full_cmd, timeout=timeout)

    output = result.text.strip()
    if len(output) > _MAX_OUTPUT_CHARS:
        output = f"[输出过长，截取末尾 {_MAX_OUTPUT_CHARS} 字符]\n...{output[-_MAX_OUTPUT_CHARS:]}"

    status = "成功" if result.exit_code == 0 else f"失败(exit_code={result.exit_code})"
    return f"[{status}]\n{output}" if output else f"[{status}]\n(无输出)"
