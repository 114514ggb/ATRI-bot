import aiohttp
import uuid

api_key="fc57c8c15fe94a83a56aaa1f9401be6b.kALSJcRdCTn87TdO"

tool_json = {
    "name": "web_search",
    "description": "实时网络信息检索工具,适用于需要需要时效性信息（新闻/事件/数据）的场景,这个工具会返回关键词的搜索结果",
    "properties": {
        "key_word": {
            "type": "string",
            "description": "搜索的关键词组合",
        }
    }
}

async def main(key_word):
    print(key_word)
    return {"web_search": await web_search(key_word)}

async def web_search(key_word):
    """分条返回关键词的搜索结果"""
    msg = [
        {
            "role": "user",
            "content":key_word
        }
    ]
    tool = "web-search-pro"
    url = "https://open.bigmodel.cn/api/paas/v4/tools"
    request_id = str(uuid.uuid4())
    data = {
        "request_id": request_id,
        "tool": tool,
        "stream": False,
        "messages": msg
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=data,
            headers={'Authorization': api_key},
            timeout=300
        ) as response:
            data_dict = await response.json()

            return data_dict["choices"][0]["message"]['tool_calls'][1]['search_result']
