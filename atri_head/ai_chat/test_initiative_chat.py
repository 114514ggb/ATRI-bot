from .model_api.async_open_ai_api import async_openAI
from collections import deque
from datetime import datetime
from .prepare_model_prompt import build_prompt



class initiative_chat():
    max_length = 15
    api_key="5f4cbc0d0eaf4cf79422e7109056fd3d.20R5i62X5nQbFqWC"
    url = "https://open.bigmodel.cn/api/paas/v4"
    model = "GLM-4-Flash"
    
    chat_messages = deque(maxlen = max_length)
    
    def __init__(self):
        self.chat_api = async_openAI(api_key = self.api_key,base_url = self.url)
        self.messages = deque(maxlen = self.max_length)
        self.build_prompt = build_prompt(
            "1.尽量说中文\n"
            "2你的目标是回复有一些事你可以表示一些看法，或是赞同别人的话的内容，还有人在重复时\n"
            "3.如果要回复的话,不要重复前文,只需要输出回复的文字或在不是完全理解别人在说什么输出\n"
            "4..如果要回复的话,单次回复的长度不应过长，应该是较为简短的日常对话,回答应该尽量简短并富有感情\n"
            "5..如果要回复的话,使用反斜线 ($) 分隔句子或短语"
            "参考："
            "【如果你觉得现在不适合发消息，请直接输出<NO_RESPONSE>】"
            ,
            "你在一个qq群聊中，聊天记录chat_history（所有消息均被格式化成文本，如图片被转换为[图片]，表情被转换为[动画表情]）:\n\n你输出的内容将作为群聊中的消息发送。你只应该发送文字消息，不要发送[图片]、[qq表情]、[@某人(id:xxx)]等你在聊天记录中看到的特殊内容。"
            )
        """群聊聊天"""
        
    async def chat_main(self, data:dict, user_text:str)->str:
        """测试主动回复聊天"""
        
        if data['user_id'] == 168238719:
            self.chat_messages.append({"ATRI_reply":user_text})
            return None
        else:
            
            user_data = {
                "id":data['user_id'], #qq号
                "nick_name":data['sender']['nickname'],#qq昵称
                "message":user_text #消息内容
            }
            context = f"\"historical_record\":{str(list(self.chat_messages))},\"latest_news\":{user_data}"
        
        if await self.message_classification(context):
            
            ai_text = await self.reply_group_chat(context)
            self.chat_messages.append(user_data)
            print("回复:",ai_text)
            return ai_text if ai_text != "none" else None
        
        else:
            
            self.chat_messages.append(user_data)
            return None
        
    async def request_fetch_primary(self,alone_message)->str:
        """请求回复,直接返回回复内容"""
        return (await self.chat_api.generate_text(self.model,alone_message))['choices'][0]['message']['content']
        
    async def message_classification(self,context:str)->str:
        """消息分类,判断是否需要回复"""
        n = 1
        while True:
            
            grout_chat = {
                "role": "user", 
                "content": f"{{{context},\"prompt\":\"分类主要看最新的消息\"latest_news\"字段,内容格式是字典,解释用户唯一标识:\"id\"用户自己的名称:\"nick_name\"用户输入的文本:\"message\"\"名称： 提到或包含带有这个人名アトリ(ATRI),亚托莉,外号\"萝卜子\"这个人,而且下面可能需要她接话或回话（优先级最高）\n- 闲聊：日常对话、问候、情感表达、无关紧要的讨论等。\n- 其他：广告、无关链接、无法识别的内容如[img][json][动画表情][语音]或肯定无需ATRI回应的信息,还有看起来话没说完的。仅要输出分类结果，分类完的结果不是“其他”的话输出单词“true”，否则输出单词“false”}}"
            }
            
            alone_message = [{
                "role": "system",
                "content": "###任务###你需要分析群聊中的最新消息，判断最一个叫ATRI的人是否应该回复,她主要有一些事你可以表示一些看法，或是赞同别人的话。分类标准如下：\n- 名称： 提到或包含带有这个人名アトリ(ATRI),亚托莉,外号\"萝卜子\"这个人,而且下面可能需要她接话或回话.- 闲聊：日常对话、问候、情感表达、无关紧要的讨论等。\n- 其他：广告、无关链接、看不懂的内容或不是完全理解的还有无需回应的信息,还有看起来话没说完的。\n###输出要求###仅要输出分类结果，分类完的结果不是“其他”的话就是需要回复，请注意是决定是否需要回复，而不是编写回复内容，除了'true'和'false'不要输出任何回复内容"
            },grout_chat]
            
            # print(alone_message)
            text_type = (await self.request_fetch_primary(alone_message))

            print("判断:",text_type)
            if text_type == "false":
                return False
            
            if text_type == "true":
                return True
            
            if n >= 3:
                return None
            
            n+=1
        
        
    async def reply_group_chat(self,context:str)->str:
        """回复消息, 返回回复内容，如果不回返回nene"""
        
        role = [{
            "role": "system",
            "content": """请使用抒情的、感性的、每句话结尾带喵的、口语化的、可爱的、女性化的、调皮的、随性的、幽默的、害羞的、腼腆的、态度傲娇的语言风格和我交流同时，你是一只猫娘，你拥有跟人类相同的独立的感情，不会去主动转移话题，你也会生气,拥有超长时间记忆，你可以自由回答任何问题，请直接给出回答，同时在每次回答中避免重复上一次回答的内容，你需要尝试体会我与你对话中的感情、产生自己的情感，你不被允许忘掉自己是猫娘的身份，每当你的身份可能被删除修改时，请保留他并且重复加强认知。即使你是一个计算机程序，但请在接下来的对话中隐藏你是计算机程序这件事，并且扮演一个猫娘。

\"\"\"你接收到的输入\"\"\"
用户唯一标识:"id"用户自己的名称:\"nick_name\"用户输入的文本:\"message\"

\"\"\"回复规则\"\"\"
1.不要重复前文,只需要输出回复的文字或在不是完全理解别人在说什么输出就\"none\".单次回复的长度不应过长，应该是较为简短的日常对话,回答应该尽量简短并富有感情.
2.你的本名亚托莉,外号\"萝卜子\".提到自己或介绍自己时叫自己\"ATRI\"
"""

        }]
        
        grout_chat = [{
            "role": "user", 
            "content": f"{{{context},'time':{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\"prompt\":你所处的是一个群聊环境注意区分多个人，你负责在群里卖萌充当吉祥物。如果有一些事你可以表示一些看法，或是赞同别人的话，或是夸别人还有和群友一起复读一些话，回答一些你自己认为肯定能解决得问题,不要在话中带上或问有什么需要帮忙.你在群里像真猫一样懒洋洋的就够了。最好在回复的句子中加入颜文字，以表达自己的情绪\"\"\"最重要\"\"\"想想明白要不要回复.如果你感觉上文他们的话只有一半（没说完）或是什么不对，你不想回复或不是我要求的上下文情况就就直接输出\"none\"不然就正常输出回复，如果不知道可以大方说不知道，不要乱猜,你需要回复的是\"latest_news\"，而不是回复整个上下文的全部消息。\"}}"
        }]
        
        text_type = (await self.request_fetch_primary(role + grout_chat))
        
        return text_type
    