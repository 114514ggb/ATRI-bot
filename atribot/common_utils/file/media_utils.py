import asyncio
import base64
import os
import shutil
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from atribot.common_utils.file.file_utils import resolve_file_to_bytes
from atribot.common_utils.file.media_cache import (
    _get_lock,
    cache_get,
    cache_put,
    make_cache_key,
)
from atribot.core.type.chat_message_types import File

AUDIO_MAX_BYTES = 10 * 1024 * 1024   # 10MB
VIDEO_MAX_BYTES = 50 * 1024 * 1024   # 50MB
AUDIO_BITRATE = "128k"               # 音频统一转码码率
VIDEO_CRF = 28                       # 视频统一转码质量(CRF, 越小越清晰)
VIDEO_AUDIO_BITRATE = "128k"         # 视频中音轨码率
TRANSCODE_TIMEOUT = 60.0             # ffmpeg 转码超时(秒)

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


def _source_str(source: str | File) -> str:
    """从统一来源参数中提取源字符串"""
    return source.file if isinstance(source, File) else str(source)


async def url_to_audio_base64(
    source: str | File,
    file_name: str | None = None,
    max_bytes: int = AUDIO_MAX_BYTES,
) -> tuple[str, str]:
    """下载音频并编码为 base64 字符串

    支持 http(s)://、file://、base64:// 以及本地路径等来源

    Args:
        source: 音频来源，可以是 File 对象或字符串(http/https/file/base64 或本地路径)
        file_name: 可选文件名，用于推断音频格式
        max_bytes: 最大允许下载的字节数，默认 10MB

    Returns:
        ``(base64_data, format_str)`` 元组：
        - base64_data: 不带前缀的 base64 编码字符串
        - format_str: 音频格式，如 ``'mp3'``、``'ogg'``、``'wav'`` 等

    Raises:
        ValueError: 下载失败或文件超过大小限制时抛出
    """
    name, data = await resolve_file_to_bytes(source, file_name or "audio", max_bytes=max_bytes)
    return base64.b64encode(data).decode(), _detect_audio_format(_source_str(source), file_name or name)


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
    source: str | File,
    file_name: str | None = None,
    max_bytes: int = VIDEO_MAX_BYTES,
) -> tuple[str, str]:
    """下载视频并编码为 base64 字符串

    QQ CDN 等临时签名 URL 模型侧无法直接访问，应在 Bot 端下载后传 base64
    支持 http(s)://、file://、base64:// 以及本地路径等来源

    Args:
        source: 视频来源，可以是 File 对象或字符串(http/https/file/base64 或本地路径)
        file_name: 可选文件名，用于推断 MIME 类型
        max_bytes: 最大允许下载的字节数，默认 50MB

    Returns:
        ``(base64_data, mime_type)`` 元组：
        - base64_data: 不带前缀的 base64 编码字符串
        - mime_type: 视频 MIME 类型，如 ``'video/mp4'``

    Raises:
        ValueError: 下载失败或文件超过大小限制时抛出
    """
    name, data = await resolve_file_to_bytes(source, file_name or "video", max_bytes=max_bytes)
    mime = _detect_video_mime(_source_str(source), file_name or name)
    return base64.b64encode(data).decode(), mime


@dataclass(frozen=True)
class MediaConvertResult:
    """统一媒体转换结果

    Attributes:
        data: 纯 base64 编码字符串(不含前缀)
        fmt: 格式标识：音频为 'mp3'/'ogg'/'wav' 等，图片/视频为 MIME(如 'image/jpeg'/'video/mp4')
        mime: 完整 MIME 类型(如 'audio/mp3'、'image/jpeg'、'video/mp4')
        converted: 是否成功转换/压缩为目标格式(True=成功, False=保持原始格式)
    """
    data: str
    fmt: str
    mime: str
    converted: bool

    @property
    def data_uri(self) -> str:
        """带 MIME 前缀的完整 data URI"""
        return f"data:{self.mime};base64,{self.data}"


@lru_cache(maxsize=1)
def _ffmpeg_path() -> str | None:
    """返回 ffmpeg 可执行文件路径；未安装返回 None(结果缓存,避免重复探测)"""
    return shutil.which("ffmpeg")


async def _run_ffmpeg(
    args: list[str],
    *,
    timeout: float = TRANSCODE_TIMEOUT,
) -> bool:
    """异步执行 ffmpeg,正常退出返回 True,否则返回 False"""
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.wait(), timeout=timeout)
        return process.returncode == 0
    except (asyncio.TimeoutError, OSError, ValueError):
        return False


async def _ffmpeg_transcode(
    data: bytes,
    input_suffix: str,
    output_suffix: str,
    build_args: Callable[[str], list[str]],
    *,
    timeout: float = TRANSCODE_TIMEOUT,
) -> bytes | None:
    """通用 ffmpeg 转码流程：写临时文件→执行→读回→清理失败返回 None

    Args:
        data: 原始媒体字节数据
        input_suffix: 输入临时文件后缀(如 '.ogg')
        output_suffix: 输出临时文件后缀(如 '.mp3')
        build_args: 接收输出路径并返回 ffmpeg 参数列表(不含 ffmpeg/-y/-i)的构建函数
        timeout: 转码超时秒数

    Returns:
        转码后的字节数据；未安装 ffmpeg 或转码失败返回 None
    """
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        return None

    input_path = output_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=input_suffix, delete=False) as file_obj:
            file_obj.write(data)
            input_path = file_obj.name
        output_path = input_path + output_suffix

        args = [ffmpeg, "-y", "-i", input_path, *build_args(output_path)]
        if not await _run_ffmpeg(args, timeout=timeout):
            return None

        with open(output_path, "rb") as file_obj:
            return file_obj.read()
    except Exception:
        return None
    finally:
        for path in (input_path, output_path):
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass


async def transcode_audio_to_mp3(
    data: bytes,
    *,
    bitrate: str = AUDIO_BITRATE,
    input_suffix: str = ".audio",
    timeout: float = TRANSCODE_TIMEOUT,
) -> bytes | None:
    """将音频字节转码为 mp3(依赖 ffmpeg)，失败或未安装 ffmpeg 时返回 None

    Args:
        data: 原始音频字节数据
        bitrate: 目标码率，如 '128k'
        input_suffix: 输入临时文件后缀(便于 ffmpeg 识别格式)
        timeout: 转码超时秒数

    Returns:
        转码后的 mp3 字节数据；失败返回 None
    """

    def build_args(output_path: str) -> list[str]:
        return [
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", bitrate,
            "-ar", "44100",
            "-ac", "2",
            output_path,
        ]

    return await _ffmpeg_transcode(data, input_suffix, ".mp3", build_args, timeout=timeout)


async def transcode_video_to_mp4(
    data: bytes,
    *,
    crf: int = VIDEO_CRF,
    audio_bitrate: str = VIDEO_AUDIO_BITRATE,
    max_dimension: int | None = None,
    input_suffix: str = ".video",
    timeout: float = TRANSCODE_TIMEOUT,
) -> bytes | None:
    """将视频字节转码为 mp4(H.264/AAC,依赖 ffmpeg)，失败或未安装 ffmpeg 时返回 None

    Args:
        data: 原始视频字节数据
        crf: 质量参数(0-51,越小越清晰)
        audio_bitrate: 音轨码率
        max_dimension: 限制视频最长边像素(按比例缩放),None 不缩放
        input_suffix: 输入临时文件后缀
        timeout: 转码超时秒数

    Returns:
        转码后的 mp4 字节数据；失败返回 None
    """

    def build_args(output_path: str) -> list[str]:
        args: list[str] = []
        if max_dimension:
            args += ["-vf", f"scale='min({max_dimension},iw)':'-2'"]
        args += [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(crf),
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            "-movflags", "+faststart",
            output_path,
        ]
        return args

    return await _ffmpeg_transcode(data, input_suffix, ".mp4", build_args, timeout=timeout)


async def url_to_audio_mp3(
    source: str | File,
    file_name: str | None = None,
    *,
    max_bytes: int = AUDIO_MAX_BYTES,
    bitrate: str = AUDIO_BITRATE,
) -> MediaConvertResult:
    """下载音频并统一转换为 mp3 base64(统一格式入口)

    回退链：
    - 下载失败 -> 抛出异常(调用方捕获后回退 URL 或文本描述)
    - ffmpeg 转码成功 → ``converted=True`` 的 ``audio/mp3`` 结果
    - 转码失败(未安装 ffmpeg 等) → 保持原始格式 base64,``converted=False``

    Args:
        source: 音频来源(http/https/file/base64 或本地路径)
        file_name: 可选文件名，用于推断格式
        max_bytes: 最大允许下载字节数，默认 10MB
        bitrate: mp3 目标码率

    Returns:
        MediaConvertResult

    Raises:
        Exception: 下载失败时抛出
    """
    src = _source_str(source)
    key = make_cache_key("audio", src, file_name, f"mb={max_bytes};br={bitrate}")

    async with _get_lock(key):
        entry = await cache_get(key)
        if entry is not None:
            return MediaConvertResult(
                data=entry.to_base64(),
                fmt=entry.fmt,
                mime=entry.mime,
                converted=entry.converted,
            )

        name, data = await resolve_file_to_bytes(source, file_name or "audio", max_bytes=max_bytes)

        fmt = _detect_audio_format(src, file_name or name)
        cache_bytes: bytes = data
        if converted := await transcode_audio_to_mp3(data, bitrate=bitrate, input_suffix=f".{fmt}"):
            result = MediaConvertResult(
                data=base64.b64encode(converted).decode(),
                fmt="mp3",
                mime="audio/mp3",
                converted=True,
            )
            cache_bytes = converted
        else:
            result = MediaConvertResult(
                data=base64.b64encode(data).decode(),
                fmt=fmt,
                mime=f"audio/{fmt}",
                converted=False,
            )

        await cache_put(key, cache_bytes, result.fmt, result.mime, result.converted)
        return result


async def url_to_video_mp4(
    source: str | File,
    file_name: str | None = None,
    *,
    max_bytes: int = VIDEO_MAX_BYTES,
    crf: int = VIDEO_CRF,
    max_dimension: int | None = None,
) -> MediaConvertResult:
    """下载视频并统一转换为 mp4 base64(统一格式入口)

    回退链：
    - 下载失败 -> 抛出异常(调用方捕获后回退 URL)
    - ffmpeg 转码成功 → ``converted=True`` 的 ``video/mp4`` 结果
    - 转码失败(未安装 ffmpeg 等) → 保持原始格式 base64,``converted=False``

    Args:
        source: 视频来源(http/https/file/base64 或本地路径)
        file_name: 可选文件名，用于推断格式
        max_bytes: 最大允许下载字节数，默认 50MB
        crf: 转码质量参数
        max_dimension: 限制视频最长边像素,None 不缩放

    Returns:
        MediaConvertResult

    Raises:
        Exception: 下载失败时抛出
    """
    src = _source_str(source)
    key = make_cache_key("video", src, file_name, f"mb={max_bytes};crf={crf};dim={max_dimension}")

    async with _get_lock(key):
        entry = await cache_get(key)
        if entry is not None:
            return MediaConvertResult(
                data=entry.to_base64(),
                fmt=entry.fmt,
                mime=entry.mime,
                converted=entry.converted,
            )

        name, data = await resolve_file_to_bytes(source, file_name or "video", max_bytes=max_bytes)

        mime = _detect_video_mime(src, file_name or name)
        cache_bytes: bytes = data
        if converted := await transcode_video_to_mp4(
            data,
            crf=crf,
            max_dimension=max_dimension,
            input_suffix=f".{mime.split('/')[-1]}",
        ):
            result = MediaConvertResult(
                data=base64.b64encode(converted).decode(),
                fmt="mp4",
                mime="video/mp4",
                converted=True,
            )
            cache_bytes = converted
        else:
            result = MediaConvertResult(
                data=base64.b64encode(data).decode(),
                fmt=mime,
                mime=mime,
                converted=False,
            )

        await cache_put(key, cache_bytes, result.fmt, result.mime, result.converted)
        return result
