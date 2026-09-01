import asyncio
import base64
import io
from typing import TYPE_CHECKING

import aiohttp
from PIL import Image, ImageFile

from atribot.common_utils.file.file_utils import resolve_file_to_bytes
from atribot.common_utils.file.media_cache import make_cache_key
from atribot.common_utils.file.media_utils import MediaConvertResult, _load_with_cache
from atribot.common_utils.http_client import HTTPClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import File

if TYPE_CHECKING:
    from atribot.core.platform.send_client import SendClientBase

ImageFile.LOAD_TRUNCATED_IMAGES = True

_MAX_DOWNLOAD_RETRIES: int = 2

_GET_IMAGE_MAX_BYTES: int = 1024 * 1024
"""通过 get_image API 获取图片的原始体积上限(1MB)"""


def convert_to_jpeg(
    image_bytes: bytes,
    max_size_kb: int | None = None,
    background: tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    """
    将任意图片字节强制统一转码为标准 JPEG(含动画 GIF 取首帧)

    特性:
    - 动画(GIF/WebP 多帧)取第一帧转静态图
    - RGBA/LA/P 等带透明通道的图片合成到指定背景色(默认白底),避免转 RGB 变黑
    - 解码失败(数据损坏/截断/非图片)抛出异常,供调用方捕获处理
    - 截断图片会在解码时抛 ``OSError('truncated')``,而不会被静默灰色填充,
      以便 ``url_to_image_jpeg`` 等调用方识别并发起重试下载
    - max_size_kb 限制输出体积:先降画质(90→20),仍超限则等比例缩小尺寸并固定画质 20

    Args:
        image_bytes: 原始图片字节数据
        max_size_kb: 目标体积上限(KB);None 表示不限制(仍会统一转 JPEG)
        background: 透明区域合成背景色,默认白色 (255, 255, 255)

    Returns:
        标准 JPEG 字节

    Raises:
        Exception: 图片解码/编码失败时抛出(PIL 异常等),含截断图抛 OSError
    """
    _prev_trunc_flag = ImageFile.LOAD_TRUNCATED_IMAGES
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()

        if getattr(image, "is_animated", False):
            image.seek(0)
            image.load()
    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = _prev_trunc_flag

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
    不再透传原始格式此函数为 ``convert_to_jpeg`` 的兼容封装:
    - **解码层 OSError(截断/损坏)不再回退**,而是向上抛出,避免把残缺内容当成功结果
    - 仅对非解码类异常回退返回原始字节
    Args:
        image_bytes: 原始图片的字节数据
        max_size_kb: 目标大小上限,单位KB

    Returns:
        bytes: 压缩转码后的 JPEG 字节;非解码类失败返回原始数据

    Raises:
        OSError: 输入为截断/损坏图片时抛出(供调用方重试/丢弃,而非产出灰色填充)
    """
    try:
        return convert_to_jpeg(image_bytes, max_size_kb=max_size_kb)
    except OSError:
        # 截断/损坏图片不得静默回退为原始字节(会产出灰色填充), 交由调用方重试/丢弃
        raise
    except Exception:
        return image_bytes


def _ensure_download_complete(resp: aiohttp.ClientResponse, content: bytes) -> bytes:
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
            return content
        if len(content) != expected:
            raise ValueError(
                f"下载不完整: Content-Length={clen} 实际={len(content)} bytes"
            )
    return content


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

            content = _ensure_download_complete(resp, content)

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
    """下载图片并统一转换为 JPEG base64

    Args:
        source: 图片来源(File 或字符串)
        max_size_kb: 压缩后体积上限(KB),None 不限制(仍转 JPEG)
        max_bytes: 最大下载字节数,默认 10MB
        file_name: 文件名(QQ 媒体为内容哈希),作为缓存键

    Returns:
        MediaConvertResult

    Raises:
        Exception: 下载失败或图片损坏/截断时抛出,且不入缓存
    """
    src = source.file if isinstance(source, File) else str(source)
    key = make_cache_key("image", src, file_name, f"kb={max_size_kb}")

    async def produce() -> tuple[bytes, MediaConvertResult]:
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
        return jpeg, result

    return await _load_with_cache(key, produce)


async def fetch_image_jpeg(
    source: str | File,
    *,
    file_name: str | None = None,
    send_client: SendClientBase | None = None,
    max_size_kb: int | None = 2048,
    max_bytes: int = 10 * 1024 * 1024,
) -> MediaConvertResult:
    """获取图片并统一转换为 JPEG base64

    提供 send_client 和 file_name 时优先走 get_image API(仅小图)；失败或图片过大则回退下载

    Args:
        source: 图片来源(File 或字符串)
        file_name: QQ 图片文件哈希
        send_client: 发送客户端,用于 get_img_details
        max_size_kb: 压缩后体积上限(KB),None 不限制
        max_bytes: 回退路径最大下载字节数,默认 10MB

    Returns:
        MediaConvertResult

    Raises:
        Exception: 两条路径均失败时抛出
    """
    if send_client is not None and file_name:
        src = source.file if isinstance(source, File) else str(source)
        key = make_cache_key("image", src, file_name, f"kb={max_size_kb}")

        async def produce_via_details() -> tuple[bytes, MediaConvertResult]:
            details = await send_client.get_img_details(file=file_name)
            if not details or not details.get("base64"):
                raise ValueError("get_image 无 base64")
            raw_bytes = base64.b64decode(details["base64"])
            if len(raw_bytes) > _GET_IMAGE_MAX_BYTES:
                raise ValueError("图片过大,回退下载")
            jpeg = await asyncio.to_thread(convert_to_jpeg, raw_bytes, max_size_kb)
            result = MediaConvertResult(
                data=base64.b64encode(jpeg).decode(),
                fmt="jpeg",
                mime="image/jpeg",
                converted=True,
            )
            return jpeg, result

        try:
            return await _load_with_cache(key, produce_via_details)
        except Exception:
            pass  # 回退到 url_to_image_jpeg

    return await url_to_image_jpeg(
        source,
        max_size_kb=max_size_kb,
        max_bytes=max_bytes,
        file_name=file_name,
    )
