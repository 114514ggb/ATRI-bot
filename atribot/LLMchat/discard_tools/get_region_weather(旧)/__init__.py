import aiohttp


key = "S-6FTxYf0YMfqlS2d"
tool_json = {
    "name": "get_region_weather",
    "description": "查询指定地区的实时天气数据，支持地名/IP地址/经纬度三种定位方式",
    "properties": {
        "location": {
            "type": "string",
            "description": "输入格式：1) 地名（如北京） 2) IP地址 3) 经纬度坐标（如39.90,116.40）直接输入'ip'自动获取本地天气",
        }
    }
}



async def main(location):
    url =f"https://api.seniverse.com/v3/weather/now.json?key={key}&location={location}&language=zh-Hans&unit=c"

    return {"get_region_weather":await get_region_weather(url)}

async def get_region_weather(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if 'status' in data:
                return data['status']
            else:
                return data['results'][0]['now'] | {
                    'last_update': data['results'][0]['last_update'],
                    'path': data['results'][0]['location']['path']
                }