import asyncio
import base64
import io
import mimetypes
import os
import shutil
import sys
import tarfile
import tempfile
import uuid
import zipfile

from atribot.common_utils import resolve_file_to_bytes
from atribot.core.service_container import container
from atribot.core.type.bot_types import atriMessageEvent
from atribot.core.type.chat_message_types import File, FileMessageSegment
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox
from atribot.LLMchat.sandbox.no_sandbox import NoSandbox
from atribot.LLMchat.sandbox.sandbox_base import ExecutionResult, GeneratedFile, SandBoxBase

sand_box: SandBoxBase = container.get("SandBox")

_COLLECT_MAX_BYTES = 200 * 1024 * 1024
"""输入文件进沙盒的大小上限（与 send_file 的 200MB 读取上限对齐）"""


async def collect_context_file_segments(
    message_data: atriMessageEvent,
    names: list[str],
) -> list[FileMessageSegment]:
    """按文件名收集要进沙盒的输入文件段

    优先使用事件上注入的 file_resolver（WebUI 附件注册表，返回本地路径段），
    未注入时回退到 ChatManager 聊天上下文检索（QQ 平台，url 为网络地址）。
    只返回匹配到的段，缺失的文件名由调用方决定如何提示。
    """
    resolver = message_data.get_extra("file_resolver")
    if callable(resolver):
        return list(resolver(names) or [])

    from atribot.core.cache.management_chat_example import ChatManager

    chat_manager: ChatManager = container.get("ChatManager")
    remaining = set(names)
    if message_data.group_id is not None:
        context_messages = (await chat_manager.get_group_context(message_data.group_id)).messages
    else:
        context_messages = (await chat_manager.get_private_context(message_data.user_id)).messages

    segments: list[FileMessageSegment] = []
    for message in list(context_messages):
        for segment in message.segments:
            if isinstance(segment, FileMessageSegment) and segment.file_name in remaining:
                segments.append(segment)
                remaining.remove(segment.file_name)
                if not remaining:
                    return segments
    return segments


def session_dirs(group_id: int | None, user_id: int | None = None) -> tuple[str, str, str, str]:
    """返回会话工作区路由信息

    群聊按群号隔离: {work_dir}/groups/<群号>/
    私聊按用户隔离: {work_dir}/private/<QQ号>/
    执行结束后只清理 tmp/run_{uuid} 临时目录,data/ 目录永久保留

    Returns:
        tuple: (data_dir, shared_dir, session_type, session_id)
            data_dir 为该会话的持久化数据目录,shared_dir 为全局共享目录
    """
    if group_id is not None:
        session_type = "group"
        session_id = str(group_id)
        session_root = f"{sand_box.work_dir}/groups/{session_id}"
    else:
        session_type = "private"
        session_id = str(user_id) if user_id is not None else "anonymous"
        session_root = f"{sand_box.work_dir}/private/{session_id}"
    return f"{session_root}/data", f"{sand_box.work_dir}/shared", session_type, session_id


def session_workspace(group_id: int | None, user_id: int | None = None) -> str:
    """返回会话(群/私聊用户)的持久化数据目录(容器内绝对路径)"""
    data_dir, _, _, _ = session_dirs(group_id, user_id)
    return data_dir


def is_local_sandbox() -> bool:
    """当前沙盒是否为本地执行后端(no-sandbox)"""
    return isinstance(sand_box, NoSandbox)


def _python3_command() -> str:
    """返回 shell 命令行中使用的 python 解释器

    Windows 本地后端下 PATH 上的 python3 通常是无参即退出的应用商店存根,
    因此改用当前进程解释器的绝对路径(带引号,兼容含空格路径)
    """
    if is_local_sandbox() and os.name == "nt":
        return f'"{sys.executable}"' if sys.executable else "python"
    return "python3"


async def _ensure_sandbox_dirs(*dirs: str) -> None:
    """确保沙盒内的目录存在

    Docker 走 shell 的 mkdir -p;本地后端直接创建,不依赖 shell 命令
    """
    if isinstance(sand_box, NoSandbox):
        for d in dirs:
            os.makedirs(d, exist_ok=True)
        return
    await sand_box.run_command(f"mkdir -p {' '.join(dirs)}")


async def _write_script(code: str, script_path: str) -> None:
    """把代码写入沙盒内的脚本文件"""
    if isinstance(sand_box, NoSandbox):
        await _upload_bytes_to_sandbox(code.encode("utf-8"), script_path)
        return
    b64_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")
    await sand_box.run_command(f"echo {b64_code} | base64 -d > {script_path}")


async def _cleanup_sandbox_dir(dir_path: str) -> None:
    """删除沙盒内的临时目录"""
    if isinstance(sand_box, NoSandbox):
        await asyncio.to_thread(shutil.rmtree, dir_path, True)
        return
    await sand_box.run_command(f"rm -rf {dir_path}", timeout=5)


def _safe_filename(name: str) -> str:
    """提取安全的文件名。

    Args:
        name: 原始文件名。

    Returns:
        清理后的文件名，若为空则返回 'input.bin'。
    """
    safe_name = os.path.basename(name).strip()
    return safe_name or "input.bin"


async def _upload_bytes_to_sandbox(content: bytes, remote_path: str) -> None:
    """将二进制内容写入沙盒

    Docker 后端走内存 tar + put_archive;其余后端(如本地 no-sandbox)
    通过临时文件走统一的 upload_file 接口

    Args:
        content: 要写入的二进制数据。
        remote_path: 沙盒内的目标绝对路径。

    Raises:
        RuntimeError: Docker 容器未初始化时抛出。
    """
    if isinstance(sand_box, DockerSandbox):
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
        return

    fd, tmp_path = tempfile.mkstemp(prefix="atri_upload_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        await sand_box.upload_file(tmp_path, remote_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


async def _collect_generated_files_local(
    run_dir: str,
    ignored_names: set[str],
    max_file_size: int,
    max_total_size: int,
) -> tuple[list[GeneratedFile], str]:
    """本地(no-sandbox)后端的文件收集实现,直接遍历运行目录

    警告文案与 Docker 版保持一致,便于上层统一处理
    """
    warnings: list[str] = []
    candidates: list[tuple[str, str]] = []
    total_size = 0

    if os.path.isdir(run_dir):
        for root, _dirs, files in os.walk(run_dir):
            for name in files:
                if name in ignored_names:
                    continue
                full_path = os.path.join(root, name)
                size = os.path.getsize(full_path)
                if size > max_file_size:
                    warnings.append(
                        f"\n[System Warning] File '{name}' ignored. "
                        f"Size ({size} bytes) exceeds limit ({max_file_size} bytes)."
                    )
                    continue
                candidates.append((full_path, name))
                total_size += size

    if total_size > max_total_size:
        return [], (
            f"\n[System Warning] Generated files ignored. Total size ({total_size} bytes) "
            f"exceeds limit ({max_total_size} bytes)."
        )

    if not candidates:
        return [], "".join(warnings)

    if len(candidates) == 1:
        full_path, filename = candidates[0]
        with open(full_path, "rb") as f:
            content = f.read()
        mime_type, _ = mimetypes.guess_type(filename)
        return [
            GeneratedFile(
                path=filename,
                content=content,
                type=mime_type or "application/octet-stream",
            )
        ], "".join(warnings)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for full_path, filename in candidates:
            zip_file.write(full_path, arcname=filename)

    return [
        GeneratedFile(path="output.zip", content=zip_buffer.getvalue(), type="application/zip")
    ], "".join(warnings)


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
    if not isinstance(sand_box, DockerSandbox):
        return await _collect_generated_files_local(
            run_dir, ignored_names, max_file_size, max_total_size
        )

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
        await _ensure_sandbox_dirs(run_dir)

        for index, file_item in enumerate(files or [], start=1):
            filename, content = await resolve_file_to_bytes(
                file_item,
                default_name=f"input_{index}.bin",
                max_bytes=max_file_size,
            )
            safe_name = _safe_filename(filename)
            remote_file_path = f"{run_dir}/{safe_name}"
            await _upload_bytes_to_sandbox(content=content, remote_path=remote_file_path)
            ignored_names.add(safe_name)

        await _write_script(code, script_path)

        exec_result = await sand_box.run_command(
            f"cd {run_dir} && {_python3_command()} -u {script_name}",
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
            await _cleanup_sandbox_dir(run_dir)

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
    group_id: int | None = None,
    user_id: int | None = None,
    file_segments: list[FileMessageSegment] | None = None,
    timeout: int = 30,
    max_file_size: int = 100 * 1024 * 1024,
    max_total_size: int = 200 * 1024 * 1024,
) -> ExecutionResult:
    """在沙盒中执行 Python 代码

    约束：
    - 输入文件仅接受 `FileMessageSegment` 及其子类。
    - 文件名使用 `segment.file_name`。
    - 文件内容统一通过 `segment.url` 的 HTTPS 地址下载。
    - 任何输入文件相关问题将直接抛出异常。

    Args:
        code: 要执行的 Python 代码字符串。
        group_id: 群号,群聊时用于隔离持久化工作区目录。
        user_id: 用户 QQ 号,私聊(group_id 为 None)时按用户隔离工作区目录。
        file_segments: 输入文件段列表。
        timeout: 执行超时（秒）。
        max_file_size: 单个文件大小限制。
        max_total_size: 生成文件总大小限制。

    Returns:
        ExecutionResult: 包含标准输出、错误输出、退出码及生成文件的对象

    Raises:
        ValueError: 输入文件配置错误（如缺少文件名或非 HTTPS 链接）
    """
    if not sand_box.is_running:
        await sand_box.start()

    data_dir, shared_dir, session_type, session_id = session_dirs(group_id, user_id)
    session_root = f"{sand_box.work_dir}/{'groups' if session_type == 'group' else 'private'}/{session_id}"

    run_id = uuid.uuid4().hex
    session_tmp_base = f"{session_root}/tmp"
    run_dir = f"{session_tmp_base}/run_{run_id}"
    script_name = "main.py"
    script_path = f"{run_dir}/{script_name}"

    ignored_names: set[str] = {script_name}

    try:
        await _ensure_sandbox_dirs(data_dir, shared_dir, run_dir)

        for segment in file_segments or []:
            if not segment.file_name:
                raise ValueError("file_name为空")
            if not segment.url:
                raise ValueError(f"文件 {segment.file_name} 缺少可下载的 url")

            _, content = await resolve_file_to_bytes(
                segment.url, segment.file_name, max_bytes=_COLLECT_MAX_BYTES
            )
            await _upload_bytes_to_sandbox(
                content=content,
                remote_path=f"{run_dir}/{segment.file_name}",
            )
            ignored_names.add(segment.file_name)

        await _write_script(code, script_path)

        env_prefix = (
            f"export GROUP_ID={session_id} "
            f"GROUP_WORKSPACE={data_dir} "
            f"SESSION_TYPE={session_type} "
            f"SESSION_ID={session_id} "
            f"SESSION_WORKSPACE={data_dir} "
            f"SHARED_DIR={shared_dir} && "
        )
        exec_result = await sand_box.run_command(
            f"{env_prefix}cd {run_dir} && {_python3_command()} -u {script_name}",
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
        if run_dir.startswith(session_tmp_base) and "run_" in run_dir:
            await _cleanup_sandbox_dir(run_dir)
