import aiohttp

from atribot.common_utils.http_client import HTTPClient
from atribot.core.service_container import container


async def download_text(
    url: str,
    max_chars: int = 400,
    max_bytes: int = 1024 * 100,
    encoding: str | None = None,
) -> str:
    """流式下载文本文件(Range 请求只取前 max_bytes 字节)

    Args:
        url: 文件 URL
        max_chars: 解码后最大字符数，超限截断
        max_bytes: 最大下载字节数(网络硬限制)
        encoding: 指定编码,None 时用响应 charset 或 BOM 检测，默认 utf-8

    Returns:
        文本内容；失败/超时/非文本返回空字符串
    """
    try:
        session: aiohttp.ClientSession = container.get_by_type(HTTPClient).session
        async with session.get(
            url,
            headers={
                'Accept': 'text/plain,text/html,text/*,application/json,*/*;q=0.8',
                'Range': f'bytes=0-{max_bytes-1}',
            },
            timeout=aiohttp.ClientTimeout(total=30, connect=10),
        ) as resp:
            if resp.status not in (200, 206):
                return ""

            raw_bytes = await resp.content.read(max_bytes)
            if not raw_bytes:
                return ""

            enc = encoding or resp.charset
            if enc is None:
                if raw_bytes.startswith(b'\xef\xbb\xbf'):
                    enc = 'utf-8-sig'
                elif raw_bytes.startswith(b'\xff\xfe'):
                    enc = 'utf-16-le'
                elif raw_bytes.startswith(b'\xfe\xff'):
                    enc = 'utf-16-be'
                else:
                    enc = 'utf-8'

            text = raw_bytes.decode(enc, errors='replace')
            return text[:max_chars] if len(text) > max_chars else text
    except Exception as error:
        print(f"下载失败 {url}: {error}")
        return ""
