from atribot.common_utils.http_client import HTTPClient
from atribot.core.service_container import container


async def search_music(keywords: str, limit: int = 5) -> list[dict]:
    """网易云音乐搜索接口，返回歌曲信息列表。

    Args:
        keywords: 搜索关键词。
        limit: 返回数量。

    Returns:
        歌曲信息列表，例如：
        `[{'name': '冬の花', 'id': 1345485069}, ...]`。
    """
    url = "https://music.163.com/api/cloudsearch/pc"
    data = {"s": keywords, "type": 1, "limit": limit}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://music.163.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
    }

    http:HTTPClient = container.get("HTTPClient")
    response_data = await http.post_form(url, data, headers=headers)

    return [
        {"name": music_item["name"], "id": music_item["id"]}
        for music_item in response_data["result"].get("songs", [])
    ]
