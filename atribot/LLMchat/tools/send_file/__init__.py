import asyncio
import base64
import io
import os
import shlex
import tarfile

from atribot.core.atri_config import atriConfig
from atribot.core.service_container import container
from atribot.core.type.bot_types import atriMessageEvent
from atribot.LLMchat.sandbox.no_sandbox import NoSandbox

sand_box = container.get("SandBox")
config: atriConfig = container.get("config")

_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif"}

_MAX_SEND_BYTES = 200 * 1024 * 1024

tool_json = {
    "name": "send_file",
    "description": "将沙盒内的文件发送到user",
    "properties": {
        "path": {
            "type": "string",
            "description": "沙盒内文件的绝对路径",
        },
    },
}


async def _read_file_content(path: str) -> tuple[bytes, str] | None:
    """读取沙盒内文件,返回 (内容, 文件名);文件不存在返回 None

    Raises:
        RuntimeError: 文件过大或内容无法读取
    """
    if isinstance(sand_box, NoSandbox):
        if not os.path.isfile(path):
            return None
        if os.path.getsize(path) > _MAX_SEND_BYTES:
            raise RuntimeError("文件过大(超过200MB)")
        with open(path, "rb") as f:
            return f.read(), os.path.basename(path) or "file"

    check = await sand_box.run_command(
        f"test -f {shlex.quote(path)} && echo EXISTS || echo NOTFOUND", timeout=5
    )
    if "NOTFOUND" in check.stdout:
        return None

    bits, _ = await asyncio.to_thread(sand_box.container.get_archive, path)
    file_obj = io.BytesIO()
    for chunk in bits:
        file_obj.write(chunk)
        if file_obj.tell() > _MAX_SEND_BYTES:
            raise RuntimeError("文件过大(超过200MB)")
    file_obj.seek(0)

    with tarfile.open(fileobj=file_obj, mode="r") as tar:
        members = [m for m in tar.getmembers() if m.isfile()]
        if not members:
            raise RuntimeError("无法提取文件内容")
        extracted = tar.extractfile(members[0])
        if not extracted:
            raise RuntimeError("无法读取文件内容")
        content = extracted.read()
        filename = members[0].name.split("/")[-1] or "file"
    return content, filename


async def main(path: str, message_data: atriMessageEvent) -> str:
    if not container.exists("SandBox") or not sand_box.is_running:
        return "[Error]沙盒未运行"

    try:
        read_result = await _read_file_content(path)
    except Exception as e:
        return f"[Error]读取沙盒文件失败:{e}"

    if read_result is None:
        return f"[Error]文件不存在:{path}"
    content, filename = read_result

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    b64_content = f"base64://{base64.b64encode(content).decode()}"
    if ext in _IMAGE_EXTS:
        await message_data.deliver_image(b64_content, local_Path_type=False)
        return f"已发送图片:{filename}"
    else:
        await message_data.deliver_file(url_file=b64_content, name=filename, local_Path_type=False)
        return f"已发送文件: {filename}"
