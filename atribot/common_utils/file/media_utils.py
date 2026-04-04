import base64

from atribot.common_utils.http_client import HTTPClient
from atribot.core.service_container import container

AUDIO_MAX_BYTES = 10 * 1024 * 1024   # 10MB
VIDEO_MAX_BYTES = 50 * 1024 * 1024   # 50MB

_AUDIO_FORMAT_MAP: dict[str, str] = {
    "mp3": "mp3",
    "ogg": "ogg",
    "wav": "wav",
    "flac": "flac",
    "aac": "aac",
    "m4a": "mp4",
    "silk": "ogg",
    "amr": "ogg",
    "opus": "ogg",
}


def _detect_audio_format(url: str, file_name: str | None = None) -> str:
    """从 URL 或文件名推断音频格式，无法识别时默认返回 'mp3'"""
    name = file_name or url.split("?")[0]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return _AUDIO_FORMAT_MAP.get(ext, "mp3")


async def url_to_audio_base64(
    url: str,
    file_name: str | None = None,
    max_bytes: int = AUDIO_MAX_BYTES,
) -> tuple[str, str]:
    """下载音频 URL 并编码为 base64 字符串。

    Args:
        url: 音频文件的网络地址。
        file_name: 可选文件名，用于推断音频格式。
        max_bytes: 最大允许下载的字节数，默认 10MB。

    Returns:
        ``(base64_data, format_str)`` 元组：
        - base64_data: 不带前缀的 base64 编码字符串。
        - format_str: 音频格式，如 ``'mp3'``、``'ogg'``、``'wav'`` 等。

    Raises:
        ValueError: 下载失败或文件超过大小限制时抛出。
    """
    http: HTTPClient = container.get("HTTPClient")
    data = await http.get_bytes(url, max_bytes)
    return base64.b64encode(data).decode(), _detect_audio_format(url, file_name)


_VIDEO_MIME_MAP: dict[str, str] = {
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
    "avi": "video/avi",
    "flv": "video/x-flv",
    "mkv": "video/x-matroska",
    "m4v": "video/mp4",
}


def _detect_video_mime(url: str, file_name: str | None = None) -> str:
    """从 URL 或文件名推断视频 MIME 类型，无法识别时默认返回 'video/mp4'"""
    name = file_name or url.split("?")[0]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return _VIDEO_MIME_MAP.get(ext, "video/mp4")


async def url_to_video_base64(
    url: str,
    file_name: str | None = None,
    max_bytes: int = VIDEO_MAX_BYTES,
) -> tuple[str, str]:
    """下载视频 URL 并编码为 base64 字符串。

    QQ CDN 等临时签名 URL 模型侧无法直接访问，应在 Bot 端下载后传 base64。

    Args:
        url: 视频文件的网络地址。
        file_name: 可选文件名，用于推断 MIME 类型。
        max_bytes: 最大允许下载的字节数，默认 50MB。

    Returns:
        ``(base64_data, mime_type)`` 元组：
        - base64_data: 不带前缀的 base64 编码字符串。
        - mime_type: 视频 MIME 类型，如 ``'video/mp4'``。

    Raises:
        ValueError: 下载失败或文件超过大小限制时抛出。
    """
    http: HTTPClient = container.get("HTTPClient")
    data = await http.get_bytes(url, max_bytes)
    mime = _detect_video_mime(url, file_name)
    return base64.b64encode(data).decode(), mime
