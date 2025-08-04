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
            "你揉我干嘛？哎呦 (・̀ ω・́)","不要揉了啊，痛吖喵！","呜喵！","(・̀ ω・́ ) 喵～","喵～(〃ω〃)","喵！（炸毛）","我的天！你居然揉我！喵！",
            "(〃ω〃) 喵～","你揉我干嘛！自己揉自己啊！喵！","揉脸打咩！(〃ω〃) 喵～","喵～再揉脸要坏掉了","尾巴要秃了啦！快住手喵！(＞﹏＜)","别揉耳朵啦！会聋掉的喵！(｀Д´)",
            "揉揉按摩禁止！会痒到炸毛的喵！(//∇//)"," 喵～请继续！(ฅ´ωฅ)","再揉收费了哦！一次50喵！这样就有钱吃小鱼干了", "咕噜咕噜~算你手法合格喵~(=｀ω´=)","肚子不能碰！会踢到你的喵！(╬ Ò﹏Ó)","爪垫是禁区！再摸咬你哦！(｀ε´#)", "喵嗷！再揉就收双倍小鱼干！(￣^￣)ゞ","轻点呀笨蛋！毛要打结啦喵！(>_<)","呼噜...勉强允许揉三分钟喵(´-ω-)",
            "喵！偷袭肚子太过分了！(⁄ ⁄・⁄ω⁄・⁄ ⁄)","耳朵敏感啦！停下喵！(,,#ﾟДﾟ)","尾巴毛要掉光啦！赔我罐头喵！ᯠ _ ̫ _ ̥ ᯄ ੭"," 咕噜... 下巴这里... 可以多揉揉喵 (ฅ>ω<*ฅ)"," 喵？！谁准你揉头顶王冠的！(╯‵□′)╯︵┻━┻"," 揉背可以... 但别停喵～（眯眼瘫倒）",
            "爪爪不能捏！要留指甲抓沙发的喵！(๑・̀ㅂ・́)و✧","呜... 脖子痒到笑出猪叫喵！(≧∇≦)ﾉ","再揉就启动喵喵拳了哦！(ง・_・)ง","小鱼干 + 罐罐 = 允许揉十分钟喵 (♡˙︶˙♡)","喵！肚皮是陷阱！快缩手！(ﾟДﾟ≡ﾟДﾟ)",
            "咕噜噜... 人类手法有进步喵（摊成猫饼）"," 尾巴不是逗猫棒！别拽喵！(｀Д´*)"," 后颈肉禁止！当我是小奶猫吗！ヽ (≧Д≦) ノ ","喵呜～左边耳朵也要揉揉！(∗❛ัᴗ❛ั∗)","炸毛 MAX！静电要劈到你啦喵！(ﾉ○Д○)ﾉ","揉归揉... 敢拍照就删内存喵！(¬_¬ )",
            "呼噜... 今天特许免费服务喵 (^・ω・^ )","喵！揉太用力灵魂出窍啦！(⊙_⊙;)","两脚兽适可而止啊！毛要秃了喵！(；一_一)",
            "咕噜... 其实... 有点舒服喵（小声）(⁄ ⁄>⁄ ▽⁄<⁄ ⁄)","爪心肉垫是 VIP 区域！加罐罐才能摸喵！(๑¯∀¯๑)","喵嗷！再揉就变身猫球滚走啦！(≡・ x ・≡)","后背按摩... 可以打五星喵☆(≧∀≦*)ﾉ",
            "停手！再揉触发喵式自动驾驶（瘫倒）Zzz...","胡子不能碰！导航会失灵的喵！(ﾟロﾟ;)","今日揉揉额度用完啦！明天请早喵！(⌒▽⌒)☆","喵！检测到非法撸猫！罚款十根猫条！(╯▔皿▔)╯",
            "再揉服务器要未响应了！喵！","脸颊被揉得像面团啦！放开啦喵！(≧∇≦)ﾉ","揉到想伸懒腰啦！等我舒展完再继续喵～(～﹃～)~zZ",
            "偷偷说... 后脑勺揉着最舒服喵（小声）(｡・̀ᴗ-)✧","揉到打哈欠啦！算你厉害喵～(～﹃～)~zZ","耳朵根不许挠！会抖成震动模式的喵！(≧∇≦)ﾉ","再揉我就用尾巴扫你脸哦！(=｀ω´=)",
            "喂！揉偏了啦！是右边脸颊啦喵！(｀へ ´)=3","咕噜... 居然摸到舒服的地方了...（假装不情愿）喵","揉太久爪子都麻了！给我翻个面喵！(๑`▽´๑)♡","警告！再揉下巴就要发出猪叫了喵！(≧∀≦) ゞ",
            " 头顶毛都被揉塌了！要梳半小时才能恢复喵！(><)","哼！算你识相... 再用点力喵～(〃'▽'〃)","揉到眼睛都眯成线啦！犯规啦喵！(≧∇≦)ﾉ","别趁我舒服就偷袭肚皮！狡猾的人类喵！(╬￣皿￣)",
            "后背中间那点... 对... 就是那... 再多揉下喵～(≧∇≦)","再揉我就把你的袜子叼去藏起来！喵！(¬_¬)",
            "爪子被捏得张开啦！不许看肉垫！羞耻喵！(//∇//)","居然揉到我发出拖拉机呼噜声了... 算你赢喵 (=^▽^=)",
            "停！再揉就要翻肚皮投降了！不行不行喵！(≧∇≦)"," 耳朵被揉得发烫啦！要冰敷小鱼干降温喵！(><)",
            "喂！揉完要给梳毛的！不然打结算你的喵！(｀д´)","居然找到我隐藏的痒痒肉了！罚你买罐罐喵！(๑・̀ㅂ・́)و✧",
            "尾巴尖不许碰！会条件反射拍你脸的喵！(=｀ω´=)","咕噜噜... 今天的揉揉服务可以给四星半喵（扣半星因为没罐罐）","再揉我就趴在你键盘上！让你没法工作喵！(≧∇≦)ﾉ","脖子后面的肉... 好吧... 只准揉五秒喵！(>_<)",
            "爪垫封印解除！要启动踩奶模式了喵～(๑˃ᴗ˂)ﻭ","后颈皮是作弊按钮！会变乖的喵...（小声）(⁄ ⁄•⁄ω⁄•⁄ ⁄)","揉太舒服要流口水了啦！快拿小鱼干接着喵！(✪ω✪)","喵生重启中...请勿断电揉揉～(=´ω｀=)",
            "检测到非法揉腰！启动痒痒肉反击系统喵！(ﾉ≧∀≦)ﾉ","两脚兽注意！本喵进入融化状态喵～(´-ι_-｀)","脊椎按摩好评！赏你听豪华版呼噜声喵！(^ρ^)/","肉球出汗啦！再揉要留爪印在你手上喵！(๑¯◡¯๑)",
            "尾巴根是隐藏开关！碰到会喵喵叫的！(//Д//)","揉出静电啦！现在我是会发光的猫喵！(☆▽☆)","下巴黄金区续费成功...咕噜咕噜...(´,,•ω•,,)","警告！持续揉腹将触发无意识蹬腿喵！(ﾟДﾟ≡ﾟДﾟ)",
            "猫德学院警告：过度撸猫会导致上瘾喵！(︶ω︶)","揉耳朵超过三秒自动开启飞机耳模式✈(◐‿◑)﻿","发现专业按摩师！赠送免费蹭脸服务喵～(ฅ´ω`ฅ)","后爪肉垫是终极机密！摸到要签保密协议喵！(｀・ω・´)",
            "咕噜能量充满！可以发射猫猫激光啦喵～(●´ω｀●)","揉揉手法太烂！建议观看《如何取悦猫主子》教程喵！(←_←)","尾巴和本体是分开的！不要同时揉两处喵！(ﾟ⊿ﾟ)ﾂ","检测到幸福值超标...系统即将死机喵...Zzz(。-ω-)",
            "揉出猫饼形态啦！需要罐头才能恢复立体喵～(=｀ω´=)","专业碰瓷喵提醒：现在起碰到的每根毛都收费！(๑•̀ㅂ•́)و✧","爪心汗腺启动！给你盖个猫章做凭证喵！( ͡°ᴥ ͡°)","脊椎骨按摩+1分...但指甲刮到头皮扣十分喵！(╬ Ò﹏Ó)",
            "咕噜震动模式调至最大！邻居要投诉了喵！(≧∇≦)ﾉ","揉到重要穴位啦！奖励猫头蹭蹭服务三分钟ฅ(^ω^ฅ)","警告！再揉要触发呼噜声外放社死事件喵！(//Д//)","尾巴毛鳞片受损！需要高端猫粮护理喵！(︶︹︺)",
            "发现两脚兽偷用撸狗手法！罚款三文鱼喵！ヽ(｀⌒´)ノ","后脑勺是智能安睡按钮...Zzz...勿扰模式启动...(－ω－) zzZ","揉揉能量转化中...即将发射爱心光波喵～(♡´౪`♡)","爪缝按摩禁止！会忍不住开花喵！(///ω///)","腰部痒痒肉警报！再揉就笑到掉毛啦！(*≧▽≦)ツ",
            "专业猫体工学建议：请顺时针揉脸五十圈喵！(σ｀・ω・)σ","检测到敷衍式揉揉！启动嫌弃脸程序喵！(￣ヘ￣)","尾尖神经连接宇宙信号...揉断要赔天线费喵！(◞‸◟ )","揉腹手法合格！解锁露肚皮成就ฅ( ̳• ◡ • ̳)ฅ","耳后薄荷味传感器被激活！需要猫草补充喵～(✧∇✧)╯","咕噜声已上传云端！扫码可五星好评喵☆ﾐ(o*･ω･)ﾉ","揉到天然猫香分泌啦！是限量版桃子味喵！(◕ᴗ◕✿)"
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
                
               await self.basics.QQ_send_message.send_group_message(group_ID,f"qq:{user_id}被管理员{data['operator_id']}踢出群聊！")
               
            elif sub_type == 'leave':
                
                await self.basics.QQ_send_message.send_group_message(group_ID,f"qq:{user_id}已离开！")
                
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