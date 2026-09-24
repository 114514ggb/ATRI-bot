"""沙盒依赖工具统一定义（run_python_code / run_command / send_file / add_file）

四个工具的 handler 统一在此定义，并以 ``SANDBOX_TOOL_SPECS`` 导出给
:class:`ToolCalls` 显式注册；描述与启用状态由 :func:`env.build_tool_json`
按当前沙盒环境(后端 x 平台 x shell)在加载/重载时生成。
"""

import asyncio
import base64
import io
import os
import shlex
import tarfile
from typing import Any

from atribot.common_utils import resolve_file_to_bytes
from atribot.core.type.bot_types import atriMessageEvent
from atribot.LLMchat.sandbox.no_sandbox import NoSandbox
from atribot.LLMchat.sandbox.sandbox_base import ExecutionResult
from atribot.LLMchat.tools.sandbox_tools.env import MAX_OUTPUT_CHARS
from atribot.LLMchat.tools.sandbox_tools.execution import (
    _COLLECT_MAX_BYTES,
    _upload_bytes_to_sandbox,
    collect_context_file_segments,
    run_python_code_with_segments,
)
from atribot.LLMchat.tools.sandbox_tools.runtime import require_sandbox
from atribot.LLMchat.tools.sandbox_tools.workspace import session_workspace

_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif"}
_MAX_SEND_BYTES = 200 * 1024 * 1024

_RUN_PYTHON_CODE_PROPERTIES = {
    "code": {"type": "string", "description": "The Python code to execute"},
    "files": {
        "type": "array",
        "description": "你在上下文中看到的要临时使用文件名称列表，会自动把对应文件名的文件放在脚本同级目录,脚本运行完后删除",
        "items": {"type": "string"},
    },
}

_RUN_COMMAND_PROPERTIES = {
    "command": {"type": "string", "description": "要执行的 Shell 命令"},
    "path": {
        "type": "string",
        "description": "执行命令的目录(沙盒内绝对路径)不填时默认使用当前会话(群聊按群/私聊按用户)的持久化目录",
    },
    "timeout": {
        "type": "integer",
        "description": "命令超时时间(秒)，默认 30,最大 300下载、编译等耗时操作应适当增大",
        "default": 30,
        "minimum": 1,
        "maximum": 300,
    },
}

_SEND_FILE_PROPERTIES = {
    "path": {"type": "string", "description": "沙盒内文件的绝对路径"},
}

_ADD_FILE_PROPERTIES = {
    "file_name": {"type": "string", "description": "要上传的文件名(需在聊天上下文中存在)"},
    "dest": {"type": "string", "description": "沙盒内目标绝对路径，留空时默认上传到沙盒工作区根目录"},
}


async def run_python_code(code: str, message_data: atriMessageEvent, files: list[str] | None = None) -> str:
    """在沙盒中执行 Python 代码并回传生成文件"""
    require_sandbox()

    file_segments = []
    if files:
        file_segments = await collect_context_file_segments(message_data, files)

    execution_result: ExecutionResult = await run_python_code_with_segments(
        code=code,
        group_id=message_data.group_id,
        user_id=message_data.user_id,
        file_segments=file_segments,
    )

    output_text = execution_result.text
    if len(output_text) > MAX_OUTPUT_CHARS:
        output_text = f"[截取末尾{MAX_OUTPUT_CHARS}字符]\n...{output_text[-MAX_OUTPUT_CHARS:]}"

    await message_data.deliver_merge_text(
        message=f"{code}\n\n执行的输出:\n{output_text}",
        source="执行的代码",
    )

    if execution_result.files:
        file = execution_result.files[0]
        filename = file.path

        if (filename.rsplit(".", 1)[-1].lower() if "." in filename else "") in _IMAGE_EXTS:
            await message_data.deliver_image("base64://" + file.to_base64(), local_Path_type=False)
            return f"代码执行结果是:{output_text}\n并且已经发送代码生成图片:{filename}"
        else:
            await message_data.deliver_file(
                url_file="base64://" + file.to_base64(),
                name=file.path,
                local_Path_type=False,
            )
            return f"代码执行结果是:{output_text}\n并且已经打包发送代码生成文件:{filename}"

    return f"代码执行结果是:{output_text}"


async def run_command(command: str, message_data: atriMessageEvent, path: str | None = None, timeout: int = 30) -> str:
    """在沙盒中执行 Shell 命令"""
    sand_box = require_sandbox()
    if not sand_box.is_running:
        await sand_box.start()

    if path is None:
        path = session_workspace(message_data.group_id, message_data.user_id)

    is_cmd = getattr(sand_box, "shell_kind", "sh") == "cmd"
    # 按 shell 方言选择「确保目录存在」与「切到该目录」的写法
    ensure_dir = (
        f'if not exist "{path}" mkdir "{path}"' if is_cmd else f"mkdir -p {shlex.quote(path)}"
    )
    cd_prefix = f'cd /d "{path}"' if is_cmd else f"cd {shlex.quote(path)}"

    await sand_box.run_command(ensure_dir, timeout=10)
    timeout = max(1, min(timeout, 300))
    full_cmd = f"{cd_prefix} && {command}"

    await message_data.deliver_merge_text(
        message=f"在 {path} 目录执行命令:\n{command}",
        source="执行Shell命令",
    )
    result = await sand_box.run_command(full_cmd, timeout=timeout)

    output = result.text.strip()
    if len(output) > MAX_OUTPUT_CHARS:
        output = f"[输出过长，截取末尾 {MAX_OUTPUT_CHARS} 字符]\n...{output[-MAX_OUTPUT_CHARS:]}"

    status = "成功" if result.exit_code == 0 else f"失败(exit_code={result.exit_code})"
    return f"[{status}]\n{output}" if output else f"[{status}]\n(无输出)"


async def _read_file_content(path: str) -> tuple[bytes, str] | None:
    """读取沙盒内文件,返回 (内容, 文件名);文件不存在返回 None

    Raises:
        RuntimeError: 文件过大或内容无法读取
    """
    sand_box = require_sandbox()
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


async def send_file(path: str, message_data: atriMessageEvent) -> str:
    """将沙盒内生成的文件发送给用户"""
    sand_box = require_sandbox()
    if not sand_box.is_running:
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


async def add_file(file_name: str, message_data: atriMessageEvent, dest: str = "") -> str:
    """将聊天上下文中的文件上传到沙盒内指定路径"""
    sand_box = require_sandbox()

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


SANDBOX_TOOL_SPECS: list[tuple[str, Any, dict, dict]] = [
    ("run_python_code", run_python_code, _RUN_PYTHON_CODE_PROPERTIES, {}),
    ("run_command", run_command, _RUN_COMMAND_PROPERTIES, {"required": ["command"]}),
    ("send_file", send_file, _SEND_FILE_PROPERTIES, {}),
    ("add_file", add_file, _ADD_FILE_PROPERTIES, {}),
]
