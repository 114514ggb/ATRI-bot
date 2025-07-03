from ..Basics import Basics,Command
import asyncio
import random
import httpx
import re

class itemAction():
    """根据需要执行对应的操作"""
    _lock_async = asyncio.Lock()
    
    def __init__(self):
        self.basics = Basics()
        self.listeners = [
            self.poke,
            self.manage_add_group,
            self.listen_music
            # self.initiative_chat,
        ]
        """监听器list"""

    async def main(self,group_ID, data):
        """反射主函数"""
        for item in self.listeners:
            await item(group_ID, data)
            
        return False
        
    async def poke(self,group_ID, data):
        """戳一戳的反馈"""
        if 'sub_type' in data and data['sub_type'] == "poke" and data['self_id'] == data['target_id']:
            reactivity_list = [
                "你揉我干嘛？哎呦( •̀ ω •́ )","不要揉了啊,痛吖喵!","呜喵！",
                "( •̀ ω •́ )喵~","喵~(〃ω〃)","喵！（炸毛）","我的天！你居然揉我！喵！",
                "(〃ω〃)喵~","你揉我干嘛！自己揉自己啊！喵！","揉脸打咩！(〃ω〃)喵~",
                "喵~再揉脸要坏掉了","尾巴要秃了啦！快住手喵！(＞﹏＜)","别揉耳朵啦！会聋掉的喵！(｀Д´)",
                "揉揉按摩禁止！会痒到炸毛的喵！(//∇//)","喵~请继续！(ฅ´ω`ฅ)","再揉收费了哦！一次50喵！这样就有钱吃小鱼干了",
                "咕噜咕噜~算你手法合格喵~(=｀ω´=)","肚子不能碰！会踢到你的喵！(╬ Ò﹏Ó)","爪垫是禁区！再摸咬你哦！(｀ε´#)",
                "喵嗷！再揉就收双倍小鱼干！(￣^￣)ゞ","轻点呀笨蛋！毛要打结啦喵！(>_<)","呼噜...勉强允许揉三分钟喵(´-ω-`)",
                "喵！偷袭肚子太过分了！(⁄ ⁄•⁄ω⁄•⁄ ⁄)","耳朵敏感啦！停下喵！(,,#ﾟДﾟ)","尾巴毛要掉光啦！赔我罐头喵！(;´༎ຶД༎ຶ`)",
                "咕噜...下巴这里...可以多揉揉喵(ฅ>ω<*ฅ)","喵？！谁准你揉头顶王冠的！(╯‵□′)╯︵┻━┻","揉背可以...但别停喵~（眯眼瘫倒）",
                "爪爪不能捏！要留指甲抓沙发的喵！(๑•̀ㅂ•́)و✧","呜...脖子痒到笑出猪叫喵！(≧∇≦)ﾉ",
                "再揉就启动喵喵拳了哦！(ง •_•)ง","小鱼干+罐罐=允许揉十分钟喵(♡˙︶˙♡)","喵！肚皮是陷阱！快缩手！(ﾟДﾟ≡ﾟДﾟ)",
                "咕噜噜...人类手法有进步喵（摊成猫饼）","尾巴不是逗猫棒！别拽喵！(｀Д´*)","后颈肉禁止！当我是小奶猫吗！ヽ(≧Д≦)ノ",
                "喵呜~左边耳朵也要揉揉！(∗❛ัᴗ❛ั∗)","炸毛MAX！静电要劈到你啦喵！(ﾉ○Д○)ﾉ","揉归揉...敢拍照就删内存喵！(¬_¬ )",
                "呼噜...今天特许免费服务喵(^・ω・^ )","喵！揉太用力灵魂出窍啦！(⊙_⊙;)","两脚兽适可而止啊！毛要秃了喵！(；一_一)",
                "咕噜...其实...有点舒服喵（小声）(⁄ ⁄>⁄ ▽⁄<⁄ ⁄)","爪心肉垫是VIP区域！加罐罐才能摸喵！(๑¯∀¯๑)",
                "喵嗷！再揉就变身猫球滚走啦！(≡・ x ・≡)","后背按摩...可以打五星喵☆(≧∀≦*)ﾉ",
                "停手！再揉触发喵式自动驾驶（瘫倒）Zzz...","胡子不能碰！导航会失灵的喵！(ﾟロﾟ;)",
                "今日揉揉额度用完啦！明天请早喵！(⌒▽⌒)☆","喵！检测到非法撸猫！罚款十根猫条！(╯▔皿▔)╯",
                "再揉服务器要未响应了!喵！"
            ]
            text = random.choice(reactivity_list)

            await self.basics.QQ_send_message.send_group_message(group_ID,text)
            await self.basics.QQ_send_message.send_group_poke(group_ID,data['user_id'])
            return True
        
        return False
    
    async def initiative_chat(self,group_ID, data):
        """自动判断回复群消息"""
        if group_ID == 235984211 and "message" in data:
            async with self._lock_async:
                ai_response = await self.basics.AI_interaction.auto_response.chat_main(
                    data=data,
                    user_text = Command.data_processing_text(data)
                    )
                if ai_response:
                    for message in ai_response.split("\\"):
                        await self.basics.QQ_send_message.send_group_message(group_ID,message)
                        await asyncio.sleep(0.8) #模拟输入延迟
                    return True
                
        return False
    
    async def manage_add_group(self,group_ID, data):
        """管理群事件"""
        white_list_gropup:dict = {
            1038698883 : "问题：亚托莉机器人的英文名\n答案：ATRI"
        }
        """白名单群key:群号 value:请求加群的验证信息"""

        if 'sub_type' in data and group_ID in white_list_gropup:
            
            sub_type = data['sub_type']
            user_id = data['user_id']
            
            if sub_type == "add":
                
                if data['comment'] == white_list_gropup[group_ID]: 
                    await self.basics.QQ_send_message.set_group_add_request(data['flag'],True)
                else:
                    await self.basics.QQ_send_message.send_group_message(group_ID,f"有人申请加群了!\n{data['comment']}")
                    
            elif sub_type == "approve":
                
                await self.basics.QQ_send_message.send_group_message(group_ID,f"欢迎[CQ:at,qq={user_id}]加入群聊！")

            elif sub_type == 'kick':
                
               await self.basics.QQ_send_message.send_group_message(group_ID,f"[CQ:at,qq={user_id}]被管理员{data['operator_id']}踢出群聊！")
               
            elif sub_type == 'leave':
                
                await self.basics.QQ_send_message.send_group_message(group_ID,f"[CQ:at,qq={user_id}]退出群聊！")
                
        return False
    
    async def listen_music(self,group_ID, data:dict):
        """掌管群听歌的"""
        
        async def search_music(keywords, limit=5)->list[dict]:
            """
            网易云音乐搜索接口，返回歌曲信息列表
            
            Args:
                :keywords 搜索关键词
                :limit 返回数量
                
            Returns:
                歌曲名和id
                [{'name': '冬の花', 'id': 1345485069},...]
            """
            url = 'https://music.163.com/api/cloudsearch/pc'
            data = {'s': keywords, 'type': 1, 'limit': limit}
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://music.163.com/'
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, headers=headers)
            data = response.json()
            print(data)
            return [{"name":v["name"],"id":v["id"]}  for v in data['result'].get('songs',[])]
        
        pattern = r"^来首(.{1,50})$"
        
        if match := re.match(pattern,data.get("raw_message","")):
            if music_lsit := await search_music(match.group(1)):
                await self.basics.QQ_send_message.send_group_music(
                    group_ID,
                    "163",
                    str(music_lsit[0]["id"])
                )
        
        return False
        
        



    def add_listener(self, callback):
        """添加监听器"""
        self.listeners.append(callback)
        return True

    def remove_listener(self, callback):
        """移除监听器"""
        try:
            self.listeners.remove(callback)
            return True
        except ValueError:
            return False