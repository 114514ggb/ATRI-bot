import asyncio
import base64
import io

import aiohttp
from PIL import Image, ImageFile

from atribot.common_utils.file.file_utils import resolve_file_to_bytes
from atribot.common_utils.file.media_cache import (
    _get_lock,
    cache_get,
    cache_put,
    make_cache_key,
)
from atribot.common_utils.file.media_utils import MediaConvertResult
from atribot.common_utils.http_client import HTTPClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import File

ImageFile.LOAD_TRUNCATED_IMAGES = True

_MAX_DOWNLOAD_RETRIES: int = 2


def convert_to_jpeg(
    image_bytes: bytes,
    max_size_kb: int | None = None,
    background: tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    """
    将任意图片字节强制统一转码为标准 JPEG(含动画 GIF 取首帧)。

    特性:
    - 动画(GIF/WebP 多帧)取第一帧转静态图
    - RGBA/LA/P 等带透明通道的图片合成到指定背景色(默认白底),避免转 RGB 变黑
    - 解码失败(数据损坏/截断/非图片)抛出异常,供调用方捕获处理
    - max_size_kb 限制输出体积:先降画质(90→20),仍超限则等比例缩小尺寸并固定画质 20

    Args:
        image_bytes: 原始图片字节数据
        max_size_kb: 目标体积上限(KB);None 表示不限制(仍会统一转 JPEG)
        background: 透明区域合成背景色,默认白色 (255, 255, 255)

    Returns:
        标准 JPEG 字节

    Raises:
        Exception: 图片解码/编码失败时抛出(PIL 异常等)
    """
    image = Image.open(io.BytesIO(image_bytes))
    image.load()

    if getattr(image, "is_animated", False):
        image.seek(0)
        image.load()

    image = _flatten_to_rgb(image, background)

    if max_size_kb is None:
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=90)
        return out.getvalue()

    max_size_bytes = max_size_kb * 1024
    quality = 90
    scale = 1.0

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

        if out.tell() <= max_size_bytes:
            return out.getvalue()

    return out.getvalue()


def _flatten_to_rgb(
    image: Image.Image,
    background: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """将任意模式的图片转为 RGB,透明区域合成到指定背景色(默认白底)"""
    if image.mode in ("RGBA", "LA"):
        rgba = image.convert("RGBA")
        bg = Image.new("RGB", rgba.size, background)
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg

    if image.mode == "P":
        if "transparency" in image.info:
            rgba = image.convert("RGBA")
            bg = Image.new("RGB", rgba.size, background)
            bg.paste(rgba, mask=rgba.split()[-1])
            return bg
        return image.convert("RGB")

    return image.convert("RGB")


def compress_image(image_bytes: bytes, max_size_kb: int) -> bytes:
    """
    压缩图片到指定大小以内(包含画质降低和尺寸缩放两种策略)

    注意:自 v2 起,压缩前会统一将任意格式(含动画 GIF 取首帧)转码为标准 JPEG,
    不再透传原始格式。此函数为 ``convert_to_jpeg`` 的兼容封装,
    转码失败时回退返回原始字节。

    Args:
        image_bytes: 原始图片的字节数据
        max_size_kb: 目标大小上限,单位KB

    Returns:
        bytes: 压缩转码后的 JPEG 字节;若转换失败返回原始数据
    """
    try:
        return convert_to_jpeg(image_bytes, max_size_kb=max_size_kb)
    except Exception:
        return image_bytes


async def urls_list_to_base64(
    urls: list[str],
    prefix: str = "data:image/jpeg;base64,",
    concurrency: int = 5,
    max_size_kb: int | None = 1024,
) -> list[str]:
    """
    并发下载一组图片 URL 并压缩，返回对应的 base64 字符串列表
    
    使用 aiohttp 实现并发下载，通过信号量控制并发数量
    下载后的图片会根据指定的体积限制进行压缩
    
    Args:
        urls: 图片URL地址列表
        prefix: Base64字符串的前缀,默认为JPEG格式的数据URI前缀
        concurrency: 最大并发下载数量,默认为5
        max_size_kb: 图片最大体积限制,单位KB设为 None 表示不压缩
                    默认值为 1024KB (1MB)
    
    Returns:
        List[str]: 与输入顺序一致的base64字符串列表
                如果某个URL下载失败,对应的位置会返回空字符串
    
    Examples:
        >>> urls = ['https://example.com/image1.jpg', 'https://example.com/image2.jpg']
        >>> results = await urls_to_base64(urls, max_size_kb=500)
        >>> for i, base64_str in enumerate(results):
        ...     if base64_str:
        ...         print(f'图片{i+1}转换成功')
    
    Raises:
        Exception: 此方法不会抛出异常，所有异常都会被捕获并记录，
                失败的URL对应位置返回空字符串
    """
    semaphore = asyncio.Semaphore(concurrency)
    session:aiohttp.ClientSession = container.get("HTTPClient").session

    async def fetch(url: str) -> str:
        async with semaphore:
            try:
                async with session.get(
                    url,
                    headers={"Accept": "image/*;q=0.8"},
                ) as resp:
                    if resp.status != 200:
                        return ""

                    content = await resp.read()
                    if len(content) == 0:
                        return ""

                    if max_size_kb is not None:
                        content = await asyncio.to_thread(compress_image, content, max_size_kb)

                    return f"{prefix}{base64.b64encode(content).decode('utf-8')}"
            except Exception as error:
                print(f"下载失败 {url}: {error}")
                return ""

    return await asyncio.gather(*(fetch(url) for url in urls))


async def url_to_base64(
    url: str,
    prefix: str = "data:image/jpeg;base64,",
    max_size_kb: int | None = 1024,
) -> str:
    """
    下载单张图片并压缩,返回对应的base64字符串
    
    使用 aiohttp 实现图片下载，下载后的图片会根据指定的体积限制进行压缩
    
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
        此方法不会抛出异常，所有异常都会被捕获并记录，
        失败时返回空字符串
    """
    try:
        http:HTTPClient = container.get("HTTPClient")
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
    max_bytes: int = 10 * 1024 * 1024,
    file_name: str | None = None,
) -> MediaConvertResult:
    """下载图片并统一转换为 JPEG base64(统一格式入口)

    支持 http(s)://、file://、base64:// 以及本地路径等来源，
    下载后通过 ``convert_to_jpeg`` 强制转码为标准 JPEG(动画 GIF 取首帧)。
    转换结果按 file_name(或来源)磁盘缓存，命中时跳过下载与压缩。

    Args:
        source: 图片来源(File 对象或字符串)
        max_size_kb: 压缩后最大体积(KB),None 表示不限制体积(仍统一转 JPEG)
        max_bytes: 最大允许下载字节数，默认 10MB
        file_name: 文件名(QQ 媒体为内容哈希),作为缓存键;None 时回退来源标识

    Returns:
        转换成功返回 MediaConvertResult(data, "jpeg", "image/jpeg", True)

    Raises:
        Exception: 下载失败或图片无法解码(损坏/截断)时抛出,且不会写入磁盘缓存
    """
    src = source.file if isinstance(source, File) else str(source)
    key = make_cache_key("image", src, file_name, f"kb={max_size_kb}")

    async with _get_lock(key):
        entry = await cache_get(key)

        if entry is not None:
            return MediaConvertResult(
                data=entry.to_base64(),
                fmt=entry.fmt,
                mime=entry.mime,
                converted=entry.converted,
            )

        data = None
        jpeg: bytes | None = None
        for attempt in range(_MAX_DOWNLOAD_RETRIES + 1):
            _, data = await resolve_file_to_bytes(source, "image", max_bytes=max_bytes)
            try:
                jpeg = await asyncio.to_thread(convert_to_jpeg, data, max_size_kb)
                break
            except OSError as exc:
                if attempt < _MAX_DOWNLOAD_RETRIES and "truncated" in str(exc).lower():
                    await asyncio.sleep(0.5)
                    continue
                raise

        result = MediaConvertResult(
            data=base64.b64encode(jpeg).decode(),
            fmt="jpeg",
            mime="image/jpeg",
            converted=True,
        )
        await cache_put(key, jpeg, result.fmt, result.mime, result.converted)
        return result
