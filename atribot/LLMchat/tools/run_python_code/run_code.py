import asyncio
import base64
import io
import mimetypes
import os
import tarfile
import uuid
import zipfile

import aiohttp

from atribot.common_utils import resolve_file_to_bytes
from atribot.common_utils.http_client import HTTPClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import File, FileMessageSegment
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox
from atribot.LLMchat.sandbox.sandbox_base import ExecutionResult, GeneratedFile

sand_box:DockerSandbox = container.get("SandBox")


def _safe_filename(name: str) -> str:
    """提取安全的文件名。

    Args:
        name: 原始文件名。

    Returns:
        清理后的文件名，若为空则返回 'input.bin'。
    """
    safe_name = os.path.basename(name).strip()
    return safe_name or "input.bin"


async def _upload_bytes_to_container(content: bytes, remote_path: str) -> None:
    """将二进制内容上传到 Docker 容器。

    Args:
        content: 要上传的二进制数据。
        remote_path: 容器内的目标绝对路径。

    Raises:
        RuntimeError: 容器未初始化时抛出。
    """
    if not sand_box.container:
        raise RuntimeError("Sandbox container is not initialized")

    tar_stream = io.BytesIO()
    file_name = os.path.basename(remote_path)

    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        info = tarfile.TarInfo(name=file_name)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))

    tar_stream.seek(0)
    remote_dir = os.path.dirname(remote_path) or sand_box.work_dir

    await sand_box.run_command(f"mkdir -p {remote_dir}")
    await asyncio.to_thread(
        sand_box.container.put_archive,
        path=remote_dir,
        data=tar_stream,
    )


async def _download_https_file(url: str) -> bytes:
    """从 HTTPS 地址下载文件。

    Args:
        url: 下载地址，必须以 https:// 开头。

    Returns:
        文件的二进制内容。

    Raises:
        ValueError: URL 协议错误或 HTTP 状态码非 2xx。
    """
    if not url.startswith("https://"):
        raise ValueError(f"文件地址必须是 https:// ，当前为: {url}")

    http:HTTPClient = container.get("HTTPClient")
    return await http.get_bytes(url, timeout=aiohttp.ClientTimeout(total=30, connect=10))


async def _collect_generated_files(
    run_dir: str,
    ignored_names: set[str],
    max_file_size: int,
    max_total_size: int,
) -> tuple[list[GeneratedFile], str]:
    """从沙盒运行目录收集新产生的文件

    Args:
        run_dir: 执行目录路径。
        ignored_names: 需要忽略的文件名集合（通常是脚本本身和输入文件）
        max_file_size: 单个文件最大大小限制
        max_total_size: 所有文件总大小限制

    Returns:
        tuple: (生成的 GeneratedFile 列表, 警告信息字符串)。
    """
    bits, _ = await asyncio.to_thread(sand_box.container.get_archive, run_dir)
    file_obj = io.BytesIO()
    downloaded_size = 0
    safe_download_limit = max_total_size + 1024 * 1024 

    for chunk in bits:
        file_obj.write(chunk)
        downloaded_size += len(chunk)
        if downloaded_size > safe_download_limit:
            return [], "\n[System Warning] Archive download aborted. Size exceeds memory safety limit."
    
    file_obj.seek(0)

    generated_files: list[GeneratedFile] = []
    valid_members: list[tuple[tarfile.TarInfo, str]] = []
    total_size = 0
    warnings = []

    with tarfile.open(fileobj=file_obj, mode="r") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue

            filename = os.path.basename(member.name)
            if filename in ignored_names:
                continue

            if member.size > max_file_size:
                warnings.append(
                    f"\n[System Warning] File '{filename}' ignored. "
                    f"Size ({member.size} bytes) exceeds limit ({max_file_size} bytes)."
                )
                continue

            valid_members.append((member, filename))
            total_size += member.size

        if total_size > max_total_size:
            return [], (
                f"\n[System Warning] Generated files ignored. Total size ({total_size} bytes) "
                f"exceeds limit ({max_total_size} bytes)."
            )

        if not valid_members:
            return [], "".join(warnings)

        if len(valid_members) == 1:
            member, filename = valid_members[0]
            extracted = tar.extractfile(member)
            if extracted:
                mime_type, _ = mimetypes.guess_type(filename)
                generated_files.append(
                    GeneratedFile(
                        path=filename,
                        content=extracted.read(),
                        type=mime_type or "application/octet-stream",
                    )
                )
            return generated_files, "".join(warnings)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for member, filename in valid_members:
                extracted = tar.extractfile(member)
                if extracted:
                    zip_file.writestr(filename, extracted.read())

        generated_files.append(
            GeneratedFile(
                path="output.zip",
                content=zip_buffer.getvalue(),
                type="application/zip",
            )
        )

    return generated_files, "".join(warnings)



async def run_python_code(
    code: str, 
    files: list[File] = None,
    timeout: int = 30, 
    max_file_size: int = 20 * 1024 * 1024,
    max_total_size: int = 150 * 1024 * 1024
)->ExecutionResult:
    """在沙盒中执行一次性python代码

    Args:
        code (str): 要执行的代码字符串
        files (list[File]): 要输入到环境的文件列表
        timeout (int, optional): 执行超时时间（秒）. Defaults to 30.
        max_file_size (int, optional): 单个文件最大字节数限制（仅在单文件模式下生效）. Defaults to 20*1024*1024.
        max_total_size (int, optional): 产生的所有文件总大小限制（压缩前）. Defaults to 150*1024*1024.

    Returns:
        ExecutionResult: 包含执行结果的对象
    """
    if not sand_box.is_running:
        await sand_box.start()

    run_id = uuid.uuid4().hex
    run_dir = f"{sand_box.work_dir}/run_{run_id}"
    script_name = "main.py"
    script_path = f"{run_dir}/{script_name}"

    exec_result: ExecutionResult | None = None
    warning_msg = ""
    generated_files: list[GeneratedFile] = []
    ignored_names: set[str] = {script_name}

    try:
        await sand_box.run_command(f"mkdir -p {run_dir}")

        for index, file_item in enumerate(files or [], start=1):
            filename, content = await resolve_file_to_bytes(
                file_item,
                default_name=f"input_{index}.bin",
                max_bytes=max_file_size,
            )
            safe_name = _safe_filename(filename)
            remote_file_path = f"{run_dir}/{safe_name}"
            await _upload_bytes_to_container(content=content, remote_path=remote_file_path)
            ignored_names.add(safe_name)

        b64_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")
        await sand_box.run_command(f"echo {b64_code} | base64 -d > {script_path}")

        exec_result = await sand_box.run_command(
            f"cd {run_dir} && python3 -u {script_name}",
            timeout=timeout,
        )

        try:
            generated_files, warning_msg = await _collect_generated_files(
                run_dir=run_dir,
                ignored_names=ignored_names,
                max_file_size=max_file_size,
                max_total_size=max_total_size,
            )
        except Exception as error:
            warning_msg = f"\n[System Error] Failed to process generated files: {error}"

    finally:
        if run_dir.startswith(sand_box.work_dir) and "run_" in run_dir:
            await sand_box.run_command(f"rm -rf {run_dir}", timeout=5)

    if exec_result is None:
        return ExecutionResult(
            stdout="",
            stderr="Execution failed internally.",
            exit_code=-1,
            text="Execution failed internally.",
            files=[],
        )

    if warning_msg:
        exec_result.stderr += warning_msg
        exec_result.text += warning_msg

    exec_result.files = generated_files
    return exec_result


async def run_python_code_with_segments(
    code: str,
    file_segments: list[FileMessageSegment] | None = None,
    timeout: int = 30,
    max_file_size: int = 100 * 1024 * 1024,
    max_total_size: int = 200 * 1024 * 1024,
) -> ExecutionResult:
    """在沙盒中执行 Python 代码（输入文件来自 FileMessageSegment）。

    约束：
    - 输入文件仅接受 `FileMessageSegment` 及其子类。
    - 文件名使用 `segment.file_name`。
    - 文件内容统一通过 `segment.url` 的 HTTPS 地址下载。
    - 任何输入文件相关问题将直接抛出异常。

    Args:
        code: 要执行的 Python 代码字符串。
        file_segments: 输入文件段列表。
        timeout: 执行超时时间（秒）。
        max_file_size: 单个文件大小限制。
        max_total_size: 生成文件总大小限制。

    Returns:
        ExecutionResult: 包含标准输出、错误输出、退出码及生成文件的对象。

    Raises:
        ValueError: 输入文件配置错误（如缺少文件名或非 HTTPS 链接）。
    """
    if not sand_box.is_running:
        await sand_box.start()

    run_id = uuid.uuid4().hex
    run_dir = f"{sand_box.work_dir}/run_{run_id}"
    script_name = "main.py"
    script_path = f"{run_dir}/{script_name}"

    ignored_names: set[str] = {script_name}

    try:
        await sand_box.run_command(f"mkdir -p {run_dir}")

        for segment in file_segments or []:
            if not segment.file_name:
                raise ValueError("file_name为空")
            if not segment.url:
                raise ValueError(f"文件 {segment.file_name} 缺少可下载的 url")

            await _upload_bytes_to_container(
                content = await _download_https_file(segment.url), 
                remote_path = f"{run_dir}/{segment.file_name}"
            )
            ignored_names.add(segment.file_name)

        b64_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")
        await sand_box.run_command(f"echo {b64_code} | base64 -d > {script_path}")

        exec_result = await sand_box.run_command(
            f"cd {run_dir} && python3 -u {script_name}",
            timeout=timeout,
        )

        generated_files, warning_msg = await _collect_generated_files(
            run_dir=run_dir,
            ignored_names=ignored_names,
            max_file_size=max_file_size,
            max_total_size=max_total_size,
        )

        if warning_msg:
            exec_result.stderr += warning_msg
            exec_result.text += warning_msg

        exec_result.files = generated_files
        return exec_result

    finally:
        if run_dir.startswith(sand_box.work_dir) and "run_" in run_dir:
            await sand_box.run_command(f"rm -rf {run_dir}", timeout=5)
