import asyncio
from urllib.parse import urlparse

import aiohttp
import trafilatura

tool_json = {
    "name": "web_browser",
    "description": "访问一个网址并提取里面的静态文本内容,会过滤无关元素",
    "properties": {
        "url": {
            "type": "string",
            "description": "目标URL"
        }
    }
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Referer': 'https://www.google.com/',
    'Accept-Language': 'zh-CN,zh-TW;q=0.9,zh-HK;q=0.8,zh;q=0.7',
}

#简单黑名单
BLOCKED_IPS = ['127.0.0.1', 'localhost', '0.0.0.0']

async def main(url: str):
    return await fetch_url(url)


def is_safe_url(url):
    try:
        hostname = urlparse(url).hostname
        if hostname in BLOCKED_IPS:
            return False
        return True
    except Exception:
        return False


async def fetch_url(url: str):
    if not is_safe_url(url):
        return {"error": "Security Alert: Access to this URL is restricted."}

    timeout = aiohttp.ClientTimeout(total=15) # 设置超时防止卡死

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return {"error": f"HTTP Status {response.status}", "url": url}
                
                content_type = response.headers.get('Content-Type', '').lower()
                
                if 'application/json' in content_type:
                    return {"type": "json", "content": await response.json()}
                
                if 'text/html' not in content_type:
                    return {"type": "other", "info": "Non-HTML content detected (e.g., binary/file)."}

                html = await response.text(errors='ignore')

                text_content = trafilatura.extract(
                    html, 
                    include_links=True, 
                    output_format='markdown',
                    target_language='zh'
                )

                if not text_content:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    for script in soup(["script", "style", "nav", "footer"]):
                        script.decompose()
                    text_content = soup.get_text(separator='\n', strip=True)

                max_len = 9500
                if len(text_content) > max_len:
                    text_content = text_content[:max_len] + "\n\n[Content Truncated...]"

                return {
                    "url": url,
                    "title": trafilatura.extract_metadata(html).title if trafilatura.extract_metadata(html) else "No Title",
                    "content": text_content
                }

        except asyncio.TimeoutError:
            return {"error": "Request timed out"}
        except Exception as e:
            return {"error": str(e)}

if __name__ == "__main__":
    from pprint import pp
    # url = "https://www.example.com"
    url = "https://playwright.dev/docs/browsers"
    pp(asyncio.run(fetch_url(url)))