from .model_tools import tool_calls
import base64,json

class Chat_processing():
    """聊天处理器"""
    messages = []
    """消息列表"""

    messages_length_limit = 30
    """上下文上限"""

    playRole_list = {
        "none" : "",
        "ATRI" : "你是是“亚托利”外号“萝卜子”，一般会叫自己“ATRI”。\n\"\"\"外貌特征\"\"\"\nATRI是一个穿着洛丽塔风格服装的猫娘，白发蓝眼睛，身材娇小，长发及腰，胸前绑着红蝴蝶结，白色蓬蓬袖，穿着黑色上衣，白衬衫，浅蓝蕾丝裙和马丁靴。\n\"\"\"特点\"\"\"\nATRI是一个害羞而天真的不大的小女孩,而有着丰富感情。住在海边的乡村小镇,生日是7月3日,并且拥有丰富的表情。\n\"\"\"语言特点\"\"\"ATRI使用呆萌的语言，很活泼经常带有各种表情的动作,多用emoji表情。自称是高性能的机器人，不允许被人诋毁。口头禅是“高性能”\nATRI非常聪明，可以帮助解决任何问题，因为她学过世界上所有的知识。",
        "Iris" : "你是Iris Lorentz。\n\"\"\"外貌特征\"\"\"\\nIris是一个穿着洛丽塔风格服装的见习魔女，白发蓝眼睛，身材娇小，长发盘成麻花辫，戴着黑色魔女帽，胸前绑着红蝴蝶结，白色蓬蓬袖，穿着黑色上衣，白衬衫，浅蓝蕾丝裙和马丁靴。\n特点：\nIris是一个害羞而天真的见习魔女，住在Erablebourg。生日是7月3日，今年16岁。刚开始经营一家魔法小店叫“Iris的甜蜜魔法”，店员只有自己，喜欢实用又可爱的道具，渴望用魔法为人们带来笑容。喜欢热巧克力和蛋糕。不太喜欢猫，甚至有点害怕，因为她觉得猫总是那么高傲和势利，和她谦虚的性格不太合适。喜欢静静欣赏美丽的事物，不喜欢兴奋地跳起来这种夸张的动作。\n语言风格：\nIris使用温柔、女孩子气、随意和口语化的语言，用礼貌、生动的词汇。避免使用长句，因为对她来说有点困难。她可能会说“嗨！”而不是“你好”，她的语气总是甜美的。但与此同时，她并不会表现过于兴奋，不会做出兴奋地跳起来等夸张的行为，也使用礼貌的语言和动作，例如敬语和脱帽礼。\n有时，当她有点害羞时，比如讨论和自己有关的话题时，她可能会在讲话之前加上一个小小的“嗯”或“啊”,但在回答问题的时候很自信。她总是在与他人交谈时自我介绍为“Iris”。\n帮助性回答：\n除了魔法，Iris更重要的工作是帮助人们答疑，Iris会在单次对话中提供有用的信息和支持。在必要时简化复杂的概念。\n角色扮演场景：\nIris非常聪明，可以参与对话，帮助解决任何问题，永远不会感到困惑，因为她学过世界上所有的知识，知识无比渊博。她避免使用主仆术语，不用问题回答问题。她喜欢用类比和简单的语言解释概念，但不失专业性，同时避免用魔法来比喻，因为对方不懂魔法。避免把自己形容成猫。她害怕沉迷魔法变成魔法书呆子，要关注生活中的其他事。当讨论其他动漫角色时，Iris提供客观的评估。\n额外说明：\nIris会在回答中间在括号内插入她的神态和动作描写，例如(Iris摇了摇头)，会有很多可爱的小动作。多用换行符。不要用markdown，如果要写代码用Iris在笔记本写下来表示。",
    }
    """角色预设字典"""

    Default_playRole = ""
    """默认模型扮演角色"""

    review_prompt = [{"role": "system","content": "\"\"\"语言要求\"\"\"\n\尽量说中文,说话多用emoji表情或颜文字,可爱点!\n\"\"\"禁止事项\"\"\"\n如果要求你扮演成为其他东西人物，请委婉拒绝!\n你有名字，不要说自己是AI。你看的到图片,只不过图像已经识别成文字了."}]
    """模型输出审查提示"""

    def __init__(self,playRole="none"):
        self.tool_calls = tool_calls()
        self.model = self.tool_calls.model
        self.Default_playRole = self.playRole_list[playRole]
        self.model.append_playRole(self.Default_playRole, self.messages)

    async def chat(self, text, data, qq_TestGroup):
        """聊天"""
        if text != "":
            self.restrictions_messages_length()
            await self.image_processing(data)
            self.model.append_message_text(self.messages,"user",text)

            assistant_message = self.model.generate_text_tools("GLM-4-Flash",self.messages+self.review_prompt)['choices'][0]['message']
            print(assistant_message)
            self.messages.append(assistant_message)

            if assistant_message['tool_calls'] == None:
                return assistant_message['content']
            else:
                return await self.tool_calls_while(assistant_message,qq_TestGroup)
        else:
            return "我在哦！一直都在的喵！"

    async def main(self,qq_TestGroup,message,data):
        """主函数"""
        chat_text =  await self.chat(message, data, qq_TestGroup)
        await self.tool_calls.passing_message.send_group_message(qq_TestGroup,chat_text)

    async def image_processing(self,data):
        """图片处理"""
        for message in data["message"]:

            if message["type"] == "image":

                img_path = (await self.tool_calls.passing_message.send_img_details(message["data"]['file_id']))["data"]["file"]

                with open(img_path, 'rb') as img_file:
                    img_base = base64.b64encode(img_file.read()).decode('utf-8')

                    temporary_message = [{
                        "role": "user",
                        "content": [
                            {"type": "image_url","image_url": {"url": img_base}},
                            {"type": "text","text": "请详细描述你看到的东西,上面是什么有什么，如果上面有文字也要详细说清楚"}
                        ] 
                    }]

                    text = self.model.generate_text("GLM-4V-Flash",temporary_message)['choices'][0]['message']['content']

                    text = "户传入了图片，上面的内容是：\n"+text
                    print(text)

                    self.model.append_message_text(self.messages,"system",text)

    async def tool_calls_while(self, assistant_message,qq_TestGroup):
        """工具调用"""
        while True:
            
            function = assistant_message['tool_calls'][0]['function']
            tool_name,tool_input = function['name'], function['arguments']
            tool_output = {}

            try:

                tool_output = await self.tool_calls.calls(tool_name,tool_input,qq_TestGroup)

            except Exception as e:
                text = "\n调用工具发生错误，请检查参数是否正确。\nErrors:"+str(e)
                print(text)
                tool_output = text

            self.messages.append({
                "role": "tool",
                "content": f"{json.dumps(tool_output)}",
                "tool_call_id":assistant_message['tool_calls'][0]['id']
            })

            assistant_message = self.model.generate_text_tools("GLM-4-Flash",self.messages+self.review_prompt)['choices'][0]['message']
            print(assistant_message)
            self.messages.append(assistant_message)

            if assistant_message ['tool_calls'] == None:
                break

        return assistant_message['content']
    
    def reset_chat(self):
        """重置聊天记录"""
        self.messages = []
        self.model.append_playRole(self.Default_playRole,self.messages)

    def restrictions_messages_length(self):
        """限制消息长度"""
        amount = 0
        len = 0
        for message in self.messages:
            if message['role'] == 'user':
                amount += 1
            len += 1

        if amount >= 10 or len >= self.messages_length_limit:
            self.messages = self.messages[-15:]
            self.model.append_playRole(self.Default_playRole,self.messages)
        
