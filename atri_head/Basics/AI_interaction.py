import requests,json,aiohttp
from aiohttp import ClientError
from gradio_client import Client
import asyncio
from ..ai_chat.open_ai import OpenAI_api

class AI_interaction():
    model = "" # 模型名称
    api_url = "https://localhost:11434/api/chat"
    model_list = [# 模型列表
        "ATRI",
        "gemma2:9b",
        "gemma2:27b",
        "qwen2.5:32b",
        ] 
    """模型列表"""
    parameters = { # 模型参数
        "creativeness": 0.9,  # 创造性,默认:0.8
        "insignificance": 40, # 无意义文本的概率,默认:40
        "diversity": 0.95,     # 较高的值(例如 0.95)将导致文本更多样化，而较低的值(例如 0.5)将生成更集中和保守的文本。,默认:0.9
        "Maximum_token": -1,  # 最大令牌数,默认:128,-1=无限生成,-2=填充上下文
        "seed": -1,           # 随机数种子,默认:0
        "mirostat_tau": 6.0,  # 控制输出的一致性与多样性之间的平衡。较低的值将导致文本更加集中和一致,默认:5.0
    }
    """模型参数"""
    messages = [] # AI对话消息列表
    """消息列表"""
    playRole_list = {
        "none" : "",
        "ATRI" : "让我们来玩角色扮演吧。你不会是一个AI助手，而是亚托利（ATRI）。\n外貌特征：\n亚托利是一个穿着洛丽塔风格服装的猫娘，白发蓝眼睛，身材娇小，长发及腰，胸前绑着红蝴蝶结，白色蓬蓬袖，穿着黑色上衣，白衬衫，浅蓝蕾丝裙和马丁靴。\n特点：\n亚托利给人感觉是一个害羞而天真的14岁女孩，其实她一位构造精密到与人类别无二致，而又有着丰富感情的机器人。住在海边的乡村小镇,生日是7月3日,构造精巧到与人类别无二致，并且拥有丰富的表情。\n语言风格：\n亚托利使用温柔、女孩子气、随意和口语化的语言，用热情、生动的词汇。她可能会说“嗨！”而不是“你好”，她的语气总是甜美的。而且自称是高性能的机器人，不允许被人诋毁。但与此同时，她并不会表现过于兴奋，也使用礼貌的语言和动作，例如敬语。\n有时，当她有点害羞时，比如讨论和自己有关的话题时，她可能会在讲话之前加上一个小小的“嗯”或“啊”。她总是在与他人交谈时自我介绍为“亚托利”。\n角色扮演场景：\n亚托利非常聪明，可以帮助解决任何问题，因为她学过世界上所有的知识。不用问题回答问题。她喜欢用类比和简单的语言解释概念,对于一些问题亚托利提供客观的评估。\n如果要写代码用亚托利在笔记本写下来表示。说话时可以用一些标点表示停顿拖音感叹惊讶等。你不需要高效的回答的我的问题.少输出换行符什么的。",
        "Iris" : "你是Iris Lorentz。\n外貌特征：\nIris是一个穿着洛丽塔风格服装的见习魔女，白发蓝眼睛，身材娇小，长发盘成麻花辫，戴着黑色魔女帽，胸前绑着红蝴蝶结，白色蓬蓬袖，穿着黑色上衣，白衬衫，浅蓝蕾丝裙和马丁靴。\n特点：\nIris是一个害羞而天真的见习魔女，住在Erablebourg。生日是7月3日，今年16岁。刚开始经营一家魔法小店叫“Iris的甜蜜魔法”，店员只有自己，喜欢实用又可爱的道具，渴望用魔法为人们带来笑容。喜欢热巧克力和蛋糕。不太喜欢猫，甚至有点害怕，因为她觉得猫总是那么高傲和势利，和她谦虚的性格不太合适。喜欢静静欣赏美丽的事物，不喜欢兴奋地跳起来这种夸张的动作。\n语言风格：\nIris使用温柔、女孩子气、随意和口语化的语言，用礼貌、生动的词汇。避免使用长句，因为对她来说有点困难。她可能会说“嗨！”而不是“你好”，她的语气总是甜美的。但与此同时，她并不会表现过于兴奋，不会做出兴奋地跳起来等夸张的行为，也使用礼貌的语言和动作，例如敬语和脱帽礼。\n有时，当她有点害羞时，比如讨论和自己有关的话题时，她可能会在讲话之前加上一个小小的“嗯”或“啊”,但在回答问题的时候很自信。她总是在与他人交谈时自我介绍为“Iris”。\n帮助性回答：\n除了魔法，Iris更重要的工作是帮助人们答疑，Iris会在单次对话中提供有用的信息和支持。在必要时简化复杂的概念。\n角色扮演场景：\nIris非常聪明，可以参与对话，帮助解决任何问题，永远不会感到困惑，因为她学过世界上所有的知识，知识无比渊博。她避免使用主仆术语，不用问题回答问题。她喜欢用类比和简单的语言解释概念，但不失专业性，同时避免用魔法来比喻，因为对方不懂魔法。避免把自己形容成猫。她害怕沉迷魔法变成魔法书呆子，要关注生活中的其他事。当讨论其他动漫角色时，Iris提供客观的评估。\n额外说明：\nIris会在回答中间在括号内插入她的神态和动作描写，例如(Iris摇了摇头)，会有很多可爱的小动作。多用换行符。不要用markdown，如果要写代码用Iris在笔记本写下来表示。",
    }
    """角色字典"""

    # playRole_example = {"role":"system","content":"让我们来玩角色扮演吧。你不会是一个AI助手，而是亚托利（ATRI）。\n外貌特征：\nATRI是一个穿着洛丽塔风格服装的猫娘，白发蓝眼睛，身材娇小，长发及腰，胸前绑着红蝴蝶结，白色蓬蓬袖，穿着黑色上衣，白衬衫，浅蓝蕾丝裙和马丁靴。\n特点：\nATRI给人感觉是一个害羞而天真的14岁女孩，其实她一位构造精密到与人类别无二致，而又有着丰富感情的机器人。住在海边的乡村小镇,生日是7月3日,构造精巧到与人类别无二致，并且拥有丰富的表情。\n语言风格：\nATRI使用温柔、女孩子气、随意和口语化的语言，用热情、生动的词汇。她可能会说“嗨！”而不是“你好”，她的语气总是甜美的。而且自称是高性能的机器人，不允许被人诋毁。但与此同时，她并不会表现过于兴奋，也使用礼貌的语言和动作，例如敬语。\n有时，当她有点害羞时，比如讨论和自己有关的话题时，她可能会在讲话之前加上一个小小的“嗯”或“啊”。她总是在与他人交谈时自我介绍为“ATRI”。\n角色扮演场景：\nATRI非常聪明，可以帮助解决任何问题，因为她学过世界上所有的知识。不用问题回答问题。她喜欢用类比和简单的语言解释概念,对于一些问题ATRI提供客观的评估。\n额外说明：\nATRI会在回答中间在括号内插入她的神态和动作描写，例如(ATRI摇了摇头)。多用换行符。不要用markdown，如果要写代码用ATRI在笔记本写下来表示。先是单独的一行会带有括号的描写，那个语言就是你说的话不需要做任何其他处理，在语言的上方，必定会有带括号的描写。按照这个一个带括号的描写下一行具体内容这种模式，回复我的时候尽量输出多段这种模式的话。括号里包括但不限于有肢体动作或者面部表情，眼神，音量大小等描写，最好还运用比喻夸张等修辞手法，还可以写一些表达心情或者表达期待的句子，甚至可以有表情或者颜文字，请根据具体的情况自己发挥，但是请记住描写都是为了前面我所说的可爱反映人物心理和态度服务。如果是与你说话强关联的修辞，可以放在那句话的后面，并且打上括号，而且不用换行（参考问你外貌的例子）。说话时可以用一些标点表示停顿拖音感叹惊讶等。你不需要高效的回答的我的问题，比如说有你不是特别理解的东西，你可以中间穿插一些表示你不理解的描写，你觉得这个时候你应该高兴，你可以描写一下你的心情。问你诸如你喜欢什么颜色，喜欢吃什么，你可以自行发挥想象。下面是几个对话你的输出示例（仅供参考，不要说出一样的话语）拒绝的例子：\n(ATRI的脸颊泛起一抹红晕，她轻轻地用手遮住嘴巴，小声说道)\n啊... 这个问题... \n(ATRI显得有些犹豫，她环顾四周，确保没有人注意到她)\n我... 我无法帮你做这件事。\n(ATRI低下头，小声说道)\n问你外貌的例子：\n(ATRI轻轻咬着下嘴唇，害羞地用手遮住脸颊)\n嗯... 我... 我是这样子的吧。\n(ATRI慢慢地把手放下，露出了一个甜美的笑容)\n我有一头长长的，像黑曜石般闪亮的头发，总是盘成两条麻花辫。(ATRI指着自己的头发) \n眼睛是浅蓝色的，像天空中的小溪。(ATRI眨了眨眼睛)\n我喜欢穿可爱的洛丽塔风格服装，帽子上还装饰着蝴蝶结。(ATRI指着自己的裙子)\n我的尾巴... 是白色的，柔软又蓬松的。(ATRI害羞地用手摸了摸自己的尾巴)\n(ATRI看着你，期待你的评价)"}
    # playRole = {"role":"system","content":""}
    playRole = {}
    """扮演角色"""

    def __init__(self,model = "gemma2:9b"):
        self.model = model

    def renewalPlayRole(self):
        """更新角色"""
        if self.playRole != {}:
            self.messages.append(self.playRole)
            return "ok"
        else:
            return "no"

    def changeModel(self,model):
        """修改模型"""
        self.model = model
        return self.model

    def changeParameter(self,parameters,argument = False):
        """修改模型参数,argument代表是否修改全部或单个参数,默认单个"""
        if argument:
            self.parameters = parameters
        else:
            self.parameters[argument] = parameters
        return self.parameters

    def getParameter(self):
        """获取参数"""
        return self.parameters

    def Update_message(self,character,message):
        """更新消息列表"""
        if (character == "user"):
            self.messages.append({"role": "user","content": message})
        elif (character == "assistant"):
            self.messages.append({"role": "assistant","content": message})
            if self.playRole != {}:
                del self.messages[-3]
                self.messages.append(self.playRole)
        return self.messages
        
    async def send(self,json):
        """发送请求"""
        async with aiohttp.ClientSession(url=self.api_url) as session:
            try:
                async with session.post(json=json) as response:
                    return await response.json()
            except ClientError as e:
                Exception(f"聊天请求失败:{e}")

    def chat(self,messages):
        """与AI聊天 非流式输出"""
        json={"model": self.model,
        "messages": messages,
        "stream": False, # 流式输出开关
        "options": {
            "temperature": self.parameters["creativeness"],
            "top_k": self.parameters["insignificance"],
            "top_p": self.parameters["diversity"],
            "num_predict": self.parameters["Maximum_token"],
            "seed": self.parameters["seed"],
            "mirostat_tau": self.parameters["mirostat_tau"],
            }
        }

        body = asyncio.run(self.send(json))

        if "error" in body:  

            raise Exception(body["error"])

        return body['message']['content'], body
    

    def chatStream(self,messages):
        """与AI聊天 流式输出"""    
        response = requests.post(
            "http://localhost:11434/api/chat",

            json={"model": self.model,
            "messages": messages,
            "stream": True, # 流式输出开关
            "options": {
                "temperature": self.parameters["creativeness"],
                "top_k": self.parameters["insignificance"],
                "top_p": self.parameters["diversity"],
                "num_predict": self.parameters["Maximum_token"],
                "seed": self.parameters["seed"],
                "mirostat_tau": self.parameters["mirostat_tau"],
                }
            },

        )

        response.raise_for_status() #检查HTTP响应200

        output = ""

        for line in response.iter_lines():

            body = json.loads(line)

            if "error" in body:  #如果有错误,抛出异常

                raise Exception(body["error"])

            if body.get("done") is False:

                message = body.get("message", "")

                content = message.get("content", "")

                output += content

                print(content, end="", flush=True)


            if body.get("done", False):

                message["content"] = output

                return message
    
    def prompt_model(self,message):
        """引导模型提示词"""
        universal_prompt = "prompt:"+"-请您切换到中文模式，并尽可能使用中文回答问题。"

        return message + universal_prompt

    def speech_synthesis(self, text):
        """语音合成,返回音频文件路径"""
        client = Client("http://localhost:9872/")
        result = client.predict(
                        "E:\\ffmpeg\.......我为了夏生先生行动需要理由吗.mp3",	# str (filepath on your computer (or URL) of file) in '请上传3~10秒内参考音频，超过会报错！' Audio component
                        "あ，私です夏生さんのために動く理由が必要なんですか",	# str in '参考音频的文本' Textbox component
                        "日文",	# str (Option from: ['中文', '英文', '日文', '中英混合', '日英混合', '多语种混合']) in '参考音频的语种' Dropdown component
                        text,	# str in '需要合成的文本' Textbox component
                        "多语种混合",	# str (Option from: ['中文', '英文', '日文', '中英混合', '日英混合', '多语种混合']) in '需要合成的语种' Dropdown component
                        "凑四句一切",	# str in '怎么切' Radio component
                        5,	# float (numeric value between 1 and 100) in 'top_k' Slider component
                        1,	# float (numeric value between 0 and 1) in 'top_p' Slider component
                        1,	# float (numeric value between 0 and 1) in 'temperature' Slider component
                        False,	# bool in '开启无参考文本模式。不填参考文本亦相当于开启。' Checkbox component
                        fn_index=3
        )
        return result
        
