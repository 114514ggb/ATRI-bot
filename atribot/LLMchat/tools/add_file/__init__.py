from atribot.common_utils import resolve_file_to_bytes
from atribot.core.service_container import container
from atribot.core.type.bot_types import atriMessageEvent
from atribot.LLMchat.sandbox.sandbox_base import SandBoxBase
from atribot.LLMchat.tools.run_python_code.run_code import (
    _COLLECT_MAX_BYTES,
    _upload_bytes_to_sandbox,
    collect_context_file_segments,
)

sand_box: SandBoxBase = container.get("SandBox")

tool_json = {
    "name": "add_file",
    "description": "将聊天上下文中的文件上传到沙盒内指定路径。自动在聊天历史中查找匹配文件名的文件",
    "properties": {
        "file_name": {
            "type": "string",
            "description": "要上传的文件名（需在聊天上下文中存在）",
        },
        "dest": {
            "type": "string",
            "description": "容器内目标绝对路径，默认放在 /workspace/<file_name>",
        },
    },
}


async def main(file_name: str, message_data: atriMessageEvent, dest: str = "") -> str:
    if not container.exists("SandBox"):
        return "[Error] 沙盒未启动。"

    if not sand_box.is_running:
        await sand_box.start()

    segments = await collect_context_file_segments(message_data, [file_name])
    segment = segments[0] if segments else None

    if not segment:
        return f"[Error]在聊天上下文中未找到文件: {file_name}"
    if not segment.url:
        return f"[Error]文件{file_name}没有可下载的地址"

    remote_path = dest if dest else f"{sand_box.work_dir}/{file_name}"
    try:
        _, content = await resolve_file_to_bytes(
            segment.url, file_name, max_bytes=_COLLECT_MAX_BYTES
        )
    except Exception as e:
        return f"[Error]读取文件{file_name}失败: {e}"
    await _upload_bytes_to_sandbox(content=content, remote_path=remote_path)
    return f"已上传 {file_name} → {remote_path} ({len(content)} 字节)"
