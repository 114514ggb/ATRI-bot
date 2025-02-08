from openai import AsyncOpenAI

class async_openAI:
    """async OpenAI API"""
    model_parameters = {
        'stream': False,#是否流式输出
        'frequency_penalty': 1.5,#一个介于-2.0和2.0之间的数字。正值会根据文本中至今出现的频率对新令牌进行惩罚，降低模型重复同一行文字的可能性。
        'top_p':0.8,#核采样的概率阈值，用于控制模型生成文本的多样性。top_p越高，生成的文本更多样。反之，生成的文本更确定。取值范围：（0,1.0]
        'temperature': 1.5,#控制生成文本的随机性。生成的文本更多样，反之，生成的文本更确定。 取值范围： [0, 2) temperature和top_p一般只设置一个
        'max_tokens': 8192,#生成文本的最大长度
        'stop': None,#当模型生成的文本即将包含指定的字符串或token_id时，将自动停止生成。
    }

    tools = []
    '''工具列表，用于指定模型可以使用的工具'''

    messages = []

    def __init__(self, api_key, base_url, tools = [None]):
        self.client = AsyncOpenAI(
            api_key=api_key, 
            base_url=base_url,
        )
        self.tools = tools

    def alter_parameters(self, parameters, value):
        """修改参数"""
        self.model_parameters[parameters] = value
        return self.model_parameters
    
    def append_message_text(self,role,content):
        """添加文本消息,role为角色,content为内容"""
        self.messages.append({"role": role,"content": content})
        return True
    
    def append_message_image(self,image_url, text="请描述这个图片", role = "user"):
        """添加带图片消息,role为角色,image_url为图片链接,text为问题文字"""
        self.messages.append({
            "role": role,
            "content": [
                {"type": "image_url","image_url": {"url": image_url}},
                {"type": "text","text": text}
            ]  
        })

        return True

    async def generate_text(self, my_model, my_messages):
        """请求生成文本,全部默认。"""
        completion = await self.client.chat.completions.create(
            model = my_model, 
            messages = my_messages,
        )

        return completion.model_dump()

    async def generate_text(self, my_model, my_messages):
        """请求生成文本,全部默认。"""
        completion = await self.client.chat.completions.create(
            model = my_model, 
            messages = my_messages,
        )

        return completion.model_dump()

    async def generate_text_argument(self, my_model, my_messages):
        """请求生成文本，带自定义参数"""
        completion = await self.client.chat.completions.create(
            model = my_model, 
            messages = my_messages,
            frequency_penalty = self.model_parameters['frequency_penalty'],
            top_p = self.model_parameters['top_p'],
            temperature = self.model_parameters['temperature'],
            max_tokens = self.model_parameters['max_tokens'],
        )

        return completion.model_dump()
    
    async def generate_text_tools(self, my_model, my_messages, response_format= {"type": "text"}):
        """请求生成文本,带工具,可带格式，带自定义参数"""
        completion = await self.client.chat.completions.create(
            model = my_model, 
            messages = my_messages,
            frequency_penalty = self.model_parameters['frequency_penalty'],
            top_p = self.model_parameters['top_p'],
            temperature = self.model_parameters['temperature'],
            max_tokens = self.model_parameters['max_tokens'],
            response_format = response_format,
            tools = self.tools,
        )

        return completion.model_dump()
    
    async def request_fetch_primary(self, my_messages:list ,my_model = "gemini-2.0-flash-exp-search",response_format= {"type": "text"}):
        """请求生成文本，返回主要内容"""
        data = await self.generate_text_tools(my_model, my_messages,response_format)
        # print(data)
        return data['choices'][0]['message']