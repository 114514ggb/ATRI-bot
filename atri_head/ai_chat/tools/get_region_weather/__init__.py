import httpx,asyncio


key = "S-6FTxYf0YMfqlS2d"
tool_json = {
    "name": "get_region_weather",
    "description": "获取指定地区的天气情况",
    "properties": {
        "location": {
            "type": "string",
            "description": "位置名称，可以是地区，如北京上海或者是一个IP地址，经纬度,直接输入‘ip’,即可获取本地天气情况。",
        }
    }
}



async def main(location):
    url =f"https://api.seniverse.com/v3/weather/now.json?key={key}&location={location}&language=zh-Hans&unit=c"

    return {"get_region_weather":await get_region_weather(url)}

async def get_region_weather(url):
    async with httpx.AsyncClient() as client: 
        response = await client.get(url)
        data = response.json()
        if 'status' in data:
            return data['status']
        else:
            return data['results'][0]['now']|{'last_update': data['results'][0]['last_update'],'path': data['results'][0]['location']['path']}