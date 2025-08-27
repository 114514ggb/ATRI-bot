from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.event_trigger.string_respond import string_response
from atribot.core.service_container import container
from logging import Logger
from typing import Dict
from enum import Enum
import random


class EventType(Enum):
    """事件类型枚举"""
    META = 'meta_event'
    """元事件"""
    REQUEST = 'request'             
    """请求事件"""
    NOTICE = 'notice'              
    """通知事件"""
    MESSAGE = 'message'            
    """消息事件"""
    MESSAGE_SENT = 'message_sent'   
    """消息发送事件"""

class EventTrigger:
    """事件简单分类触发"""
    
    def __init__(self):        
        self.log:Logger = container.get("log")
        self.send_message:qq_send_message = container.get("SendMessage")
        self.str_response = string_response()
        
        self.message_processors = [
            (lambda data: True,self.str_response.manage)
        ]
        """消息事件"""
        
        self.notice_processors = [
            (lambda data: data.get('sub_type') in ["approve",'kick','leave'], self.manage_group_inform),
            (lambda data: data.get('sub_type') == "poke" and data['self_id'] == data['target_id'],self.poke)
        ]
        """通知事件"""
        
        self.request_processors = [
            (lambda data: data.get('sub_type') == "add", self.manage_add_group)
        ]
        """请求事件"""
        
        self.processors = {
            EventType.MESSAGE: self.message_processors,
            EventType.NOTICE: self.notice_processors,
            EventType.REQUEST: self.request_processors
        }
    
    async def dispatch(self, data: Dict, group_id:int) -> None:
        """分发事件到不同处理器"""
        post_type = data.get('post_type')
        event_type = EventType(post_type)
        
        processors = self.processors.get(event_type, [])
        
        for condition, handler in processors:
            if condition(data):
                try:
                    await handler(group_id, data)
                except Exception as e:
                    self.log.error(f"处理器执行失败: {handler.__name__}, 错误: {e}")
    
    
    async def manage_group_inform(self,group_id, data):
        """管理群通知事件"""

        sub_type = data['sub_type']
        user_id = data['user_id']
                
        if sub_type == "approve":
            
            await self.send_message.send_group_message(group_id,f"欢迎[CQ:at,qq={user_id}]加入群聊！")

        elif sub_type == 'kick':
            
            await self.send_message.send_group_message(group_id,f"qq:{user_id}被管理员{data['operator_id']}踢出群聊！")
            
        elif sub_type == 'leave':
            
            await self.send_message.send_group_message(group_id,f"qq:{user_id}已离开！")
            
    async def manage_add_group(self,group_id, data):
        """管理加群的请求"""
        white_list_gropup:dict = {
            1038698883 : "问题：亚托莉机器人的英文名\n答案：ATRI",
            2169027872 : "",
        }
        """白名单群key:群号 value:请求加群的验证信息"""
        
        if group_id in white_list_gropup and data['comment'] == white_list_gropup[group_id]: 
            await self.send_message.set_group_add_request(data['flag'],True)
        else:
            await self.send_message.send_group_message(group_id,f"有人申请加群了!\n验证信息:\n{data['comment']}") 


    async def poke(self,group_id, data):
        """戳一戳的反馈"""
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

        await self.send_message.send_group_message(group_id,text)
        await self.send_message.send_group_poke(group_id,data['user_id'])

    