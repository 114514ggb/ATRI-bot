from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.commands.bromidic.picture_processing import pictureProcessing
from atribot.core.command.command_parsing import command_system
from atribot.core.service_container import container
from atribot.commands.bromidic.get_bilibili import BiliBiliCrawler
from bilibili_api import video


cmd_system:command_system = container.get("CommandSystem")
send_message:qq_send_message = container.get("SendMessage")
image_processing = pictureProcessing()



@cmd_system.register_command(
    name="bili",
    description="爬取B站视频信息",
    aliases=["b站", "bilibili"],
    examples=[
        "/bili BV1234567890",
        "/bili https://www.bilibili.com/video/BV1234567890 --info --stats",
        "/bili BV1234567890 -a",
        "/bili BV1234567890 --charging --danmaku"
    ],
    authority_level=1
)
@cmd_system.flag(
    name="info",
    short="i", 
    description="获取视频基本信息（标题、UP主、简介等）"
)
@cmd_system.flag(
    name="stats", 
    short="s",
    description="获取统计数据（播放量、点赞数等）"
)
@cmd_system.flag(
    name="online",
    short="o", 
    description="获取在线观看人数"
)
@cmd_system.flag(
    name="danmaku",
    short="d",
    description="获取弹幕信息"
)
@cmd_system.flag(
    name="charging",
    short="c",
    description="获取充电用户信息"
)
@cmd_system.flag(
    name="all",
    short="a",
    description="获取所有信息"
)
@cmd_system.argument(
    name="url_or_bv",
    description="BV号或是带有合法BV号的链接",
    required=True,
    metavar="URL/BV"
)
async def bili_crawler_command(
        message_data: dict, 
        url_or_bv: str, 
        info: bool = False, 
        stats: bool = False, 
        online: bool = False, 
        danmaku: bool = False, 
        charging: bool = False, 
        all: bool = False
    ):
    """B站视频信息爬取命令处理函数"""
    
    crawler = BiliBiliCrawler()
    
    group_id = message_data["group_id"]
    try:

        bvid = crawler.get_bv_id(url_or_bv)
 
        if all or not any([info, stats, online, danmaku, charging]):
            result = await crawler.get_video_information(bvid)
            await send_message.send_group_merge_forward(group_id, [result],source = "爬取返回值")
            return
        
        result = []
        
        v = video.Video(bvid=bvid, credential=crawler.credential)
        
        if info or stats:
            
            video_info = await v.get_info()
            
            if info:
                basic_info = crawler.parse_video_info_basic(video_info)
                result.extend(basic_info)
            
            if stats:
                # 获取统计信息
                stats_info = crawler.parse_video_stats(video_info)
                crawler.add_text(result, stats_info)
        
        # 在线人数
        if online:
            
            online_data = await v.get_online()
            online_info = crawler.parse_online_info(online_data)
            crawler.add_text(result, online_info)
        
        # 弹幕信息
        if danmaku:
            
            danmaku_data = await v.get_danmaku_view(0)
            danmaku_info = crawler.parse_danmaku_info(danmaku_data)
            crawler.add_text(result, danmaku_info)
        
        # 充电信息
        if charging:
            
            charging_data = await v.get_chargers()
            charging_info = crawler.parse_charging_info(charging_data)
            result.extend(charging_info)
        
        if result:
            await send_message.send_group_merge_forward(group_id, [result],source = "爬取返回值")
        else:
            await send_message.send_group_merge_text(group_id, "❌ 未获取到任何信息",source = "爬取返回值")
            
    except Exception as e:
        raise ValueError(f"❌爬取失败!\n{e}")
        


@cmd_system.register_command(
    name="picture_processing",
    description="图片处理命令",
    aliases=["图片","image","img"],
    examples=[
        "/picture_processing 在草地上奔跑的猫咪",
        "/image 一只戴着眼镜的狐狸 [CQ:image,file=example.jpg]"
    ],
    authority_level=1
)
@cmd_system.argument(
    name="prompt",
    description="图片处理的提示词",
    required=True,
    metavar="PROMPT"
)
async def picture_processing(message_data: dict, prompt:str):
    """图片处理命令处理函数"""
    
    img_base64 = await image_processing.step(message_data, prompt, model = "gptimage")
    group_id = message_data["group_id"]
    
    await send_message.send_group_pictures(group_id,f"base64://{img_base64}",local_Path_type=False)

