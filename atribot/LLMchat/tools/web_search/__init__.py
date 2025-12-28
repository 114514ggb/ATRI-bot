import aiohttp
from typing import List, Dict, Optional, Any
from atribot.core.service_container import container


headers = {
    "Authorization": f"Bearer {container.get("config").model.tavily_search_API_key}",
    "Content-Type": "application/json"
}

tool_json = {
    "name": "web_search",
    "description": "强大的网络搜索工具，提供全面、实时的搜索结果。支持自定义结果数量、内容类型与域名筛选，是获取实时信息、新闻与进行网络内容分析的理想方案",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query"
        },
        "search_depth": {
            "type": "string",
            "enum": [
                "basic",
                "advanced"
            ],
            "description": "The depth of the search. It can be 'basic' or 'advanced'",
            "default": "advanced"
        },
        "topic": {
            "type": "string",
            "enum": [
                "general",
                "news"
            ],
            "description": "The category of the search. This will determine which of our agents will be used for the search",
            "default": "general"
        },
        "days": {
            "type": "number",
            "description": "The number of days back from the current date to include in the search results. This specifies the time frame of data to be retrieved. Please note that this feature is only available when using the 'news' search topic",
            "default": 3
        },
        "time_range": {
            "type": "string",
            "description": "The time range back from the current date to include in the search results. This feature is available for both 'general' and 'news' search topics",
            "enum": [
                "day",
                "week",
                "month",
                "year",
                "d",
                "w",
                "m",
                "y"
            ]
        },
        "max_results": {
            "type": "number",
            "description": "The maximum number of search results to return",
            "default": 10,
            "minimum": 5,
            "maximum": 20
        },
        "include_images": {
            "type": "boolean",
            "description": "Include a list of query-related images in the response",
            "default": False
        },
        "include_image_descriptions": {
            "type": "boolean",
            "description": "Include a list of query-related images and their descriptions in the response",
            "default": False
        },
        "include_raw_content": {
            "type": "boolean",
            "description": "Include the cleaned and parsed HTML content of each search result",
            "default": False
        },
        "include_domains": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "A list of domains to specifically include in the search results, if the user asks to search on specific sites set this to the domain of the site",
            "default": []
        },
        "exclude_domains": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of domains to specifically exclude, if the user asks to exclude a domain set this to the domain of the site",
            "default": []
        }
    }
}



async def main(
        query: str,
        search_depth: str = "basic",
        topic: str = "general",
        days: int = 3,
        time_range: Optional[str] = None,
        max_results: int = 10,
        include_images: bool = False,
        include_image_descriptions: bool = False,
        include_raw_content: bool = False,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None
    ):
    return await web_search(
        query=query, 
        search_depth=search_depth, 
        topic=topic,
        days=days,
        time_range=time_range,
        max_results=max_results,
        include_images=include_images,
        include_image_descriptions=include_image_descriptions,
        include_raw_content=include_raw_content,
        include_domains=include_domains,
        exclude_domains=exclude_domains
    )


async def web_search(
    query: str,
    auto_parameters:bool = False,
    search_depth: str = "basic",
    topic: str = "general",
    days: int = 3,
    time_range: Optional[str] = None,
    max_results: int = 10,
    include_answer: Optional[str] = None,
    include_images: bool = False,
    include_image_descriptions: bool = False,
    include_raw_content: bool = False,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None
):
    """
    Tavily Search api
    https://docs.tavily.com/documentation/api-reference/endpoint/search
    该函数封装了 Tavily Search API，支持通用搜索和新闻搜索，允许自定义搜索深度、
    时间范围、结果数量以及内容过滤（如包含/排除特定域名）。

    Args:
        query (str): 
            搜索查询字符串（例如："Who is Leo Messi?"）。
        
        auto_parameters (bool):
            自动根据查询内容和意图配置搜索参数。你仍然可以手动设置其他参数，你的显式数值会覆盖自动参数
            include_raw_content 和 max_results 必须始终手动设置，因为它们直接影响响应大小
        
        search_depth (str, optional): 
            搜索深度。默认为 "basic"。
            - "basic": 快速搜索，返回基础结果。
            - "advanced": 深入搜索，结果更相关、质量更高，但耗时稍长（消耗 2 credits）。
        
        topic (str, optional): 
            搜索主题类别。默认为 "general"。
            - "general": 通用搜索，覆盖广泛来源。
            - "news": 新闻搜索，侧重于实时更新和主流媒体。
            
        days (int, optional): 
            回溯天数。默认为 3。
            仅当 topic 为 "news" 时生效，指定搜索过去多少天内的新闻数据。
        
        time_range (Optional[str], optional): 
            时间范围过滤器。默认为 None。
            用于筛选发布时间或更新时间。可选值包括：
            "day", "week", "month", "year", "d", "w", "m", "y"。
            适用于 "general" 和 "news" 主题。
        
        max_results (int, optional): 
            返回的最大搜索结果数量。默认为 10。
            有效范围通常为 5 到 20。
        
        include_answer (str)
            是否包含对用户查询的简短回答，由大型语言模型生成。可设置为False,true,basic 或 advanced
    
        include_images (bool, optional): 
            是否在响应中包含与查询相关的图片列表。默认为 False。
        
        include_image_descriptions (bool, optional): 
            是否包含图片的描述文本。默认为 False。
            仅当 include_images 为 True 时生效。
        
        include_raw_content (bool, optional): 
            是否包含每个搜索结果的清洗后 HTML原始内容。默认为 False。
            如果为 True，响应体将变大。
        
        include_domains (Optional[List[str]], optional): 
            指定包含的域名列表（白名单）。默认为 None。
            如果设置，搜索结果将仅限于这些域名（例如：["wsj.com", "wikipedia.org"]）。
        
        exclude_domains (Optional[List[str]], optional): 
            指定排除的域名列表（黑名单）。默认为 None。
            如果设置，搜索结果将自动过滤掉这些域名。

    Returns:
        str:人类可读的str
    """

    if include_domains is None:
        include_domains = []
    if exclude_domains is None:
        exclude_domains = []

    if auto_parameters:
        payload = {
            "query": query,
            "max_results": max_results,
            "include_raw_content": include_raw_content,
            "auto_parameters":True,
        }
    else:
        payload = {
            "query": query,
            "topic": topic,
            "search_depth": search_depth,
            "max_results": max_results,
            "days": days,
            "include_images": include_images,
            "include_image_descriptions": include_image_descriptions,
            "include_raw_content": include_raw_content,
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "include_answer": False
        }

    if time_range:
        payload["time_range"] = time_range

    if include_answer:
        payload["include_answer"] = include_answer

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url="https://api.tavily.com/search",
            headers=headers,
            json=payload
        ) as resp:
            json = await resp.json()
            print(json)
            return format_search_results(json)
        


def format_search_results(response_data: Dict[str, Any]) -> str:
    """
    将 Tavily 搜索结果 JSON 转换为 LLM 易读的 Markdown 文本格式。
    
    Args:
        response_data (dict): Tavily API 返回的原始 JSON 数据。
        
    Returns:
        str: 格式化后的 Markdown 字符串。
    """
    lines = []

    lines.append(f"# 🔍 搜索查询: {response_data.get("query", "未知查询")}\n")

    if answer :=  response_data.get("answer"):
        lines.append("## 💡 智能摘要")
        lines.append(f"{answer}\n")

    if results := response_data.get("results", []):
        lines.append(f"## 📄 搜索结果来源 ({len(results)}条)")
        
        for idx, item in enumerate(results, 1):
            lines.append(f"### 来源 {idx}: [{item.get("title", "无标题")}]({item.get("url", "#")})")
                         
            if content := item.get("content", "无内容摘要"):
                lines.append(f"> **摘要**: {content}")
            
            # 如果有 raw_content 通常太长
            if raw_content := item.get("raw_content"):
                lines.append(f"截断的原始html:{raw_content[:1000]}")
    else:
        lines.append("## 📄 搜索结果: 未找到相关页面\n")

    if images:= response_data.get("images", []):
        lines.append(f"## 🖼️ 相关图片 ({len(images)}张)")
        for img in images:
            if isinstance(img, str):
                lines.append(f"- ![]({img})")
            elif isinstance(img, dict):
                url = img.get("url", "")
                desc = img.get("description", "图片")
                lines.append(f"- [{desc}]({url})")
        lines.append("")

    if response_time:= response_data.get("response_time"):
        lines.append(f"*搜索耗时: {response_time}秒*")

    return "\n".join(lines)
    