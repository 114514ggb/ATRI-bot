import base64
import os
from urllib.parse import urlparse

from atribot.common_utils.http_client import HTTPClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import File


def _normalize_file_input(file_input: File | str) -> str:
    """标准化文件输入，返回统一格式的源字符串。
    
    将不同类型的文件输入转换为统一的字符串格式，支持 File 对象、文件路径、
    或已经标准化的URI(file://, http://, https://, base64://）。
    
    Args:
        file_input: 文件输入，可以是 File 对象或字符串。
            如果是字符串,可以是本地路径或已标准化的URI。
    
    Returns:
        标准化后的文件源字符串，格式为 file://path, http(s)://url 或 base64://data。
    
    Examples:
        >>> _normalize_file_input("image.jpg")
        'file:///absolute/path/to/image.jpg'
        >>> _normalize_file_input("https://example.com/image.png")
        'https://example.com/image.png'
    """
    if isinstance(file_input, File):
        return file_input.file

    raw = str(file_input)
    if raw.startswith(("file://", "http://", "https://", "base64://")):
        return raw

    if os.path.exists(raw):
        return File.from_local_path(raw).file

    return raw


def _filename_from_source(source: str, default_name: str) -> str:
    """从文件源字符串中提取文件名。
    
    根据不同的文件类型(本地、HTTP、HTTPS)从源字符串中解析出文件名。
    如果无法解析，则返回默认文件名。
    
    Args:
        source: 标准化后的文件源字符串。
        default_name: 当无法从源中提取文件名时的默认名称。
    
    Returns:
        提取的文件名或默认名称。
    
    Examples:
        >>> _filename_from_source("file:///path/to/document.pdf", "default.txt")
        'document.pdf'
        >>> _filename_from_source("https://example.com/image.png?size=large", "default.txt")
        'image.png'
    """
    file_type = File.detect_type(source)

    if file_type == "local":
        local_path = source[len("file://") :]
        return os.path.basename(local_path) or default_name

    if file_type in {"http", "https"}:
        parsed = urlparse(source)
        name = os.path.basename(parsed.path)
        return name or default_name

    return default_name


async def download_binary(url: str, max_bytes: int = 20 * 1024 * 1024) -> bytes:
    """从URL下载二进制数据。
    
    使用 aiohttp 异步下载文件内容，支持超时控制和大小限制。
    
    Args:
        url: 文件下载地址。
        max_bytes: 最大允许下载的字节数，默认20MB。
    
    Returns:
        下载的二进制数据。
    
    Raises:
        ValueError: 下载失败、HTTP状态码错误或文件超过大小限制时抛出。
    
    Examples:
        >>> data = await download_binary("https://example.com/image.jpg")
        >>> len(data)
        1024
    """
    http:HTTPClient = container.get("HTTPClient")
    try:
        return await http.get_bytes(url, max_bytes)
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"下载文件失败: {error}") from error


async def resolve_file_to_bytes(
    file_input: File | str,
    default_name: str,
    max_bytes: int = 20 * 1024 * 1024,
) -> tuple[str, bytes]:
    """将文件输入解析为二进制数据和文件名。
    
    支持多种文件输入类型:本地文件、HTTP/HTTPS URL、Base64编码数据。
    自动处理文件的标准化、下载和解码过程。
    
    Args:
        file_input: 文件输入，可以是 File 对象或字符串。
            支持的格式：
            - File 对象：从对象的 file 属性获取源
            - 本地路径：自动转换为 file:// 格式
            - HTTP/HTTPS URL:直接下载
            - Base64数据:格式为 base64://base64_encoded_data
        default_name: 当无法从源中提取文件名时的默认名称。
        max_bytes: 最大允许的文件大小(字节)默认20MB。
    
    Returns:
        包含文件名和二进制数据的元组 (filename, bytes_data)。
    
    Raises:
        FileNotFoundError: 本地文件不存在时抛出。
        ValueError: 文件类型不支持、格式错误或超过大小限制时抛出。
    
    Examples:
        >>> # 从本地文件读取
        >>> name, data = await resolve_file_to_bytes("image.jpg", "image.jpg")
        >>> 
        >>> # 从URL下载
        >>> name, data = await resolve_file_to_bytes(
        ...     "https://example.com/file.pdf", 
        ...     "document.pdf"
        ... )
        >>> 
        >>> # 从Base64解码
        >>> name, data = await resolve_file_to_bytes(
        ...     "base64://SGVsbG8gV29ybGQ=",
        ...     "message.txt"
        ... )
    """
    source = _normalize_file_input(file_input)
    file_type = File.detect_type(source)
    filename = _filename_from_source(source, default_name)

    if file_type == "local":
        local_path = source[len("file://") :]
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"本地文件不存在: {local_path}")

        size = os.path.getsize(local_path)
        if size > max_bytes:
            raise ValueError(f"本地文件超过大小限制 ({max_bytes} bytes)")

        with open(local_path, "rb") as file_obj:
            return filename, file_obj.read()

    if file_type in {"http", "https"}:
        return filename, await download_binary(source, max_bytes=max_bytes)

    if file_type == "base64":
        try:
            content = base64.b64decode(source[len("base64://") :], validate=True)
        except Exception as error:
            raise ValueError("base64 文件格式错误") from error

        if len(content) > max_bytes:
            raise ValueError(f"base64 文件超过大小限制 ({max_bytes} bytes)")

        return filename, content

    raise ValueError("不支持的文件输入类型，请使用 file://, http(s):// 或 base64://")
