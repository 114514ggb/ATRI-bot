import base64
import os
from urllib.parse import urlparse

from atribot.common_utils.http_client import HTTPClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import File


async def download_binary(url: str, max_bytes: int = 20 * 1024 * 1024) -> bytes:
    """从 URL 下载二进制数据

    Args:
        url: 文件下载地址
        max_bytes: 最大允许字节数，默认 20MB

    Returns:
        下载的二进制数据

    Raises:
        ValueError: 下载失败、HTTP 状态码错误或超过大小限制时抛出
    """
    http: HTTPClient = container.get("HTTPClient")
    try:
        return await http.get_bytes(url, max_bytes)
    except Exception as error:
        raise ValueError(f"下载文件失败: {error}") from error


async def resolve_file_to_bytes(
    file_input: File | str,
    default_name: str,
    max_bytes: int = 20 * 1024 * 1024,
) -> tuple[str, bytes]:
    """将文件输入解析为 (文件名, 二进制数据)，支持本地路径/HTTP/HTTPS/base64

    Args:
        file_input: File 对象或字符串(本地路径或已标准化 URI)
        default_name: 无法从源中提取文件名时的默认名
        max_bytes: 最大允许字节数，默认 20MB

    Returns:
        (文件名, 二进制数据) 元组

    Raises:
        FileNotFoundError: 本地文件不存在
        ValueError: 类型不支持、格式错误或超过大小限制
    """
    source = file_input.file if isinstance(file_input, File) else str(file_input)
    if not isinstance(file_input, File) and os.path.exists(source):
        source = File.from_local_path(source).file

    file_type = File.detect_type(source)

    if file_type == "local":
        local_path = source[len("file://") :]
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"本地文件不存在: {local_path}")

        size = os.path.getsize(local_path)
        if size > max_bytes:
            raise ValueError(f"本地文件超过大小限制 ({max_bytes} bytes)")

        with open(local_path, "rb") as file_obj:
            return os.path.basename(local_path) or default_name, file_obj.read()

    if file_type in {"http", "https"}:
        name = os.path.basename(urlparse(source).path) or default_name
        return name, await download_binary(source, max_bytes=max_bytes)

    if file_type == "base64":
        try:
            content = base64.b64decode(source[len("base64://") :], validate=True)
        except Exception as error:
            raise ValueError("base64 文件格式错误") from error

        if len(content) > max_bytes:
            raise ValueError(f"base64 文件超过大小限制 ({max_bytes} bytes)")

        return default_name, content

    raise ValueError("不支持的文件输入类型，请使用 file://, http(s):// 或 base64://")
