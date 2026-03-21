from typing import Any, Dict, List, Optional

import aiohttp

from atribot.core.service_container import container

headers = {
    "Authorization": f"Bearer {container.get("config").model.tavily_search_API_key}",
    "Content-Type": "application/json"
}

tool_json = {
    "name": "web_search",
    "description": "网络搜索工具，提供全面、实时的搜索结果。支持自定义结果数量、内容类型与域名筛选,在获取实时信息、新闻与进行网络内容分析的时候可以使用",
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
    include_answer: Optional[str] = "advanced",
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



async def web_extract(
    urls: str | List[str],
    include_images: bool = False,
    extract_depth: str = "basic",
    query: Optional[str] = None,
    chunks_per_source: int = 3,
    format: str = "markdown",
    timeout: Optional[float] = None
):
    """
    Tavily Extract API
    https://docs.tavily.com/documentation/api-reference/endpoint/extract
    
    该函数用于从一个或多个指定的 URL 中提取清洗后的网页内容。
    通常配合 web_search 工具使用：先搜索获取 URL，再用此工具读取内容。
    它能自动去除广告、导航栏，并返回对 LLM 友好的 Markdown 格式。

    Args:
        urls (Union[str, List[str]]): 
            需要提取内容的 URL 或 URL 列表。
            例如："https://en.wikipedia.org/wiki/Artificial_intelligence" 
            或 ["https://site1.com", "https://site2.com"]。
        
        include_images (bool, optional): 
            是否提取网页中的图片链接。默认为 False。
        
        extract_depth (str, optional): 
            提取深度。默认为 "basic"。
            - "basic": 基础提取，速度快，成本低（1 credit / 5 URLs）。
            - "advanced": 高级提取，处理动态加载内容、表格效果更好，但耗时稍长（2 credits / 5 URLs）。
        
        query (str, optional): 
            如果提供此参数，API 将根据此查询词对提取的内容块（Chunks）进行重排序（Rerank），
            优先返回与查询最相关的内容片段。适用于长文档的针对性提取。
            
        chunks_per_source (int, optional): 
            仅当提供了 `query` 时生效。定义每个源返回的最大相关片段数量。
            范围 1-5，默认为 3。
            
        format (str, optional): 
            返回内容的格式。默认为 "markdown"。
            - "markdown": 结构化文本，最适合 LLM 阅读。
            - "text": 纯文本。
            
        timeout (float, optional): 
            请求超时时间（秒）。范围 1.0 到 60.0。
            如果不设置，basic 默认为 10s，advanced 默认为 30s。

    Returns:
        str: 格式化后的人类/LLM 可读字符串，包含提取的内容或错误信息。
    """

    payload = {
        "urls": urls,
        "include_images": include_images,
        "extract_depth": extract_depth,
        "format": format,
        "include_usage": True 
    }

    if query:
        payload["query"] = query
        payload["chunks_per_source"] = chunks_per_source
    
    if timeout:
        payload["timeout"] = timeout

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url="https://api.tavily.com/extract",
                headers=headers,
                json=payload
            ) as resp:
                # 处理非 200 错误
                if resp.status != 200:
                    error_text = await resp.text()
                    return f"❌ API 请求失败: {resp.status} - {error_text}"
                
                data = await resp.json()
                # print(json.dumps(data, indent=2, ensure_ascii=False)) # 调试用
                return format_extract_results(data)
        except Exception as e:
            return f"❌ 请求过程中发生异常: {str(e)}"


def format_extract_results(response_data: Dict[str, Any]) -> str:
    """
    将 Tavily Extract 结果 JSON 转换为 LLM 易读的 Markdown 文本格式。
    """
    lines = []
    
    # 1. 处理成功提取的结果
    if results := response_data.get("results", []):
        lines.append(f"# 📄 网页提取结果 ({len(results)}个页面)\n")
        
        for idx, item in enumerate(results, 1):
            url = item.get("url", "未知URL")
            lines.append(f"## 🔗 来源 {idx}: {url}")
            
            # 原始内容 (Markdown)
            raw_content = item.get("raw_content", "")
            if raw_content:
                lines.append("### 📝 页面内容:")
                lines.append(raw_content)
                lines.append("\n---\n")
            else:
                lines.append("> 未提取到有效内容。\n")

            # 图片 (如果有)
            if images := item.get("images"):
                lines.append(f"**🖼️ 提取到的图片 ({len(images)}张):**")
                # 限制显示数量以免 Context 爆炸，或者全部列出
                for img_url in images[:5]: 
                    lines.append(f"- ![]({img_url})")
                if len(images) > 5:
                    lines.append(f"- *(还有 {len(images)-5} 张图片未展示)*")
                lines.append("")

    # 2. 处理失败的结果
    if failed_results := response_data.get("failed_results", []):
        lines.append("## ❌ 提取失败的页面")
        for item in failed_results:
            lines.append(f"- **URL**: {item.get("url", "未知URL")}")
            lines.append(f"  - 原因: {item.get("error", "未知错误")}")
        lines.append("")

    # 3. 统计信息
    stats = []
    if response_time := response_data.get("response_time"):
        stats.append(f"耗时: {response_time}秒")
    
    if stats:
        lines.append(f"*{' | '.join(stats)}*")

    return "\n".join(lines)
    
    