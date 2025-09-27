from abc import ABC, abstractmethod


class model_api_basics(ABC):
    """LLM api 基类"""
    
    model_parameters = {
        'stream': False,#是否流式输出如果设置为 True，将会以 SSE（server-sent events）的形式以流式发送消息增量。消息流以 data: [DONE] 结尾。

        'frequency_penalty': 1.5,#介于 -2.0 和 2.0 之间的数字。如果该值为正，那么新 token 会根据其在已有文本中的出现频率受到相应的惩罚，降低模型重复相同内容的可能性。

        'presence_penalty':0.5, #介于 -2.0 和 2.0 之间的数字。如果该值为正，那么新 token 会根据其是否已在已有文本中出现受到相应的惩罚，从而增加模型谈论新主题的可能性。

        #'top_p':0.4,#作为调节采样温度的替代方案，模型会考虑前 top_p 概率的 token 的结果。所以 0.1 就意味着只有包括在最高 10% 概率中的 token 会被考虑。
        
        'temperature': 0,#采样温度，介于 0 和 2 之间。更高的值，如 0.8，会使输出更随机，而更低的值，如 0.2，会使其更加集中和确定。
        # #不建议同时对'top_p','temperature'进行修改 

        'max_tokens': 8192,#介于 1 到 8192 间的整数，限制一次请求中模型生成 completion 的最大 token 数。输入 token 和输出 token 的总长度受模型的上下文长度的限制。

        'tool_choice': "auto",#控制模型调用 tool 的行为
        # # none 意味着模型不会调用任何 tool，而是生成一条消息。
        # # auto 意味着模型可以选择生成一条消息或调用一个或多个 tool。
        # # required 意味着模型必须调用一个或多个 tool。
        # # 好像只有DS有
        # # 通过 {"type": "function", "function": {"name": "my_function"}} 指定特定 tool，会强制模型调用该 tool。
        
        # 'stop': None
        #一个 string 或最多包含 16 个 string 的 list，在遇到这些词时，API 将停止生成更多的 token。

        # 'response_format': { 
        #     "type": "text"
        # },
        #响应格式
        #设置为 { "type": "json_object" } 以启用 JSON 模式
        # 注意: 使用 JSON 模式时，你还必须通过系统或用户消息指示模型生成 JSON。
        # 否则，模型可能会生成不断的空白字符，直到生成达到令牌限制，从而导致请求长时间运行并显得“卡住”。
    }
    """模型参数"""
    
    def __init__(self, 
            api_key = "", 
            base_url = ""
        ):
        self.base_url = base_url
        self.api_key = api_key
        
        
    @abstractmethod
    async def generate_text_tools(self, model:str, messages:list, tools:list)->dict:
        """请求生成文本，全量默认参数

        Args:
            model (str): 模型
            messages (list): 上下文
            tools (list): 可使用工具

        Returns:
            dict: 原消息json
        """
    
    @abstractmethod
    async def generate_json_ample(self, model:str,remainder:dict)->dict:
        """向发起请求，获取json，参数自定

        Args:
            model (str): 模型名称
            remainder (dict): 其他参数

        Returns:
            dict: 原消息json
        """
    
    def alter_parameters(self, parameters:str, value:float|bool|dict):
        """修改模型单个默认参数"""
        self.model_parameters[parameters] = value
        
    def update_parameters(self, new_parameters: dict):
        """用新字典更新久参数字典"""
        self.model_parameters |= new_parameters
    
    async def request_fetch_primary(self, model:str, messages:list[dict] ,tools:list, temperature:int = 0.3)->dict:
        """向发起请求，返回主要内容

        Args:
            model (str): 模型
            messages (list[dict]): 上下文
            tools (list): 可使用工具
            temperature (int, optional): 模型温度. Defaults to 0.3.

        Returns:
            dict: 处理过的字典
        """
        data = await self.generate_json_ample(
            model, 
            remainder = {
                'messages': messages,
                'tools': tools,
                'temperature' : temperature,
                'tool_choice': "auto" #有的模型要开启这个才能调用工具
            }
        )
        try:
            return data['choices'][0]['message']
        except EOFError:
            raise ValueError(data)
        
    def __str__(self):
        return f"url:{self.base_url},api_key:{self.base_url}"