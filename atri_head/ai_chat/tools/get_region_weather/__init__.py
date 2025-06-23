import aiohttp
import asyncio

tool_json = {
    "name": "get_region_weather",
    "description": "查询指定地区的当前和未来几天的天气数据的工具,需要用户提供地理位置参数",
    "properties": {
        "location": {
            "type": "string",
            "description": "地名（如北京,武汉）,支持中英等多国语言地名,如果为空就是本机ip所在的地址",
        }
    }
}



async def main(location):
    data_json:dict = await get_weather(location)
    try:
        data = parse_weather_data(data_json)
    except Exception:
        data = data_json
        
    return {"get_region_weather":data}

header = {
    'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 '
    'Safari/537.36',
    'accept-encoding':'gzip, deflate, br, zstd',
    'accept-language':'zh-CN,zh-TW;q=0.9,zh-HK;q=0.8,zh;q=0.7'
}

async def get_weather(city)->dict:
    """获取指定城市天气"""
    url = f'https://wttr.in/{city}?format=j1'
    async with aiohttp.ClientSession() as session:
        async with session.get(url,headers=header) as resp:
            data = await resp.json()
            return data


def parse_weather_data(weather_json):
    area = weather_json['nearest_area'][0]['areaName'][0]['value']
    region = weather_json['nearest_area'][0]['region'][0]['value']
    
    current = weather_json['current_condition'][0]
    current_str = (
        f"当前位置：{area}, {region}\n"
        f"当前时间：{current['localObsDateTime']}\n"
        f"当前温度：{current['temp_C']}°C (体感 {current['FeelsLikeC']}°C)\n"
        f"天气状况：{current['lang_zh'][0]['value']}\n"
        f"湿度：{current['humidity']}% | 风速：{current['windspeedKmph']}公里/小时\n"
        f"降水量：{current['precipMM']}毫米 | 能见度：{current['visibility']}公里"
    )
    
    forecast_str = "\n\n未来三日天气预报："
    for day in weather_json['weather']:
        date = day['date']
        forecast_str += f"\n\n日期：{date}"
        forecast_str += f"\n最高温：{day['maxtempC']}°C | 最低温：{day['mintempC']}°C"
        forecast_str += f"\n日出：{day['astronomy'][0]['sunrise']} | 日落：{day['astronomy'][0]['sunset']}"
        
        for hour in day['hourly']:
            if hour['time'] == "1200":
                forecast_str += f"\n中午天气：{hour['lang_zh'][0]['value']} ({hour['tempC']}°C)"
            if hour['time'] == "1800":
                forecast_str += f"\n傍晚天气：{hour['lang_zh'][0]['value']} ({hour['tempC']}°C)"
    
    return current_str + forecast_str
