from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.service_container import container
from atribot.core.type.bot_types import atriMessageEvent
from atribot.core.type.chat_message_types import FileMessageSegment
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox
from atribot.LLMchat.tools.run_python_code.run_code import (
    _download_https_file,
    _upload_bytes_to_container,
)

sand_box: DockerSandbox = container.get("SandBox")
chat_manager: ChatManager = container.get("ChatManager")

tool_json = {
    "name": "add_file",
    "description": "将群聊上下文中的文件上传到沙盒容器内指定路径。自动在聊天历史中查找匹配文件名的文件",
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

    group_id = message_data.group_id

    segment: FileMessageSegment | None = None
    for message in list((await chat_manager.get_group_context(group_id)).messages):
        for seg in message.segments:
            if isinstance(seg, FileMessageSegment) and seg.file_name == file_name:
                segment = seg
                break
        if segment:
            break

    if not segment:
        return f"[Error]在聊天上下文中未找到文件: {file_name}"
    if not segment.url:
        return f"[Error]文件{file_name}没有可下载的地址"

    remote_path = dest if dest else f"{sand_box.work_dir}/{file_name}"
    content = await _download_https_file(segment.url)
    await _upload_bytes_to_container(content=content, remote_path=remote_path)
    return f"已上传 {file_name} → {remote_path} ({len(content)} 字节)"
