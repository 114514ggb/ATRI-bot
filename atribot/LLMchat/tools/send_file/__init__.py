import asyncio
import base64
import io
import shlex
import shutil
import tarfile
from uuid import uuid4

from atribot.core.atri_config import atriConfig
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox

sand_box: DockerSandbox = container.get("SandBox")
send_message: QQAPIClient = container.get("SendMessage")
config: atriConfig = container.get("config")

_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif"}

tool_json = {
    "name": "send_file",
    "description": "将沙盒容器内的文件发送到群聊",
    "properties": {
        "path": {
            "type": "string",
            "description": "容器内文件的绝对路径",
        },
    },
}


async def main(path: str, message_data: ChatMessage) -> str:
    if not container.exists("SandBox") or not sand_box.is_running:
        return "[Error]沙盒未运行"

    group_id = message_data.group_id

    check = await sand_box.run_command(
        f"test -f {shlex.quote(path)} && echo EXISTS || echo NOTFOUND", timeout=5
    )
    if "NOTFOUND" in check.stdout:
        return f"[Error]文件不存在:{path}"

    try:
        bits, _ = await asyncio.to_thread(sand_box.container.get_archive, path)
        file_obj = io.BytesIO()
        for chunk in bits:
            file_obj.write(chunk)
            if file_obj.tell() > 200 * 1024 * 1024:
                return "[Error]文件过大(超过200MB)"
        file_obj.seek(0)

        with tarfile.open(fileobj=file_obj, mode="r") as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            if not members:
                return "[Error]无法提取文件内容"
            extracted = tar.extractfile(members[0])
            if not extracted:
                return "[Error]无法读取文件内容"
            content = extracted.read()
            filename = members[0].name.split("/")[-1] or "file"
    except Exception as e:
        return f"[Error]读取容器文件失败:{e}"

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _IMAGE_EXTS:
        await send_message.send_group_pictures(
            group_id=group_id,
            url_img=f"base64://{base64.b64encode(content).decode()}",
            local_Path_type=False,
        )
        return f"已发送图片:{filename}"
    else:
        temp_dir = config.file_path.temp / f"send_file_{uuid4().hex}"
        temp_path = temp_dir / filename
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_bytes(content)
        try:
            await send_message.send_group_file(
                group_id=group_id,
                url_file=str(temp_path),
                local_Path_type=True,
                echo=True,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return f"已发送文件: {filename}"
