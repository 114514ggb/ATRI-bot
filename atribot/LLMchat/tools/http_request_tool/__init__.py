import aiohttp
import asyncio
from bs4 import BeautifulSoup


tool_json = {
    "name" : "http_request_tool",
    "description": "网页内容提取工具，取并返回干净的纯文本内容，移除HTML标签和脚本",
    "properties": {
        "url": {
            "type": "string",
            "description": "需要发送请求的url"
        }
    }
}

headers = {
    'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 '
    'Safari/537.36',
    # 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'referer': 'https://www.baidu.com/',
    'Accept-Language': 'en-US,en;q=0.5',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}


async def main(url: str):
    return await get(url)


async def get(url):
    """发送GET请求并返回HTML"""
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url=url) as response:
                response.raise_for_status()
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                return soup.get_text(separator=' ', strip=True)
        except aiohttp.ClientResponseError as e:
            return f"请求到非200状态码: {e.status}"
        except aiohttp.ClientError as e:
            return f"请求出错: {str(e)}"

if __name__ == "__main__":
    print(asyncio.run(main("https://r18.中国/")))
    # print(asyncio.run(main("https://www.libhunt.com/compare-index-tts-vs-gpt-sovits?ref=compare")))
    # print(asyncio.run(main("https://github.com/bytedance/trae-agent")))