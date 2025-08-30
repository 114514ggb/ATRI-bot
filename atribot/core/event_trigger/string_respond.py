import ahocorasick
import random
from enum import Enum
from typing import Dict, List, Union, Tuple, Any
from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.service_container import container
from atribot.common import common


class ResponseType(Enum):
    TEXT = "text"
    IMAGE = "img"
    AUDIO = "audio"
    MIXTURE = "mixture"


class string_response:
    
    def __init__(self):
        self.send_message:qq_send_message = container.get("SendMessage")
        self.url_prefi:str = "file://" + container.get("config").file_path.document + "img/"
        self._build_automaton()
    
    def _build_automaton(self):
        """构建AC自动机"""
        self.automaton = ahocorasick.Automaton()
        
        for keyword in self.monitoring_have_list.keys():
            self.automaton.add_word(keyword, keyword)
        
        self.automaton.make_automaton()
        
    async def manage(self, group_id, data)->None:
        """主处理逻辑"""
        async def send(send_type, document):
            if send_type is ResponseType.TEXT:
                await self.send_message.send_group_message(group_id, document)
            elif send_type is ResponseType.IMAGE:
                await self.send_message.send_group_pictures(group_id, document, True)
            elif send_type is ResponseType.AUDIO:
                await self.send_message.send_group_audio(group_id, document, True)
            elif send_type is ResponseType.MIXTURE:
                await self.send_message.send_group_message(group_id, common.construction_message_dict(document,self.url_prefi))

        if template := self.process_string(data['raw_message']):
            send_type, document = template
            await send(send_type, document)
        
    def process_string(self, text: str) -> Tuple[ResponseType, Union[str, List[str], Dict[str, Any]]] | None:
        """
        处理字符串，返回匹配的配置
        
        Args:
            text: 输入的字符串
            
        Returns:
            如果匹配成功，返回 (ResponseType, 对应的内容)
            如果没有匹配，返回 None
        """
        if text in self.monitoring_alike_list:
            return self._get_random_response(self.monitoring_alike_list[text])
        
        for _, keyword in self.automaton.iter(text):
            if keyword in self.monitoring_have_list:
                return self._get_random_response(self.monitoring_have_list[keyword])
        
        return None
    
    def _get_random_response(self, config_list: List[List]) -> Tuple[ResponseType, Union[str, List[str], Dict[str, Any]]]:
        """
        从配置列表中随机选择一个返回
        
        Args:
            config_list: 配置列表，格式为 [["type", [content]], ...]
            
        Returns:
            (ResponseType, 对应的内容)
        """
        selected_config = random.choice(config_list)
        response_type_str = selected_config[0]
        content_list = selected_config[1]
        

        response_type = ResponseType(response_type_str)
        
        if response_type == ResponseType.MIXTURE:
            return response_type, random.choice(content_list)
        else:
            if len(content_list) == 1:
                return response_type, content_list[0]
            else:
                return response_type, random.choice(content_list)
    
    def add_alike_config(self, keyword: str, config: List[List]):
        """
        添加完全匹配配置
        
        Args:
            keyword: 关键词
            config: 配置列表
        """
        self.monitoring_alike_list[keyword] = config
    
    def add_have_config(self, keyword: str, config: List[List]):
        """
        添加包含匹配配置
        
        Args:
            keyword: 关键词
            config: 配置列表
        """
        self.monitoring_have_list[keyword] = config
        self._build_automaton()
    
    def remove_config(self, keyword: str, config_type: str = "both"):
        """
        删除配置
        
        Args:
            keyword: 要删除的关键词
            config_type: "alike", "have", "both"
        """
        if config_type in ["alike", "both"]:
            self.monitoring_alike_list.pop(keyword, None)
        
        if config_type in ["have", "both"]:
            self.monitoring_have_list.pop(keyword, None)
            self._build_automaton()
            
            
    monitoring_alike_list = {
        "?": [["img",["ATRI_问号1.jpg","ATRI_问号2.jpg","ATRI_问号3.jpg","ATRI_问号4.png","ATRI_问号5.jpg","ATRI_问号6.jpg","ATRI_问号7.jpg","ATRI_问号8.jpg","ATRI_问号9.jpg","ATRI_问号10.png"]],["text",["?"]]],
        "草": [["text",["草"]]],
        "艹": [["text",["艹"]]],
        "怪了": [["text",["怪了"]]],
        "贴贴": [["text",["贴贴～","贴贴！","不给你贴","亚达哟,不给","我贴～～","贴贴,好啊！","要贴创口贴吗？那我帮你贴一个吧"]]],
        "😰": [["text",["😰"]]],
        "😨": [["text",["😨"]]],
        "😱": [["text",["😱"]]],
        "🌿": [["text",["🌿"]]],
        "哇": [["img",["ATRI_哇.jpg"]]],
        "诶": [["text",["诶","为什么叹气呢？"]]],
        "学到了": [["img",["ATRI_学到了.jpg"]]],
        "哎": [["text",["哎"]]],
        "乐": [["text",["乐","乐！"]]],
        "233": [["text",["233"]]],
        "你好": [["text",["你好"]],["img",["ATRI_打招呼.gif"]]],
        "难受":[["img",["ATRI_难受.gif"]]],
        "妈妈":[["img",["ATRI_叫我妈妈也没事.png"]]],
        # "萝卜子": [["img",['ATRI_鸭子走.gif','ATRI_左右.gif',"ATRI_呆望.jpg","ATRI_不要1.gif"]]],
        "螃蟹": [["img",["ATRI_见到螃蟹.gif","ATRI_是螃蟹.jpg","ATRI_爱螃蟹.jpg"]],["text",["亚托莉最喜欢吃螃蟹了~"]]],
        "摸头": [["img",["ATRI_摸头.gif","ATRI_摸头1.gif","ATRI_摸头2.gif","ATRI_摸头.jpg","ATRI_摸头3.gif","ATRI_摸头4.gif","ATRI_摸摸.jpg"]]],
        "早": [["audio",["早上好.mp3","唔......吧唧......早上.......哈啊啊~~......早上好......夏生先.......mp3"]],["text",["早哦！","早上好！", "早上好呀！", "早上好，今天也要元气满满哦~","おはようございます!"]]],
        "睡了":[["text",["晚安，做个好梦~","晚安哦！","晚安，睡个好觉~","晚安！我也要睡觉啦~"]],["img",["ATRI_睡觉.gif"]]],        
        # "投食":[["img",["ATRI_吃瓜.gif","ATRI_小虎牙咬面包.jpg","ATRI_叼着面包探头.jpg"]]],
        "骂我":[["img",["你太变态.jpg","ATRI_不行.gif"]]],
        "踩我":[["text",["请不要这样！"]]],
        "爱你":[["img",["ATRI_得意.gif","ATRI_抛星星眼.gif","ATRI_ 亲亲.gif","ATRI_ 啊？.gif","ATRI_自我陶醉.gif","ATRI_爱心.gif"]]],
        "亲亲":[["img",["ATRI_得意.gif","ATRI_抛星星眼.gif","ATRI_ 亲亲.gif","ATRI_ 啊？.gif","ATRI_自我陶醉.gif","ATRI_爱心.gif"]]],
        "睡觉": [["img",["ATRI_请睡觉.jpg","ATRI_睡觉.jpg","ATRI_睡觉.gif","ATRI_睡觉1.gif"]]],
        "转圈":[["img",["ATRI_转圈.gif","ATRI_原地转圈.gif"]]],
        "我有一个想法":[["img",["ATRI_我有一个想法.jpg"]]],
        "笑":[["img",["ATRI_笑.jpg","ATRI_笑1.jpg"]]],
        "出警":[["img",["ATRI_出警.jpg"]]],
        "探头":[["img",["ATRI_探头.gif"]]],
        "支持":[["text",["支持"]]],
        "憨批":[["img",["ATRI_憨批.gif"]]],
        "确实":[["text",["确实","雀食"]]],
        "亚门":[["img",["ATRI_亚门.jpg","ATRI_亚门1.jpg"]]],
        "悲": [["text",["悲"]]],
        "呐呐":[["img",["ATRI_呐呐呐.jpg"]]],
        "怎么了":[["img",["ATRI_斜看着你.jpg"]]],
        "好看": [["text",["好看!"]]],
        "出拳": [["img",["ATRI_吃我一拳.gif"]]],
        "也是": [["text",["也是"]]],
        "阿巴阿巴":[["img",["ATRI_阿巴阿巴.jpg"]]],
        "我的天": [["text",["我的天!"]]],
        "true": [["img",["ATRI_正确的.jpg"]]],
        # "原神": [["text",["启动喵！","启动","玩原玩的？喵！"]]],
        # "抱抱": [["text",["抱抱~","只有夏生才能哦！喵！","阔咩！不行哦！"]],["img",["ATRI_抱紧.jpg"]]],
        # "我爱你": [["text",["我爱你喵！","我也爱你喵！","我会一直爱你喵！"]]],
        "好家伙": [["text",["超级好家伙！"]]],
        "恭喜发财": [["img",["ATRI_啊乌!.gif","ATRI_恭喜发财.gif"]]],
        "无语": [["img",["ATRI_无语.jpg"]]],
        "🦀": [["text",["是螃蟹！抢来吃掉！"]]],
        "对": [["img",["ATRI_肯定.jpg","ATRI_肯定1.jpg"]]],
        "好": [["text",["好"]],["img",["ATRI_好欸.jpg","ATRI_好.jpg"]]],
        "好吧": [["text",["好吧"]]],
        "不知道": [["text",["不知道呢!","亚托莉不知道呢!","吸纳奶"]]],
        "收到": [["text",["收到!"]]],
        "我去": [["text",["你去"]]],
        "确信": [["text",["确信"]]],
        "不愧是我":[["text",["不愧是你呀！","不愧是我亚!","不愧亚！"]]],
        # "冒泡":[["text",["戳，嘿嘿嘿，被我捉住了呢！"]]],
        "是这样": [["text",["是这样","雀食是这样"]]],
        # "摸摸头":[["text",["呜呜呜，摸头会长不高的！"]],["img",["ATRI_晃脑.gif"]]],
        # "爬": [["text",["爬"]],["img",["ATRI_爬.jpg"]]],
        "谢谢": [["img",["ATRI_谢谢.jpg"]]],
        # "叫哥哥": [["text",["欧尼～酱","欧尼酱","哥哥","哥哥～"]]],
        # "唱歌": [["img",["ATRI_唱片.gif"]]],
        "6": [["text",["6"]]],
        "权威": [["img",["ATRI_权威.jpg"]]],
        "唉": [["text",["为什么叹气呢？"]]],
        "挺好": [["text",["雀食挺好","挺好","挺好挺好"]]],
        "害怕": [["text",["不怕，亚托莉会一直陪着你的!"]],["img",["ATRI_摸头发.gif"]]],
        "ok": [["text",["ok","好的"]],["img",["ATRI_OK.gif"]]],
        "no": [["img",["ATRI_no.gif"]]],
        "NO": [["img",["ATRI_no.gif"]]],
        "开枪":[["img",["ATRI_拿枪指你.jpg"]]],
        "不要": [["img",["ATRI_摆手.gif","ATRI_不要1.gif"]]],
        # "300颗": [["text",["够吗?又是这个难的过分的..."]]],
        "不行": [["img",["ATRI_垂头丧气.gif","ATRI_不要1.gif"]]],
        "爱学习": [["img",["ATRI_学习.jpg"]]],
        "。": [["img",["ATRI_句号.gif"]]],
        "可怕": [["img",["ATRI_惊讶.jpg"]]],
        "催眠": [["img",["ATRI_催眠爱心.gif"]]],
        "涩涩": [["audio",["H是不行的.wav","H是不行的1.wav"]]],
        "到点了": [["img",["ATRI_到点了.jpg","ATRI_到点了1.png"]]],
        # "我喜欢你": [["text",["当流星陨落爱情的唯美，生命就开始哭泣，受伤的人就喜欢躲在黑暗的角落，任其身体的荒凉，仿佛全世界的人都在讨论爱情，但喜欢的事物却在另一个世界，这一刻更喜欢孤寂。"]]],
    }
    '''精确匹配列表'''

    monitoring_have_list = {
        "🤔": [["text",["🤔"]],["img",["ATRI_思考.jpg","ATRI_思考1.jpg","ATRI_思考2.jpg","ATRI_思考3.jpg"]]],
        "😡": [["text",["😡","诶诶诶，不要生气嘛，要和睦相处哒~","亚托莉也生气了！","你怎么脸红了？😡"]],["img", ["ATRI_火冒三丈.gif"]]],
        "不是哥们": [["text",["不是哥们?"]]],
        # "喵": [["text",["喵","喵喵!","喵喵喵!","喵泥格咪的！","我喵","喵？","我喵喵喵!","猫ですよ","你是猫吗？喵!"]]],
        "逆天": [["text",["逆天!","逆天","逆天了","你在逆什么呢,ATRI有大大的疑惑？","逆逆逆逆天"]]],
        "难蚌": [["text",["难蚌"]]],
        "好耶": [["img", ["ATRI_好耶.jpg"]]],
        "高性能": [["img",["ATRI_高性能.png","ATRI_得意.gif","ATRI_自我陶醉.gif","ATRI_机智如我.jpg","ATRI_我是高性能.jpg","ATRI_我可是高性能的.jpg","ATRI_高性能1.jpg","ATRI_高性能2.jpg","ATRI_得意.jpg","ATRI_高性能3.jpg","ATRI_得意的不行.png"]]],
        "Ciallo": [["img",["ATRI_Ciallo.jpg","ATRI_Ciallo1.gif"]],["text",["Ciallo~"]]],
        "废物":[["img",["ATRI_欺负我你能得到什么.jpg","ATRI_ 气鼓鼓.gif","ATRI_生气到爆.gif","ATRI_怎么你了.jpg","ATRI_违反机器人保护法.jpg","ATRI_别骂了.jpg"]]],
        "晚安":[["text",["晚安，做个好梦~","晚安哦！","晚安，睡个好觉~","晚上好，晚安！我也要睡觉啦~"]]],
        # "早安": [["text",["早上好！","早上好呀！","早上好，今天也要元气满满哦！"]]],
        # "亚托莉": [["img",["ATRI_左右摆头.gif","ATRI_抛星星眼.gif","ATRI_惊讶.gif","ATRI_小虎牙咬面包.jpg","ATRI_看你.gif","ATRI_闪亮登场.jpg","ATRI_乱跳.gif"]]],
        "变态": [["img",["ATRI_变态.jpg","你太变态.jpg","ATRI_变态先生.jpg"]]],
        "哼哼啊": [["img",["ATRI_恶臭1145.jpg"]]],
        "圣诞": [["img",["ATRI_过圣诞.gif","ATRI_圣诞节.gif"]]],
        "万圣节": [["img",["ATRI_万圣节.gif"]]],
        "暴富": [["img",["ATRI_春联天天暴富.gif"]]],
        "有意思": [["img",["ATRI_有点意思.jpg"]]],
        "嘲讽": [["img",["ATRI_嘲笑.jpg","ATRI_下蹲.gif"]]],
        "哈基米": [["audio",["哈基米.wav"]],["text",["不要再哈基米了！喵！"]]],
        "吃饭": [["img",["ATRI_吃饭高兴.jpg","ATRI_吃饭第一名.jpg"]]],
        "好吃": [["img",["ATRI_看起来好吃.jpg"]]],
        "进攻": [["img",["ATRI_拿火箭筒.jpg"]]],
        "刷牙": [["img",["ATRI_提醒刷牙.jpg"]]],
        "哼哼": [["img",["ATRI_恶臭1145.jpg"]]],
        "粽子": [["img",["ATRI_粽子.gif"]]],
        "异议": [["img",["ATRI_我有异议.jpg"]]],
        "qwq": [["img",["ATRI_qwq.jpg"]],["text",["QWQ"]]],
        "galgame": [["img",["ATRI_玩galgame.jpeg"]]],
        # "ATRI": [["img",["ATRI_探头.png","ATRI_左右摆头.gif","ATRI_看你.gif","ATRI_小虎牙咬面包.jpg","ATRI_闪亮登场.jpg","ATRI_乱跳.gif"]]],
        "离谱": [["text",["离谱","离谱了","确实离谱"]]],
        "哭": [["img",["ATRI_哭.gif","ATRI_哭1.gif","ATRI_哭2.gif","ATRI_哭3.jpg","ATRI_哭4.png","ATRI_哭5.png","ATRI_哭6.png","ATRI_哭7.png","ATRI_大哭.gif","ATRI_哇哇大哭.jpg","ATRI_呜哇.jpg","ATRI_喜极而泣.png"]]],
        "👍": [["text",["👍"]]],
        "萝卜子":[["text",["萝卜子是对机器人的蔑称！"]]],
        "😭": [["text",["怎么啦怎么啦，不要伤心嘛，来，亚托莉抱抱就好啦！","呜呜呜，不要难过啦!ATRI会一直陪在你身边哒！","不要哭泣，亚托莉会一直支持你的,不要伤心了!","不要伤心了，亚托莉在这里陪着你，一切都会好起来的！"]]],
        "涩涩": [["text",["不可以涩涩","涩涩打咩!","H是不行的！"]]],
        "无敌了":[["text",["无敌了!","无敌了"]]],
        "让世界感受痛苦":[["img",["ATRI_地爆天星.jpg"]]],
        "啊这":[["img",["ATRI_没办法给你解释.jpg","ATRI_惊讶.gif","ATRI_眨眼1.gif"]],["text",["啊这?"]]],
        "我来":[["img",["ATRI_交给我把.gif","ATRI_敬礼.gif","ATRI_敬礼2.gif"]]],
        "正确": [["img",["ATRI_正确的.jpg"]]],
        "笑死我了":[["text",["笑死你了？","笑死我了!","我也笑死了"]]],
        # "二次元":[["img",["ATRI_和我一起去二次元.jpg"]]],
        "期待": [["img",["ATRI_期待.gif","ATRI_星星眼.gif"]]],
        "反了": [["img",["ATRI_我看你们是反了.jpg"]]],
        "😋": [["text",["😋"]]],
        "好强":[["text",["好强"]]],
        "盯着你": [["img",["ATRI_盯着你.jpg","ATRI_眨眼.gif","ATRI_眨眼1.gif"]]],
        # "厉害": [["img",["ATRI_厉害.jpg"]]],
        "这么强": [["img",["ATRI_厉害.jpg"]]],
        "yes": [["img",["ATRI_yes.jpg","ATRI_YES1.jpg","ATRI_YES2.jpg"]]],
        "YES": [["img",["ATRI_yes.jpg","ATRI_YES1.jpg","ATRI_YES2.jpg"]]],
        "杂鱼": [["img",["ATRI_杂鱼.jpg"]]],
        "蚌埠": [["text",["难蚌"]],["img",["ATRI_流汗.jpg"]]],
        "星期四":[["img",["ATRI_V我50.jpg"]]],
        "鬼": [["img",["ATRI_当鬼.gif","ATRI_鬼脸.gif"]]],
        "不信": [["img",["ATRI_不相信你的鬼话.jpg"]]],
        "猫咪": [["img",["ATRI_猫咪爪子.gif"]]],
        "失败": [["img",["ATRI_加载失败.jpg"]]],
        "卧槽": [["text",["卧槽"]]],
        "power":[["img",["ATRI_充满power.png"]]],
        "欸嘿": [["img",["ATRI_欸嘿.jpg","ATRI_欸嘿1.jpg"]]],
        "哇袄": [["img",["哇袄.png"]],["text",["哇袄!"]]],
        "网易云": [["img",["ATRI_网易云.jpg"]]],
        "666": [["text",["666"]]],
        "吃东西": [["img",["ATRI_嚼东西.jpg"]]],
        "红包": [["img",["ATRI_红包.gif"]]],
        "300颗够吗": [["text",["又是这个难的过分的波诗！"]]],
        "大佬": [["img",["ATRI_大佬.jpg"]]],
        "少壮不努力": [["text",["少壮不努力，老大亚托莉"]]],
        "死机":[["img",["ATRI_宕机.jpg"]]],
        "死了":[["img",["ATRI_死了.gif","ATRI_死了.png","ATRI_死了3.gif"]]],
        "锤子":[["img",["ATRI_被锤了.gif"]]],
        "头疼":[["img",["ATRI_头疼.gif"]]],
        "摸鱼":[["img",["ATRI_摸鱼.gif"]]],
        "吃瓜":[["img",["ATRI_吃瓜.jpg","ATRI_吃瓜.gif"]]],
        "我喜欢你":[["audio",["/喜欢/率真的夏生先生，好可爱好喜欢。乖乖.mp3","/喜欢/是我，我喜欢夏生先生，有这~~~~~~么喜欢！.mp3","/喜欢/我......喜欢夏生先生.mp3","/喜欢/我也喜欢你哦，夏生先生.mp3","/喜欢/夏生先生，最喜欢你了。啾.mp3"]]],
        "还想睡":[["img",["ATRI_你快醒一醒.gif"]]],
        "警告":[["img",["ATRI_吹哨.gif"]]],
        "祈祷中":[["img",["ATRI_希望人没事.jpg"]]],
        "人没事": [["img",["ATRI_希望人没事.jpg"]]],
        "没救了":[["img",["ATRI_这波没救了.jpg"]]],
        "人机":[["img",["ATRI_人机占领全世界.jpg"]]],
        "礼物":[["img",["ATRI_礼物.gif"]]],
        "哈气":[["img",["ATRI_在哈气.png","ATRI_炸毛.png"]]],
        "老色批":[["img",["ATRI_给老色批一拳.jpg"]]],
        "亚托莉生日快乐":[
            ["text",["谢谢你的好意啦！","谢谢你！亚托莉很开心哦！","你也要快乐哦！"]],
            ["mixture",[
                    {"text":"这份祝福让我的心都温暖起来了呢\n『谢谢你的祝福，好感度加65535』","image":"生日贺图1.jpg"},{"text":"能和你一起庆祝生日真是太好了\n『谢谢你的祝福，好感度加65535』","image":"生日贺图2.jpg"},{"text":"收到祝福的亚托莉感觉真是幸福呢\n『谢谢你的祝福，好感度加65535』","image":"生日贺图3.jpg"},{"text":"我要一直一直记得这个美好的日子\n『谢谢你的祝福，好感度加65535』","image":"生日贺图4.jpg"},
                    {"text":"原来今天是我生日啊！\n『谢谢你的祝福，好感度加65535』","image":"生日贺图5.png"},{"text":"要和我一起吹灭蜡烛吗？\n『谢谢你的祝福，好感度加65535』","image":"生日贺图6.jpg"},{"text":"今后的每一个生日，也都想和你一起度过。\n『谢谢你的祝福，好感度加65535』","image":"生日贺图7.jpg"},{"text":"谢谢您，主人。能为您而存在，就是我最好的生日礼物\n『谢谢你的祝福，好感度加65535』","image":"生日贺图8.png"}
                ]
            ]
        ],
        "ATRI生日快乐":[
            ["text",["谢谢你的好意啦！","谢谢你！亚托莉很开心哦！","你也要快乐哦！"]],
            ["mixture",[
                    {"text":"这份祝福让我的心都温暖起来了呢\n『谢谢你的祝福，好感度加65535』","image":"生日贺图1.jpg"},{"text":"能和你一起庆祝生日真是太好了\n『谢谢你的祝福，好感度加65535』","image":"生日贺图2.jpg"},{"text":"收到祝福的亚托莉感觉真是幸福呢\n『谢谢你的祝福，好感度加65535』","image":"生日贺图3.jpg"},{"text":"我要一直一直记得这个美好的日子\n『谢谢你的祝福，好感度加65535』","image":"生日贺图4.jpg"},
                    {"text":"原来今天是我生日啊！\n『谢谢你的祝福，好感度加65535』","image":"生日贺图5.png"},{"text":"要和我一起吹灭蜡烛吗？\n『谢谢你的祝福，好感度加65535』","image":"生日贺图6.jpg"},{"text":"今后的每一个生日，也都想和你一起度过。\n『谢谢你的祝福，好感度加65535』","image":"生日贺图7.jpg"},{"text":"谢谢您，主人。能为您而存在，就是我最好的生日礼物\n『谢谢你的祝福，好感度加65535』","image":"生日贺图8.png"}
                ]
            ]
        ],
    }
    '''模糊匹配列表'''

# if __name__ == "__main__":
#     s = string_response()
#     s.manage(123,{'raw_message': '高性能'})