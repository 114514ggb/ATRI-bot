import asyncio
import base64
import io

import aiohttp
from PIL import Image


def compress_image(image_bytes: bytes, max_size_kb: int) -> bytes:
    """
    压缩图片到指定大小以内(包含画质降低和尺寸缩放两种策略)
    
    先通过逐步降低画质(从90到20)来减小文件大小，
    如果仍超过限制,则按比例缩小图片尺寸并固定画质为20继续压缩,
    直到达到目标大小或尺寸过小(小于10像素)为止。
    
    Args:
        image_bytes: 原始图片的字节数据
        max_size_kb: 目标大小上限,单位KB
    
    Returns:
        bytes: 压缩后的图片字节数据。如果压缩失败或原始图片已符合要求，返回原始数据。
    
    Examples:
        >>> with open('large.jpg', 'rb') as f:
        ...     compressed = compress_image(f.read(), 500)
        >>> print(f'压缩后大小: {len(compressed) / 1024:.2f}KB')
    """
    max_size_bytes = max_size_kb * 1024

    if len(image_bytes) <= max_size_bytes:
        return image_bytes

    try:
        image = Image.open(io.BytesIO(image_bytes))

        if image.mode != "RGB":
            image = image.convert("RGB")

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
    except Exception as error:
        print(f"图片压缩失败: {error}")
        return image_bytes


async def urls_list_to_base64(
    urls: list[str],
    prefix: str = "data:image/jpeg;base64,",
    concurrency: int = 5,
    max_size_kb: int | None = 1024,
) -> list[str]:
    """
    并发下载一组图片 URL 并压缩，返回对应的 base64 字符串列表
    
    使用 aiohttp 实现并发下载，通过信号量控制并发数量。
    下载后的图片会根据指定的体积限制进行压缩。
    
    Args:
        urls: 图片URL地址列表
        prefix: Base64字符串的前缀,默认为JPEG格式的数据URI前缀
        concurrency: 最大并发下载数量,默认为5
        max_size_kb: 图片最大体积限制,单位KB。设为 None 表示不压缩。
                    默认值为 1024KB (1MB)
    
    Returns:
        List[str]: 与输入顺序一致的base64字符串列表。
                如果某个URL下载失败,对应的位置会返回空字符串。
    
    Examples:
        >>> urls = ['https://example.com/image1.jpg', 'https://example.com/image2.jpg']
        >>> results = await urls_to_base64(urls, max_size_kb=500)
        >>> for i, base64_str in enumerate(results):
        ...     if base64_str:
        ...         print(f'图片{i+1}转换成功')
    
    Raises:
        Exception: 此方法不会抛出异常，所有异常都会被捕获并记录，
                失败的URL对应位置返回空字符串。
    """
    semaphore = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=concurrency * 2),
        headers={
            "User-Agent": "QQ/9.9.21-39038 CFNetwork/1220.1 Darwin/20.3.0",
            "Accept": "image/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        timeout=aiohttp.ClientTimeout(total=30),
    ) as session:

        async def fetch(url: str) -> str:
            async with semaphore:
                try:
                    async with session.get(url) as resp:
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
    下载单张图片并压缩，返回对应的base64字符串
    
    使用 aiohttp 实现图片下载，下载后的图片会根据指定的体积限制进行压缩。
    
    Args:
        url: 图片URL地址
        prefix: Base64字符串的前缀,默认为JPEG格式的数据URI前缀
        max_size_kb: 图片最大体积限制,单位KB。设为 None 表示不压缩。
                    默认值为 1024KB (1MB)
    
    Returns:
        str: 图片的base64字符串。如果下载失败，返回空字符串。
    
    Examples:
        >>> url = 'https://example.com/image.jpg'
        >>> result = await url_to_base64(url, max_size_kb=500)
        >>> if result:
        ...     print(f'图片转换成功: {result[:50]}...')
    
    Raises:
        此方法不会抛出异常，所有异常都会被捕获并记录，
        失败时返回空字符串。
    """
    try:
        async with aiohttp.ClientSession(
            headers={
                "User-Agent": "QQ/9.9.21-39038 CFNetwork/1220.1 Darwin/20.3.0",
                "Accept": "image/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            timeout=aiohttp.ClientTimeout(total=30),
        ) as session:
            async with session.get(url) as resp:
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
