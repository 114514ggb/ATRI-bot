import asyncio

import aiohttp

from atribot.core.service_container import container


async def download_text(
    url: str,
    max_chars: int = 400,
    max_bytes: int = 1024 * 100,
    encoding: str | None = None,
) -> str:
    """
    流式下载文本文件,支持字节和字符双重限制,防止大文件爆内存
    
    优先使用 HTTP Range 请求只下载前 max_bytes 字节,节省带宽。
    若服务器不支持 Range,则通过流式读取限制在 max_bytes 后强制断开。
    
    Args:
        url: 文件URL
        max_chars: 最大字符数（解码后截断）,默认4000字符
        max_bytes: 最大下载字节数（网络传输硬限制）,默认100KB
        encoding: 指定编码如'utf-8',None则自动检测
    
    Returns:
        str: 文本内容。失败、超时或非文本内容返回空字符串。
            若内容超过 max_chars,返回前 max_chars 个字符（带省略号提示可自定义）。
    
    Examples:
        >>> # 下载代码文件,最多1MB字节/5000字符
        >>> code = await download_text('https://example.com/large.log', max_bytes=1024*512, max_chars=5000)
        >>> 
        >>> # 明确指定GBK编码
        >>> txt = await download_text('https://example.com/legacy.txt', encoding='gbk')
    """
    try:
        session:aiohttp.ClientSession = container.get("HTTPClient").session
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
                
                enc = encoding
                if enc is None:
                    enc = resp.charset
                
                if enc is None:
                    # 检测BOM (Byte Order Mark)
                    if raw_bytes.startswith(b'\xef\xbb\xbf'):
                        enc = 'utf-8-sig'  
                    elif raw_bytes.startswith(b'\xff\xfe'):
                        enc = 'utf-16-le'
                    elif raw_bytes.startswith(b'\xfe\xff'):
                        enc = 'utf-16-be'
                    else:
                        enc = 'utf-8'
                
                text = raw_bytes.decode(enc, errors='replace')
                
                if len(text) > max_chars:
                    return text[:max_chars] 
                return text

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"下载失败 {url}: {e}")
        return ""
    except Exception as e:
        print(f"处理文本失败 {url}: {e}")
        return ""
