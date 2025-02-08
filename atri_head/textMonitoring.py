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

            if text in self.Frequently_used_words_list and self.basics.Chance.judgeChance(50):#有在常用词列表里，并且随机到50%的概率不反应
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
        type,document = random.choice(handle)
        document = random.choice(document)

        if type == "text":
            await self.basics.QQ_send_message.send_group_message(qq_TestGroup, document)
        elif type == "img":
            await self.basics.QQ_send_message.send_group_pictures(qq_TestGroup, document, True)
        elif type == "audio":
            await self.basics.QQ_send_message.send_group_audio(qq_TestGroup, document, True)

    monitoring_alike_list = {
        "?": [["img",["ATRI_问号1.jpg","ATRI_问号2.jpg","ATRI_问号3.jpg","ATRI_问号4.png","ATRI_问号5.jpg"]],["text",["?"]]],
        "草": [["text",["草"]]],
        "艹": [["text",["艹"]]],
        "怪了": [["text",["怪了"]]],
        "贴贴": [["text",["贴贴～","贴贴！","不给你贴","亚达哟,不给","我贴～～","贴贴,好啊！","要贴创口贴吗？那我帮你贴一个吧"]]],
        "😰": [["text",["😰"]]],
        "😨": [["text",["😨"]]],
        "😱": [["text",["😱"]]],
        "🌿": [["text",["🌿"]]],
        "诶": [["text",["诶","为什么叹气呢？"]]],
        "哎": [["text",["哎"]]],
        "乐": [["text",["乐","乐！"]]],
        "233": [["text",["233"]]],
        "萝卜子": [["img",['ATRI_鸭子走.gif','ATRI_左右.gif',"ATRI_呆望.jpg","ATRI_不要1.gif"]]],
        "螃蟹": [["img",["ATRI_见到螃蟹.gif"]],["text",["亚托莉最喜欢吃螃蟹了~"]]],
        "摸头": [["img",["ATRI_摸头.gif","ATRI_摸头1.gif","ATRI_摸头2.gif","ATRI_摸头.jpg"]]],
        "早": [["audio",["早上好.mp3","唔......吧唧......早上.......哈啊啊~~......早上好......夏生先.......mp3"]],["text",["早哦！","早上好！", "早上好呀！", "早上好，今天也要元气满满哦~","おはようございます!"]]],
        "睡了":[["text",["晚安，做个好梦~","晚安哦！","晚安，睡个好觉~","晚安！我也要睡觉啦~"]]],        
        "投食":[["img",["ATRI_吃瓜.gif","ATRI_小虎牙咬面包.jpg"]]],
        "骂我":[["img",["你太变态.jpg","ATRI_不行.gif"]]],
        "踩我":[["text",["请不要这样！"]]],
        "爱你":[["img",["ATRI_得意.gif","ATRI_抛星星眼.gif","ATRI_ 亲亲.gif","ATRI_ 啊？.gif","ATRI_自我陶醉.gif","ATRI_爱心.gif"]]],
        "亲亲":[["img",["ATRI_得意.gif","ATRI_抛星星眼.gif","ATRI_ 亲亲.gif","ATRI_ 啊？.gif","ATRI_自我陶醉.gif","ATRI_爱心.gif"]]],
        "睡觉": [["img",["ATRI_请睡觉.jpg","ATRI_睡觉.jpg"]]],
        "转圈":[["img",["ATRI_转圈.gif","ATRI_原地转圈.gif"]]],
        "我有一个想法":[["img",["ATRI_我有一个想法.jpg"]]],
        "笑":[["img",["ATRI_笑.jpg","ATRI_笑1.jpg"]]],
        "出警":[["img",["ATRI_出警.jpg"]]],
        "支持":[["text",["支持"]]],
        "憨批":[["img",["ATRI_憨批.gif"]]],
        "确实":[["text",["确实","雀食"]]],
        "亚门":[["img",["ATRI_亚门.jpg","ATRI_亚门1.jpg"]]],
        "悲": [["text",["悲"]]],
        "好看": [["text",["好看!"]]],
        "出拳": [["img",["ATRI_吃我一拳.gif"]]],
        "也是": [["text",["也是"]]],
        "我的天": [["text",["我的天!"]]],
        "true": [["img",["ATRI_正确的.jpg"]]],
        "原神": [["text",["启动喵！","启动","玩原玩的？喵！"]]],
        "抱抱": [["text",["抱抱~","只有夏生才能哦！喵！","阔咩！不行哦！"]],["img",["ATRI_抱紧.jpg"]]],
        "我爱你": [["text",["我爱你喵！","我也爱你喵！","我会一直爱你喵！"]]],
        "好家伙": [["text",["超级好家伙！"]]],
        "恭喜发财": [["img",["ATRI_啊乌!.gif","ATRI_恭喜发财.gif"]]],
        "无语": [["img",["ATRI_无语.jpg"]]],
        "🦀": [["text",["是螃蟹！抢来吃掉！"]]],
        "对": [["img",["ATRI_肯定.jpg","ATRI_肯定1.jpg"]]],
        "好": [["text",["好"]],["img",["ATRI_好欸.jpg"]]],
        "好吧": [["text",["好吧"]]],
        "不知道": [["text",["不知道呢!","亚托莉不知道呢!","吸纳奶"]]],
        "收到": [["text",["收到!"]]],
        "我去": [["text",["你去"]]],
        "确信": [["text",["确信"]]],
        "是这样": [["text",["是这样","雀食是这样"]]],
        "摸摸头":[["text",["呜呜呜，摸头会长不高的！"]],["img",["ATRI_晃脑.gif"]]],
        "爬": [["text",["爬"]]],
        "谢谢": [["img",["ATRI_谢谢.jpg"]]],
        "叫哥哥": [["text",["欧尼～酱"]]],
        "6": [["text",["6"]]],
        "ok": [["text",["ok","好的"]]],
        "no": [["img",["ATRI_no.jpg"]]],
        "不要": [["img",["ATRI_摆手.gif","ATRI_不要1.gif"]]],
        "300颗": [["text",["够吗?又是这个难的过分的..."]]],
        "不行": [["img",["ATRI_垂头丧气.gif","ATRI_不要1.gif"]]],
        "。": [["img",["ATRI_句号.gif"]]],
        "可怕": [["img",["ATRI_惊讶.jpg"]]],
        "我喜欢你": [["text",["当流星陨落爱情的唯美，生命就开始哭泣，受伤的人就喜欢躲在黑暗的角落，任其身体的荒凉，仿佛全世界的人都在讨论爱情，但喜欢的事物却在另一个世界，这一刻更喜欢孤寂。"]]],
    }
    '''精确匹配列表'''

    monitoring_have_list = {
        "🤔": [["text",["🤔"]],["img",["ATRI_思考.jpg","ATRI_思考1.jpg","ATRI_思考2.jpg"]]],
        "😡": [["text",["😡","诶诶诶，不要生气嘛，要和睦相处哒~","亚托莉也生气了！","你怎么脸红了？😡"]]],
        "不是哥们": [["text",["不是哥们?"]]],
        "喵": [["text",["喵","喵喵!","喵喵喵!","喵泥格咪的！","我喵","喵？","我喵喵喵!","猫ですよ","你是猫吗？喵!"]]],
        "逆天": [["text",["逆天!","逆天","逆天了","你在逆什么呢,ATRI有大大的疑惑？","逆逆逆逆天"]]],
        "难蚌": [["text",["难蚌"]]],
        "好耶": [["img", ["ATRI_好耶.jpg"]]],
        "高性能": [["img",["ATRI_高性能.png","ATRI_得意.gif","ATRI_自我陶醉.gif","ATRI_机智如我.jpg","ATRI_我是高性能.jpg"]]],
        "Ciallo": [["img",["ATRI_Ciallo.jpg"]]],
        "废物":[["img",["ATRI_欺负我你能得到什么.jpg","ATRI_ 气鼓鼓.gif","ATRI_生气到爆.gif","ATRI_怎么你了.jpg","ATRI_违反机器人保护法.jpg","ATRI_别骂了.jpg"]]],
        "晚安":[["text",["晚安，做个好梦~","晚安哦！","晚安，睡个好觉~","晚上好，晚安！我也要睡觉啦~"]]],
        "早安": [["text",["早上好！","早上好呀！","早上好，今天也要元气满满哦！"]]],
        "亚托莉": [["img",["ATRI_左右摆头.gif","ATRI_抛星星眼.gif","ATRI_惊讶.gif","ATRI_小虎牙咬面包.jpg","ATRI_看你.gif","ATRI_闪亮登场.jpg"]]],
        "变态": [["img",["ATRI_变态.jpg","你太变态.jpg","ATRI_变态先生.jpg"]]],
        "哼哼啊": [["img",["ATRI_恶臭1145.jpg"]]],
        "圣诞": [["img",["ATRI_过圣诞.gif"]]],
        "有意思": [["img",["ATRI_有点意思.jpg"]]],
        "嘲讽": [["img",["ATRI_嘲笑.jpg","ATRI_下蹲.gif"]]],
        "哈基米": [["audio",["哈基米.wav"]],["text",["不要再哈基米了！喵！"]]],
        "吃饭": [["img",["ATRI_吃饭高兴.jpg"]]],
        "好吃": [["img",["ATRI_吃饭高兴.jpg"]]],
        "学习": [["img",["ATRI_学习.jpg"]]],
        "哼哼": [["img",["ATRI_恶臭1145.jpg"]]],
        "qwq": [["img",["ATRI_qwq.jpg"]],["text",["QWQ"]]],
        "galgame": [["img",["ATRI_玩galgame.jpeg"]]],
        "ATRI": [["img",["ATRI_探头.png","ATRI_左右摆头.gif","ATRI_看你.gif","ATRI_小虎牙咬面包.jpg","ATRI_闪亮登场.jpg"]]],
        "离谱": [["text",["离谱","离谱了","确实离谱"]]],
        "哭": [["img",["ATRI_哭.gif","ATRI_哭1.gif","ATRI_哭2.gif","ATRI_大哭.gif","ATRI_哇哇大哭.jpg"]]],
        "👍": [["text",["👍"]]],
        "😭": [["text",["怎么啦怎么啦，不要伤心嘛，来，亚托莉抱抱就好啦！","呜呜呜，不要难过啦!ATRI会一直陪在你身边哒！","不要哭泣，亚托莉会一直支持你的,不要伤心了!","不要伤心了，亚托莉在这里陪着你，一切都会好起来的！"]]],
        "涩涩": [["text",["不可以涩涩","涩涩打咩!","H是不行的！"]]],
        "无敌了":[["text",["无敌了!","无敌了"]]],
        "让世界感受痛苦":[["img",["ATRI_地爆天星.jpg"]]],
        "啊这":[["img",["ATRI_没办法给你解释.jpg","ATRI_惊讶.gif"]],["text",["啊这?"]]],
        "我来":[["img",["ATRI_放心交给我吧.gif","ATRI_敬礼.gif"]]],
        "正确": [["img",["ATRI_正确的.jpg"]]],
        "笑死我了":[["text",["笑死你了？","笑死我了!","我也笑死了"]]],
        "二次元":[["img",["ATRI_和我一起去二次元.jpg"]]],
        "期待": [["img",["ATRI_期待.gif"]]],
        "冒泡":[["text",["戳，嘿嘿嘿，被我捉住了呢！"]]],
        "😋": [["text",["😋"]]],
        "好强":[["text",["好强"]]],
        "盯着你": [["img",["ATRI_盯着你.jpg","ATRI_眨眼.gif"]]],
        "厉害": [["img",["ATRI_厉害.jpg"]]],
        "yes": [["img",["ATRI_yes.jpg"]]],
        "蚌埠": [["text",["难蚌"]]],
        "鬼": [["img",["ATRI_当鬼.gif","ATRI_鬼脸.gif"]]],
        "不信": [["img",["ATRI_不相信你的鬼话.jpg"]]],
        "猫咪": [["img",["ATRI_猫咪爪子.gif"]]],
        "失败": [["img",["ATRI_加载失败.jpg"]]],
        "卧槽": [["text",["卧槽"]]],
        "欸嘿": [["img",["ATRI_欸嘿.jpg"]]],
        "哇袄": [["img",["哇袄.png"]],["text",["哇袄!"]]],
        "网易云": [["img",["ATRI_网易云.jpg"]]],
        "666": [["text",["666"]]],
        "吃东西": [["img",["ATRI_嚼东西.jpg"]]],
        "红包": [["img",["ATRI_红包.gif"]]],
        "300颗够吗": [["text",["又是这个难的过分的波诗！"]]],
        "大佬": [["img",["ATRI_大佬.jpg"]]],
        "少壮不努力": [["text",["少壮不努力，老大亚托莉"]]],
        "死机":[["img",["ATRI_宕机.jpg"]]],
        "死了":[["img",["ATRI_死了.gif"]]],
        "锤子":[["img",["ATRI_被锤了.gif"]]],        
    }
    '''模糊匹配列表'''

    Frequently_used_words_list = [
        "草","?"
    ]
    "常用词汇列表,50%几率回复"