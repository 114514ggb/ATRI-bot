import aiohttp
import uuid

api_key="fc57c8c15fe94a83a56aaa1f9401be6b.kALSJcRdCTn87TdO"

tool_json = {
    "name": "web_search",
    "description": "当你有不认识的东西或想知道你认知之外的信息时可以调用进行网络搜索,注意甄别消息内容",
    "properties": {
        "key_word": {
            "type": "string",
            "description": "你想搜索的关键词",
        }
    }
}

async def main(key_word):
    print(key_word)
    search_result = await web_search(key_word)
    return {"web_search": search_result}

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
