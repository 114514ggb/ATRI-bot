from atri_head.Basics import Basics,Command_information
import re
from lxml import etree
import aiohttp


class crawler_bili():
    """用于爬取bilibili视频信息"""
    def __init__(self):
        self.basics = Basics()

    BILIBILI_HEADER = {
        'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 '
            'Safari/537.36',
        'referer': 'https://www.bilibili.com',
    }
    """bilibili请求头"""


    async def main(self, argument, group_ID, data):

        url = argument[1][0]

        if re.match(r'^BV[1-9a-zA-Z]{10}$', url):
            url = 'https://www.bilibili.com/video/' + url

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.BILIBILI_HEADER) as response:
                if response.status == 200:
                    response = await response.text(encoding='utf-8')#获取网页源码

                    tree = etree.HTML(response, parser=etree.HTMLParser())

                    title_element = tree.xpath('//title/text()')
                    web_title = title_element[0]
                    video_tag=video_introduce=video_cover = "None"
                    video_tag,video_introduce,video_cover = tree.xpath('//meta[@name="keywords" or @name="description" or @itemprop="thumbnailUrl"]/@content')
                    text = f"网站标题:{web_title}\n网站标签:\n{video_tag}\n网站介绍:\n{video_introduce}\n封面:{video_cover}"

                    await self.basics.QQ_send_message.send_group_message(group_ID,text)
                    await self.basics.QQ_send_message.send_group_pictures(group_ID,"https:"+video_cover,local_Path_type=False)

                    return "ok"

                else:
                    Exception("请求失败")



crawler = crawler_bili()

command_main = Command_information(
    name="crawler",
    aliases=["爬虫", "crawler", "b站"],
    handler=crawler.main,
    description="爬取bilibili视频信息",
    parameter=[[0, 0], [1, 10]]
)