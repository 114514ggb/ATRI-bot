from .Basics import *
from .itemAction.action_main import itemAction
import random

class textMonitoring():
    """监控指定文本或者字段"""
    def __init__(self):
        self.itemAction = itemAction()
        self.basics = Basics()

    async def monitoring(self, text, qq_TestGroup,data):
        """监控并产生对应的反映"""
        if await self.alikeRespond(text, qq_TestGroup):
            return True
        elif await self.haveRespond(text, qq_TestGroup):
            return True
        elif await self.monitoringItem(qq_TestGroup,data):
            return True
        return False

    async def alikeRespond(self, text, qq_TestGroup):
        """精确匹配，匹配字段一样就反应"""
        if text in self.monitoring_alike_list.keys():

            if text in self.Frequently_used_words_list and self.basics.Chance.judgeChance(33):#有在常用词列表里，并且随机到33%的概率不反应
                return True
            
            await self.sendHandle(qq_TestGroup,self.monitoring_alike_list[text])
            return True
        return False

    async def haveRespond(self, text, qq_TestGroup):
        """模糊匹配,有匹配字段就反应"""
        for key in self.monitoring_have_list:
            if key in text:
                await self.sendHandle(qq_TestGroup,self.monitoring_have_list[key])
                return True
            
        return False
    
    async def monitoringItem(self, qq_TestGroup, data):
        """监控指定的字段"""
        return await self.itemAction.main(qq_TestGroup, data)

        

    async def sendHandle(self, qq_TestGroup, handle):
        """发送文本的对应的反应"""
        type,document = handle
        document = random.choice(document)

        if type == "text":
            await self.basics.QQ_send_message.send_group_message(qq_TestGroup, document)
        elif type == "img":
            await self.basics.QQ_send_message.send_group_pictures(qq_TestGroup, document, True)
        elif type == "audio":
            await self.basics.QQ_send_message.send_group_audio(qq_TestGroup, document, True)

    monitoring_alike_list = {
        "?": ["img",["ATRI_问号1.jpg","ATRI_问号2.jpg","ATRI_问号3.jpg"]],
        "草": ["text",["草"]],
        "艹": ["text",["艹"]],
        "怪了": ["text",["怪了"]],
        "贴贴": ["text",["贴贴～","贴贴！","不给你贴","亚达哟,不给","我贴"]],
        "🤔": ["text",["🤔"]],
        "😡": ["text",["😡"]],
        "诶": ["text",["诶"]],
        "哎": ["text",["哎"]],
        "乐": ["text",["乐"]],
        "早": ["audio",["早上好.mp3","唔......吧唧......早上.......哈啊啊~~......早上好......夏生先.......mp3"]],
        "233": ["text",["233"]],
        "萝卜子": ["img",['ATRI_鸭子走.gif','ATRI_左右.gif',"ATRI_呆望.jpg"]],
        "螃蟹": ["img",["ATRI_见到螃蟹.gif"]],
        "摸头": ["img",["ATRI_摸头.gif","ATRI_摸头1.gif","ATRI_摸头2.gif"]],
        "投食":["img",["ATRI_吃瓜.gif"]],
        "骂我":["img",["你太变态.jpg","ATRI_不行.gif"]],
        "踩我":["text",["请不要这样！"]],
        "爱你":["img",["ATRI_得意.gif","ATRI_抛星星眼.gif","ATRI_ 亲亲.gif","ATRI_ 啊？.gif","ATRI_自我陶醉.gif","ATRI_爱心.gif"]],
        "睡觉": ["img",["ATRI_请睡觉.jpg","ATRI_睡觉.jpg"]],
        "转圈":["img",["ATRI_转圈.gif"]],
        "我有一个想法":["img",["ATRI_我有一个想法.jpg"]],
        "笑":["img",["ATRI_笑.jpg","ATRI_笑1.jpg"]],
        "晚安":["text",["晚安，做个好梦~","晚安哦！","晚安，睡个好觉~"]],
        "早安": ["text",["早上好！","早上好呀！","早上好，今天也要元气满满哦！"]],
        "出警":["img",["ATRI_出警.jpg"]],
        "支持":["text",["支持"]],
    }
    '''精确匹配列表'''

    monitoring_have_list = {
        "不是哥们": ["text",["不是哥们?"]],
        "喵": ["text",["喵","喵喵!","喵喵喵!","喵泥格咪的！","我喵","喵？","我喵喵喵!","猫ですよ","你是猫吗？喵!"]],
        "逆天": ["text",["逆天!","逆天"]],
        "难蚌": ["text",["难蚌"]],
        "好耶": ["img", ["ATRI_好耶.jpg"]],
        "高性能": ["img",["ATRI_高性能.png","ATRI_得意.gif","ATRI_自我陶醉.gif"]],
        "Ciallo": ["img",["ATRI_Ciallo.jpg"]],
        "废物":["img",["ATRI_欺负我你能得到什么.jpg","ATRI_ 气鼓鼓.gif","ATRI_生气到爆.gif","ATRI_怎么你了.jpg","ATRI_违反机器人保护法.jpg"]],
        "亚托莉": ["img",["ATRI_左右摆头.gif","ATRI_抛星星眼.gif","ATRI_探头.png"]],
        "变态": ["img",["ATRI_变态.gif","你太变态.jpg"]],
        "哼哼啊": ["img",["ATRI_恶臭1145.jpg"]],
        "圣诞": ["img",["ATRI_过圣诞.gif"]],
        "有意思": ["img",["ATRI_有点意思.gif"]],
        "嘲讽": ["img",["ATRI_嘲笑.jpg","ATRI_下蹲.gif"]],
        "哈基米": ["audio",["哈基米.mp3"]],
    }
    '''模糊匹配列表'''

    Frequently_used_words_list = [
        "草","😡","?"
    ]
    "常用词汇列表,66%几率回复"