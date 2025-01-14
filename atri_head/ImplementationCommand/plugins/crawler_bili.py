from .example_plugin import example_plugin as example
import re
from lxml import etree
import aiohttp

class crawler_bili(example):
    """用于爬取bilibili视频信息"""
    register_order = ["/B站", "/爬虫"]

    BILIBILI_HEADER = {
        'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 '
            'Safari/537.36',
        'referer': 'https://www.bilibili.com',
    }
    """bilibili请求头"""

    async def crawler_bili(self, user_input, qq_TestGroup, data, basics):
        self.store(user_input, qq_TestGroup, data, basics)
        self.basics.Command.verifyParameter(
            self.argument,
            parameter_quantity_max_1=0, parameter_quantity_min_1=0, 
            parameter_quantity_max_2=1, parameter_quantity_min_2=1,
        )

        url = self.argument[1][0]

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

                    await self.basics.QQ_send_message.send_group_message(qq_TestGroup,text)
                    await self.basics.QQ_send_message.send_group_pictures(qq_TestGroup,"https:"+video_cover,local_Path_type=False)

                    return "ok"

                else:
                    Exception("请求失败")
