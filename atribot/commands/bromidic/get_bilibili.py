# import asyncio
import re

from bilibili_api import Credential, video


class BiliBiliCrawler:
    """爬取b站视频信息"""
    
    def __init__(self):
        self.credential = Credential(
            sessdata = "3388126a%2C1773651735%2Cf0b5d%2A91",
            bili_jct = "b44752035e966894996d005e78fad189",
            buvid3 = "6A233C53-AD93-8A3E-DFE8-70BEC4EBFAB975033infoc",
            dedeuserid = "350227721"
        )
    
    def get_bv_id(self, url: str) -> str:
        """尝试提取BV号。

        如果输入的字符串中找不到有效的BV号，则会抛出 ValueError。

        Args:
            url (str): 要提取的文本或链接。

        Returns:
            str: 提取到的BV号。

        Raises:
            ValueError: 当输入的字符串中无法找到BV号时。
        """
        match = re.search(r'(BV[a-zA-Z0-9]{10})', url)
        
        if match:
            return match.group(1)
        else:
            raise ValueError(f"无法从输入的字符串中提取到BV号: '{url}'")
        
    
    async def get_video_information(self,bvid:str)->list[dict]:
        """获取一个视频的几乎所有信息

        Args:
            bvid (str): 视频的av或bv号

        Returns:
            list[dict]: 返回可直接发送的list
        """
        v = video.Video(
            bvid = bvid,
            credential = self.credential 
        )
        
        result = []
        
        info = await v.get_info()
        """视频信息"""
        online = await v.get_online()
        """在线人数"""
        try:
            chargers = await v.get_chargers()
            """视频充电用户"""
        except Exception:
            chargers = {}
            pass
        danmaku_info= await v.get_danmaku_view(0)#获取需要传入分P参数
        """弹幕信息"""
        
        result += self.parse_video_info(info)
        
        self.add_text(result,self.parse_online_info(online))
        self.add_text(result,self.parse_danmaku_info(danmaku_info))
        
        result += self.parse_charging_info(chargers)
        
        return result
    
    @staticmethod
    def add_text(result:list, text:str)->None:
        """添加text消息

        Args:
            result (list): 要添加的list
            text (str): 要添加的文本内容
        """
        result.append({
            "type": "text",
            "data": {
                "text": text
            }
        })
    
    @staticmethod
    def add_image(result:list, image_path:str)->None:
        """添加image消息

        Args:
            result (list): 要添加的list
            image_path (str): 网络地址
        """
        result.append({
            "type": "image",
            "data": {
                "file": image_path
            }
        })
    
    @staticmethod
    def parse_online_info(online:dict) -> str:
        """返回在线观看信息

        Args:
            online (dict): api获取的online信息

        Returns:
            str: 格式化字符串
        """
        return f'\n目前总共 {online["total"]} 人在观看，其中 {online["count"]} 人在网页端观看\n'
    
    @staticmethod
    def parse_danmaku_info(danmaku_dict: dict) -> str:
        """
        解析弹幕字典信息生成花哨的格式化文本
        
        Args:
            danmaku_dict: 包含弹幕信息的字典
            
        Returns:
            str: 格式化字符串
        """
        result = []
        
        result.append("🎮 弹幕信息分析报告")

        result.append("\n📊 基本信息".ljust(10, "─"))
        result.append(f"🎯 弹幕总数: {danmaku_dict.get('count', 0):,} 条")
        result.append(f"📄 页面大小: {danmaku_dict.get('dm_seg', {}).get('page_size', 0)}")
        
        result.append("\n🎪 特殊弹幕".ljust(15, "─"))
        
        command_dms = danmaku_dict.get('command_dms', [])
        for i, dm in enumerate(command_dms, 1):
            commend_type = dm.get('commend', '')
            content = dm.get('content', '')
            
            result.append(f"\n🎭 特殊弹幕 #{i} ".ljust(10, "─"))
            result.append(f"🔹 类型: {commend_type}")
            result.append(f"🔸 内容: {content}")
            result.append(f"⏰ 发起时间: {dm.get('ctime', '未知')}")
            
            extra = dm.get('extra', {})
            
            if commend_type == '#GRADE#':  # 评分弹幕
                result.append("⭐ 评分弹幕详情".ljust(10, "─"))
                result.append(f"   👥 参与人数: {extra.get('count', 0)}人")
                result.append(f"   📈 平均评分: {extra.get('avg_score', 0):.1f}分")
                result.append(f"   🎯 发起者评分: {extra.get('mid_score', 0)}分")
                
            elif commend_type == '#VOTE#':  # 投票弹幕
                result.append("🗳️ 投票弹幕详情".ljust(10, "─"))
                result.append(f"   ❓ 投票问题: {extra.get('question', '')}")
                result.append(f"   📊 总投票数: {extra.get('cnt', 0)}票")
                total_votes = extra.get('cnt', 0)
                
                options = extra.get('options', [])
                
                if total_votes == 0:
                    for opt in options:
                        result.append(f"   ✅ 选项{opt.get('idx', '')}: {opt.get('desc', '')} - {opt.get('cnt', 0)}票 (0.0%)")
                else:
                    for opt in options:
                        option_votes = opt.get('cnt', 0)
                        percentage = (option_votes / total_votes) * 100
                        result.append(f"   ✅ 选项{opt.get('idx', '')}: {opt.get('desc', '')} - {option_votes}票 ({percentage:.1f}%)")
                    
            elif commend_type == '#ATTENTION#':  # 关注弹幕
                result.append("👀 关注弹幕详情".ljust(10, "─"))
                result.append(f"   ⏱️ 显示时长: {extra.get('duration', 0):,}ms")
        
        # 图片弹幕信息
        image_dms = danmaku_dict.get('image_dms', [])
        if image_dms:
            result.append("\n🖼️ 图片弹幕".ljust(10, "─"))
            for i, img_dm in enumerate(image_dms, 1):
                result.append(f"\n🎨 图片弹幕 #{i}:")
                result.append(f"   💬 触发文本: {' | '.join(img_dm.get('texts', []))}")
                result.append(f"   🌐 图片链接: {img_dm.get('image', '')}")
        
        return "\n".join(result)

    def parse_video_info(self, video_info:dict)->list:
        """
        解析视频信息字典
        
        Args:
            video_info (dict): B站视频信息字典
            
        Returns:
            list: 格式化可以直接发送的list
        """
        try:
            bvid = video_info.get('bvid', '未知')
            title = video_info.get('title', '无标题')
            tname = video_info.get('tname', '未知分类')
            tname_v2 = video_info.get('tname_v2', '未知分类')
            desc = video_info.get('desc', '无简介')
            
            owner_info = video_info.get('owner', {})
            up_mid = owner_info.get('mid', '未知')
            up_name = owner_info.get('name', '未知UP主')
            up_img = owner_info.get('face', None)
            
            stat_info = video_info.get('stat', {})
            view = stat_info.get('view', 0)
            danmaku = stat_info.get('danmaku', 0)
            reply = stat_info.get('reply', 0)
            favorite = stat_info.get('favorite', 0)
            coin = stat_info.get('coin', 0)
            share = stat_info.get('share', 0)
            like = stat_info.get('like', 0)
            
            hot_index = (view * 0.4 + danmaku * 0.2 + reply * 0.1 + 
                        favorite * 0.1 + coin * 0.1 + share * 0.05 + like * 0.05)
            
            if view > 0:
                favorite_rate = (favorite / view) * 100
                like_rate = (like / view) * 100
                share_rate = (share / view) * 100
            else:
                favorite_rate = 0.0
                like_rate = 0.0
                share_rate = 0.0
            
            pages = video_info.get('pages', [])
            page_info = ""
            
            page_len = len(pages)
            if page_len > 1:  
                page_info = "🎬 分P信息:\n"
                for _, page in enumerate(pages[:5]):
                    page_num = page.get('page', 1)
                    part_title = page.get('part', '无标题')
                    dimension = page.get('dimension', {})
                    width = dimension.get('width', 0)
                    height = dimension.get('height', 0)
                    duration = page.get('duration', 0)
                    mins, secs = divmod(duration, 60)
                    page_info += f"  🎞️ P{page_num}: {part_title} [{mins}:{secs:02d}] ({width}x{height})\n"
            
                if page_len > 5:
                    page_info += f"  ... 还有{page_len - 5}个分P未显示\n"
            else:
                for _, page in enumerate(pages):
                    page_num = page.get('page', 1)
                    part_title = page.get('part', '无标题')
                    dimension = page.get('dimension', {})
                    width = dimension.get('width', 0)
                    height = dimension.get('height', 0)
                    duration = page.get('duration', 0)
                    mins, secs = divmod(duration, 60)
                    page_info += f"未分P单视频🎞️{page_num}: {part_title} [{mins}:{secs:02d}] ({width}x{height})\n"
            
            result_1 = f"""
📺 视频信息:
🏷️  视频纯净链接:https://www.bilibili.com/video/{bvid}/
🏷️  标题: {title}
🆔  BV号: {bvid}
📂  主分类: {tname}
🗂️  子分类: {tname_v2}
📝  简介: {desc[:50]}{'...' if len(desc) > 50 else ''}

👤 UP主信息:
🧑‍💻  UP主: {up_name}
🔑  UID: {up_mid}
🖼️  头像: """
            result_2 = f"""

📊 统计数据:
👁️   播放: {view:,}
💬  弹幕: {danmaku:,}
💭  评论: {reply:,}
❤️   收藏: {favorite:,}(收藏率: {favorite_rate:.2f}%)
🪙  硬币: {coin:,}
📤  分享: {share:,}(分享率: {share_rate:.2f}%)
👍   点赞: {like:,}(点赞率: {like_rate:.2f}%)
🔥  热度评分: {hot_index:,.0f}

{page_info}
        """
            return_result = []
            if up_img is None:
                self.add_text(return_result,result_1+result_2)
            else:
                self.add_text(return_result,result_1)
                self.add_image(return_result,up_img)
                self.add_text(return_result,result_2)
            
            return return_result

        except Exception as e:
            return f"❌ 解析视频信息时出错: {str(e)}"

    def parse_charging_info(self, charging_info:dict)->list[dict]:
        """
        解析B站充电信息字典,返回人类可读的字符串
        
        Args:
            charging_info (dict): B站充电信息字典
            
        Returns:
            list: 返回图文混合的list
        """
        if not charging_info:
            return []
        try:
            total_count = charging_info.get('total_count', 0)
            count = charging_info.get('count', 0)
            
            charging_list = charging_info.get('list', [])
            
            return_result = []
            
            result = f"""
✨⚡️✨ B站充电信息解析 ✨⚡️✨

🎯 统计信息:
🌟 总充电人数: {total_count:,}
📊 当前显示人数: {count:,}

💫 充电用户列表 (最多显示5位):
"""
            
            rank_emojis = ["🥇", "🥈", "🥉", "🎖️", "🎖️"]
            
            display_count = min(len(charging_list), 5)
            for i in range(display_count):
                user = charging_list[i]
                uname = user.get('uname', '未知用户')
                message = user.get('message', '无留言')
                avatar = user.get('avatar',None)
                rank = user.get('rank', 0)
                
                vip_info = user.get('vip_info', {})
                vip_type = vip_info.get('vipType', 0)
                vip_status = vip_info.get('vipStatus', 0)
                
                vip_status_text = "👤 普通用户"
                if vip_status == 1:
                    if vip_type == 1:
                        vip_status_text = "💎 月度大会员"
                    elif vip_type == 2:
                        vip_status_text = "💎✨ 年度大会员"
                
                emoji = rank_emojis[i] if i < len(rank_emojis) else "🎖️"
                
                result += f"\n{emoji} 第{rank}名: {uname}"
                
                if avatar is None:
                    result += "\n   🖼️ 头像:获取头像失败"
                else:
                    self.add_text(return_result,result)
                    self.add_image(return_result,avatar)
                    result = ""
                
                result += f"\n   🔹 {vip_status_text}"
                if message and message != '':
                    result += f"\n   💬 留言: {message}"
            
            if len(charging_list) > 5:
                result += f"\n\n   ... 还有 {len(charging_list) - 5} 位充电用户未显示 ✨"
            
            self.add_text(return_result,result)
            
            return return_result
            
        except Exception as e:
            return f"❌ 解析充电信息时出错: {str(e)}"
    
    def parse_video_info_basic(self, video_info: dict) -> list:
        """解析视频基本信息（不含统计数据）"""
        try:
            bvid = video_info.get('bvid', '未知')
            title = video_info.get('title', '无标题')
            tname = video_info.get('tname', '未知分类')
            tname_v2 = video_info.get('tname_v2', '未知分类')
            desc = video_info.get('desc', '无简介')
            
            owner_info = video_info.get('owner', {})
            up_mid = owner_info.get('mid', '未知')
            up_name = owner_info.get('name', '未知UP主')
            up_img = owner_info.get('face', None)
            
            pages = video_info.get('pages', [])
            page_info = ""
            
            if len(pages) > 1:
                page_info = "🎬 分P信息:\n"

                for i, page in enumerate(pages[:5]):
                    page_num = page.get('page', 1)
                    part_title = page.get('part', '无标题')
                    dimension = page.get('dimension', {})
                    width = dimension.get('width', 0)
                    height = dimension.get('height', 0)
                    duration = page.get('duration', 0)
                    mins, secs = divmod(duration, 60)
                    page_info += f"  🎞️ P{page_num}: {part_title} [{mins}:{secs:02d}] ({width}x{height})\n"
                
                if len(pages) > 5:
                    page_info += f"  ... 还有{len(pages) - 5}个分P未显示\n"
            else:
                for _, page in enumerate(pages):
                    page_num = page.get('page', 1)
                    part_title = page.get('part', '无标题')
                    dimension = page.get('dimension', {})
                    width = dimension.get('width', 0)
                    height = dimension.get('height', 0)
                    duration = page.get('duration', 0)
                    mins, secs = divmod(duration, 60)
                    page_info += f"未分P单视频🎞️{page_num}: {part_title} [{mins}:{secs:02d}] ({width}x{height})\n"
            
            basic_text = f"""
📺 视频基本信息:
🏷️  视频纯净链接:https://www.bilibili.com/video/{bvid}/
🏷️  标题: {title}
🆔  BV号: {bvid}
📂  主分类: {tname}
🗂️  子分类: {tname_v2}
📝  简介: {desc[:100]}{'...' if len(desc) > 100 else ''}

👤 UP主信息:
🧑‍💻  UP主: {up_name}
🔑  UID: {up_mid}
🖼️  头像: """
            
            result = []
            if up_img is None:
                self.add_text(result, basic_text + (f"\n{page_info}" if page_info else ""))
            else:
                self.add_text(result, basic_text)
                self.add_image(result, up_img)
                self.add_text(result, f"{page_info}")
            
            return result
            
        except Exception as e:
            return [{"type": "text", "data": {"text": f"❌ 解析基本信息时出错: {str(e)}"}}]
    
    
    def parse_video_stats(self, video_info: dict) -> str:
        """解析视频统计信息"""
        try:
            stat_info = video_info.get('stat', {})
            view = stat_info.get('view', 0)
            danmaku = stat_info.get('danmaku', 0)
            reply = stat_info.get('reply', 0)
            favorite = stat_info.get('favorite', 0)
            coin = stat_info.get('coin', 0)
            share = stat_info.get('share', 0)
            like = stat_info.get('like', 0)
            
            hot_index = (view * 0.4 + danmaku * 0.2 + reply * 0.1 + 
                        favorite * 0.1 + coin * 0.1 + share * 0.05 + like * 0.05)
            
            if view > 0:
                favorite_rate = (favorite / view) * 100
                like_rate = (like / view) * 100
                share_rate = (share / view) * 100
            else:
                favorite_rate = 0.0
                like_rate = 0.0
                share_rate = 0.0
            
            return f"""
📊 统计数据:
👁️   播放: {view:,}
💬  弹幕: {danmaku:,}
💭  评论: {reply:,}
❤️   收藏: {favorite:,} (收藏率: {favorite_rate:.2f}%)
🪙  硬币: {coin:,}
📤  分享: {share:,} (分享率: {share_rate:.2f}%)
👍   点赞: {like:,} (点赞率: {like_rate:.2f}%)
🔥  热度评分: {hot_index:,.0f}
            """
            
        except Exception as e:
            return f"❌ 解析统计信息时出错: {str(e)}"


async def main() -> None:
    from pprint import pp
    
    b = BiliBiliCrawler()
    bvid = "adsadasdassBV17fpczGEeoadsadasds"
    # print()
    # bvid = "BV17fpczGEeo"
    _dict = await b.get_video_information(b.get_bv_id(bvid))
    pp(_dict)

    


# if __name__ == "__main__":
#     asyncio.run(main())