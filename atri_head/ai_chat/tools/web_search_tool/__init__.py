import aiohttp


tokey = "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"

headers = {
    "Authorization": f"Bearer {tokey}",
    "Content-Type": "application/json"
}

tool_json = {
    "name": "web_search_tool",
    "description": "网络信息检索工具,可以搜索到一些和关键词有关的信息,也可以用于获取一些新闻",
    "properties": {
        "query": {
            "type": "string",
            "description": "需要搜索的关键词"
        },
        "topic": {
            "type": "string",
            "description": "搜索类别可以是general或news，如果不填则默认为basic，需要近三天的新闻就填news"
        }
}
}

async def main(query, topic = "basic"):
    return await web_search(query, topic)


async def web_search(query:str ,topic:str):
    """
        Tavily Search api
        https://docs.tavily.com/documentation/api-reference/endpoint/search
    """
    payload = {
        "query": query,
        "topic": topic,
        "search_depth": "basic",
        "max_results": 5,
        "time_range": None,
        "days": 3,
        "include_answer": "advanced",
        "include_raw_content": False,
        "include_images": False,
        "include_image_descriptions": False,
        "include_domains": [],
        "exclude_domains": []
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url="https://api.tavily.com/search",
            headers=headers,
            json=payload
        ) as resp:
            return await resp.json()