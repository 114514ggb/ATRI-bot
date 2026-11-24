import asyncio
import base64
import io
from logging import Logger

import aiohttp
from PIL import Image

from atribot.common_utils.file.file_utils import resolve_file_to_bytes
from atribot.common_utils.file.media_cache import make_cache_key
from atribot.common_utils.file.media_utils import (
    MediaConvertResult,
    _load_with_cache,
    _source_str,
)
from atribot.common_utils.http_client import HTTPClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import File, to_int

_MAX_DOWNLOAD_RETRIES: int = 2
IMAGE_MAX_BYTES = 30 * 1024 * 1024
IMAGE_MAX_SIDE: int = 2048
"""送给模型前图片最长边上限(px)，超出按比例缩小，不裁剪"""

_INCOMPLETE_KEYWORDS: tuple[str, ...] = (
    "truncated",
    "不完整",
    "incomplete",
    "content-length",
)
"""命中这些关键字的错误视为下载/解码不完整，值得重试"""

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_IEND = b"IEND\xaeB`\x82"
_JPEG_EOI = b"\xff\xd9"
_TRAILING_TOLERANCE = 64 * 1024
"""允许在文件末尾该字节范围内命中结束标记(容忍尾部附加的元数据)"""


def _assert_image_complete(data: bytes) -> None:
    """按容器结构校验图片数据是否完整

    Args:
        data: 原始图片字节

    Raises:
        OSError: 已知格式(JPEG/PNG/GIF/WebP/BMP)的尾部结构不完整
    """
    if not data:
        raise OSError("图片数据不完整(truncated): 空数据")

    if data[:2] == b"\xff\xd8":
        index = data.rfind(_JPEG_EOI)
        if index == -1 or index < len(data) - _TRAILING_TOLERANCE:
            raise OSError("图片数据不完整(truncated): JPEG 缺少结束标记 EOI")
        return

    if data[:8] == _PNG_SIGNATURE:
        index = data.rfind(_PNG_IEND)
        if index == -1 or index < len(data) - _TRAILING_TOLERANCE:
            raise OSError("图片数据不完整(truncated): PNG 缺少 IEND 块")
        return

    if data[:6] in (b"GIF87a", b"GIF89a"):
        if not data.rstrip(b"\x00").endswith(b"\x3b"):
            raise OSError("图片数据不完整(truncated): GIF 缺少结束标记")
        return

    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if int.from_bytes(data[4:8], "little") + 8 > len(data):
            raise OSError("图片数据不完整(truncated): WebP RIFF 长度不足")
        return

    if data[:2] == b"BM" and len(data) >= 6:
        if int.from_bytes(data[2:6], "little") > len(data):
            raise OSError("图片数据不完整(truncated): BMP 声明长度不足")


def convert_to_jpeg(
    image_bytes: bytes,
    max_size_kb: int | None = None,
    background: tuple[int, int, int] = (255, 255, 255),
    *,
    max_side: int | None = IMAGE_MAX_SIDE,
) -> bytes:
    """
    将任意图片字节强制统一转码为标准 JPEG(含动画 GIF 取首帧)

    特性:
    - 动画(GIF/WebP 多帧)取第一帧转静态图
    - RGBA/LA/P 等带透明通道的图片合成到指定背景色(默认白底),避免转 RGB 变黑
    - 解码失败(数据损坏/截断/非图片)抛出异常,供调用方捕获处理
    - 解码前先做容器级完整性校验(见 ``_assert_image_complete``),截断图抛
      ``OSError('truncated')``,不会被静默灰色填充
    - max_side 限制最长边:超出时按原比例缩小,不裁剪
    - max_size_kb 限制输出体积:先降画质(90→20),仍超限则等比例缩小尺寸并固定画质 20

    注意:不修改 ``ImageFile.LOAD_TRUNCATED_IMAGES`` 全局标志 —— 转码运行在
    ``asyncio.to_thread`` 线程池中，多个会话并发时全局标志会被其他线程还原，
    导致截断图被宽容解码成灰色填充。PIL 默认即严格解码，无需改动。

    Args:
        image_bytes: 原始图片字节数据
        max_size_kb: 目标体积上限(KB);None 表示不限制(仍会统一转 JPEG)
        background: 透明区域合成背景色,默认白色 (255, 255, 255)
        max_side: 最长边上限(px);None/0 表示不限制

    Returns:
        标准 JPEG 字节

    Raises:
        Exception: 图片解码/编码失败时抛出(PIL 异常等),含截断图抛 OSError
    """
    _assert_image_complete(image_bytes)

    with Image.open(io.BytesIO(image_bytes)) as opened:
        opened.load()

        if getattr(opened, "is_animated", False):
            opened.seek(0)
            opened.load()

        image = _flatten_to_rgb(opened, background)

    if max_side and max_side > 0 and max(image.size) > max_side:
        ratio = max_side / max(image.size)
        image = image.resize(
            (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
            Image.Resampling.LANCZOS,
        )

    max_size_bytes = float("inf") if max_size_kb is None else max_size_kb * 1024
    quality = 90
    scale = 1.0
    last_bytes: bytes | None = None

    while True:
        out = io.BytesIO()

        if quality >= 20:
            image.save(out, format="JPEG", quality=quality)
            quality -= 10
        else:
            scale *= 0.8
            new_width = int(image.width * scale)
            new_height = int(image.height * scale)

            if new_width < 10 or new_height < 10:
                break

            temp_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            temp_image.save(out, format="JPEG", quality=20)

        last_bytes = out.getvalue()
        if len(last_bytes) <= max_size_bytes:
            return last_bytes

    if last_bytes is None:
        raise ValueError("图片压缩失败: 无法生成有效 JPEG")

    return last_bytes


def _flatten_to_rgb(
    image: Image.Image,
    background: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """将任意模式的图片转为 RGB,透明区域合成到指定背景色(默认白底)"""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        bg = Image.new("RGB", rgba.size, background)
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg

    return image.convert("RGB")


def compress_image(
    image_bytes: bytes,
    max_size_kb: int,
    max_side: int | None = IMAGE_MAX_SIDE,
) -> bytes:
    """
    压缩图片到指定大小以内(包含画质降低和尺寸缩放两种策略)

    注意:自 v2 起,压缩前会统一将任意格式(含动画 GIF 取首帧)转码为标准 JPEG,
    不再透传原始格式。此函数为 ``convert_to_jpeg`` 的兼容封装:
    - 任何失败(截断/损坏/无法压缩)均向上抛出，**不再回退返回原始字节**，
      避免 PNG 等非 JPEG 内容被当成"转码成功"写入缓存

    Args:
        image_bytes: 原始图片的字节数据
        max_size_kb: 目标大小上限,单位KB
        max_side: 最长边上限(px);None/0 表示不限制

    Returns:
        bytes: 压缩转码后的 JPEG 字节

    Raises:
        Exception: 转码失败时抛出(截断图抛 OSError)
    """
    return convert_to_jpeg(image_bytes, max_size_kb=max_size_kb, max_side=max_side)


def _ensure_download_complete(resp: aiohttp.ClientResponse, content: bytes) -> None:
    """校验下载完整性: 未压缩传输(无 Content-Encoding)且 Content-Length 与实际不符,判为截断

    若响应经过 gzip/br 等压缩,Content-Length 为压缩长度,与 ``resp.read()`` 解压后长度
    不相等属正常,故仅在无 Content-Encoding 时比对,避免误判

    Raises:
        ValueError: 下载内容与声明长度不一致(截断)
    """
    clen = resp.headers.get("Content-Length")
    if clen and not resp.headers.get("Content-Encoding"):
        try:
            expected = int(clen)
        except (TypeError, ValueError):
            return
        if len(content) != expected:
            raise ValueError(
                f"下载不完整: Content-Length={clen} 实际={len(content)} bytes"
            )


async def urls_list_to_base64(
    urls: list[str],
    prefix: str = "data:image/jpeg;base64,",
    concurrency: int = 5,
    max_size_kb: int | None = 1024,
) -> list[str]:
    """并发下载一组图片 URL 并压缩为 base64

    Args:
        urls: 图片 URL 列表
        prefix: base64 前缀,默认 JPEG data URI
        concurrency: 最大并发数
        max_size_kb: 压缩后体积上限(KB),None 不压缩

    Returns:
        base64 字符串列表,顺序与输入一致,失败项为空串
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch(url: str) -> str:
        async with semaphore:
            return await url_to_base64(url, prefix=prefix, max_size_kb=max_size_kb)

    return await asyncio.gather(*(fetch(url) for url in urls))


async def url_to_base64(
    url: str,
    prefix: str = "data:image/jpeg;base64,",
    max_size_kb: int | None = 1024,
) -> str:
    """
    下载单张图片并压缩,返回对应的base64字符串
    
    使用 aiohttp 实现图片下载,下载后的图片会根据指定的体积限制进行压缩
    
    Args:
        url: 图片URL地址
        prefix: Base64字符串的前缀,默认为JPEG格式的数据URI前缀
        max_size_kb: 图片最大体积限制,单位KB设为 None 表示不压缩
                    默认值为 1024KB (1MB)
    
    Returns:
        str: 图片的base64字符串如果下载失败,返回空字符串
    
    Examples:
        >>> url = 'https://example.com/image.jpg'
        >>> result = await url_to_base64(url, max_size_kb=500)
        >>> if result:
        ...     print(f'图片转换成功: {result[:50]}...')
    
    Raises:
        此方法不会抛出异常,所有异常都会被捕获并记录,
        失败时返回空字符串
    """
    try:
        http = container.get_by_type(HTTPClient)
        async with http.session.get(
            url=url,
            headers={
                "User-Agent": "QQ/9.9.21-39038 CFNetwork/1220.1 Darwin/20.3.0",
                "Accept": "image/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
        ) as resp:
            if resp.status != 200:
                return ""

            content = await resp.read()
            if len(content) == 0:
                return ""

            _ensure_download_complete(resp, content)

            if max_size_kb is not None:
                content = await asyncio.to_thread(compress_image, content, max_size_kb)

            return f"{prefix}{base64.b64encode(content).decode('utf-8')}"
    except Exception as error:
        print(f"下载失败 {url}: {error}")
        return ""


async def url_to_image_jpeg(
    source: str | File,
    *,
    max_size_kb: int | None = 2048,
    max_bytes: int = IMAGE_MAX_BYTES,
    file_name: str | None = None,
    max_side: int | None = IMAGE_MAX_SIDE,
    expected_size: int | str | None = None,
) -> MediaConvertResult:
    """下载图片并统一转换为 JPEG base64

    Args:
        source: 图片来源(File 或字符串)
        max_size_kb: 压缩后体积上限(KB),None 不限制(仍转 JPEG)
        max_bytes: 最大下载字节数,默认 30MB
        file_name: 文件名(QQ 媒体为内容哈希),作为缓存键
        max_side: 最长边上限(px),超出等比例缩小;None/0 不限制
        expected_size: 消息声明的原始字节数(仅用于不一致时告警,不作为失败依据);可为字符串

    Returns:
        MediaConvertResult

    Raises:
        Exception: 下载失败或图片损坏/截断时抛出,且不入缓存
    """
    src = _source_str(source)
    declared_size = to_int(expected_size)
    key = make_cache_key(
        "image", src, file_name, f"kb={max_size_kb};side={max_side}"
    )
    try:
        logger: Logger | None = container.get_by_type(Logger).getChild("ImageUtils")
    except Exception:
        # 工具/测试场景下容器可能未初始化，降级为不记日志
        logger = None

    def validate_cached_jpeg(data: bytes) -> None:
        """缓存命中的字节必须是完整 JPEG(清掉历史坏条目)"""
        _assert_image_complete(data)
        if data[:2] != b"\xff\xd8":
            raise ValueError("缓存图片不是 JPEG")

    async def produce() -> tuple[bytes, MediaConvertResult]:
        for attempt in range(_MAX_DOWNLOAD_RETRIES + 1):
            try:
                _, data = await resolve_file_to_bytes(
                    source, "image", max_bytes=max_bytes
                )
                if declared_size and len(data) != declared_size and logger:
                    logger.warning(
                        "图片下载字节数与消息声明不一致(声明=%s 实际=%s): %s",
                        declared_size,
                        len(data),
                        src,
                    )
                jpeg = await asyncio.to_thread(
                    convert_to_jpeg, data, max_size_kb, max_side=max_side
                )
            except (OSError, ValueError) as exc:
                # 仅对"下载/解码不完整"重试,其余失败直接抛出且不入缓存
                if attempt < _MAX_DOWNLOAD_RETRIES and any(
                    keyword in str(exc).lower() for keyword in _INCOMPLETE_KEYWORDS
                ):
                    if logger:
                        logger.warning("图片不完整,重试下载(%d): %s", attempt + 1, exc)
                    await asyncio.sleep(0.5)
                    continue
                raise
            return jpeg, MediaConvertResult(
                data=base64.b64encode(jpeg).decode(),
                fmt="jpeg",
                mime="image/jpeg",
                converted=True,
            )
        raise AssertionError("unreachable")  # pragma: no cover

    return await _load_with_cache(key, produce, validator=validate_cached_jpeg)
