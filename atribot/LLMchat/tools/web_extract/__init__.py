from typing import List, Optional

from atribot.LLMchat.tools.web_search import web_extract

tool_json = {
    "name": "web_extract",
    "description": "网页内容提取工具,可从指定的一个或多个URL中获取清洗后的Markdown正文内容。在深入阅读和分析特定网页内容的时候使用",
    "properties": {
        "urls": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "A list of URLs to extract content from. Usually obtained from search results"
        },
        "include_images": {
            "type": "boolean",
            "description": "Whether to extract a list of images from the webpage",
            "default": False
        },
        "extract_depth": {
            "type": "string",
            "enum": [
                "basic",
                "advanced"
            ],
            "description": "The depth of the extraction. 'basic' static content; 'advanced' handles dynamic content (SPA/JavaScript) and tables better but is slower",
            "default": "advanced"
        },
        "query": {
            "type": "string",
            "description": "Optional search query to rerank the extracted content. If provided, the tool returns specific chunks relevant to this query instead of the full page. Useful for finding specific answers in long documents"
        },
        "chunks_per_source": {
            "type": "number",
            "description": "The maximum number of relevant chunks (snippets) to return per URL. Only effective when 'query' is provided. Range: 1-5",
            "default": 3,
            "minimum": 1,
            "maximum": 5
        },
        "format": {
            "type": "string",
            "enum": [
                "markdown",
                "text"
            ],
            "description": "The output format of the extracted content. Markdown is recommended for LLMs",
            "default": "markdown"
        }
    }
}


async def main(
    urls: str | List[str],
    include_images: bool = False,
    extract_depth: str = "advanced",
    query: Optional[str] = None,
    chunks_per_source: int = 3,
    format: str = "markdown"
):
    return await web_extract(
        urls,
        include_images,
        extract_depth,
        query,
        chunks_per_source,
        format,
        timeout = 15
    )