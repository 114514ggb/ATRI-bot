from abc import ABC, abstractmethod
from logging import Logger
from typing import AsyncGenerator

from atribot.core.service_container import container
from atribot.LLMchat.model_api.llm_types import ChatCompletion, ChatCompletionChunk


class model_api_basics(ABC):
    """LLM api 基类"""
    
    model_parameters = {
        'stream': False,#是否流式输出如果设置为 True，将会以 SSE(server-sent events)的形式以流式发送消息增量消息流以 data: [DONE] 结尾

        # 'frequency_penalty': 1.5,#介于 -2.0 和 2.0 之间的数字如果该值为正，那么新 token 会根据其在已有文本中的出现频率受到相应的惩罚，降低模型重复相同内容的可能性

        # 'presence_penalty':0.5, #介于 -2.0 和 2.0 之间的数字如果该值为正，那么新 token 会根据其是否已在已有文本中出现受到相应的惩罚，从而增加模型谈论新主题的可能性

        #'top_p':0.4,#作为调节采样温度的替代方案，模型会考虑前 top_p 概率的 token 的结果所以 0.1 就意味着只有包括在最高 10% 概率中的 token 会被考虑
        
        'temperature': 0.5,#采样温度，介于 0 和 2 之间更高的值，如 0.8，会使输出更随机，而更低的值，如 0.2，会使其更加集中和确定
        # #不建议同时对'top_p','temperature'进行修改 

        'max_tokens': 8192,#介于 1 到 8192 间的整数，限制一次请求中模型生成 completion 的最大 token 数输入 token 和输出 token 的总长度受模型的上下文长度的限制

        'reasoning_effort':'high',
        #推理努力程度，值可以是 "low", "medium", "high", "extreme"
        #停用思考功能，可以将 reasoning_effort 设置为 "none"
        #默认值为 "medium"更高的推理努力程度通常会导致更准确和详细的回答，但也可能需要更多的计算资源和时间
        # "extra_body": {
        #     "google": {
        #         "thinking_config": {
        #             "thinking_budget": 800,
        #             "include_thoughts": True
        #         }
        #     }
        # }
        #谷歌模型的openai兼容.思考总结是模型原始思考的合成版本，可帮助您深入了解模型的内部推理过程
        #请注意，思考预算适用于模型的原始想法，而不适用于想法摘要
        
        'tool_choice': "auto",#控制模型调用 tool 的行为
        # # none 意味着模型不会调用任何 tool，而是生成一条消息
        # # auto 意味着模型可以选择生成一条消息或调用一个或多个 tool
        # # required 意味着模型必须调用一个或多个 tool
        # # 好像只有DS有
        # # 通过 {"type": "function", "function": {"name": "my_function"}} 指定特定 tool，会强制模型调用该 tool
        
        # 'stop': None
        #一个 string 或最多包含 16 个 string 的 list，在遇到这些词时，API 将停止生成更多的 token

        # 'response_format': { 
        #     "type": "text"
        # },
        #响应格式
        #设置为 { "type": "json_object" } 以启用 JSON 模式
        # 注意: 使用 JSON 模式时，你还必须通过系统或用户消息指示模型生成 JSON
        # 否则，模型可能会生成不断的空白字符，直到生成达到令牌限制，从而导致请求长时间运行并显得“卡住”
    }
    """模型参数"""
    
    def __init__(self, 
            api_key = "", 
            base_url = "",
            **kwargs
        ):
        super().__init__(**kwargs)
        try:
            self.log: Logger = container.get_by_type(Logger).getChild("ModelAPI")
        except Exception:
            import logging
            logging.basicConfig(level=logging.INFO)
            self.log = logging.getLogger("atri-bot.ModelAPI")
        
        self.base_url = base_url
        self.api_key = api_key
    
    @abstractmethod
    async def close(self):
        """异步关闭客户端"""
        ...

    @abstractmethod
    async def client_post_stream(self, data: dict) -> AsyncGenerator[ChatCompletionChunk]:
        """
        底层流式请求方法,返回支持的Server-Sent Events (SSE) 协议包裹的 JSON 数据
        
        Args:
            data (Dict): 请求体参数
            
        Yields:
            Dict: 原始的 chunk json 数据
        """
        ...

    @abstractmethod
    async def generate_text_tools(self, model:str, messages:list, tools:list)->ChatCompletion:
        """请求生成文本，全量默认参数

        Args:
            model (str): 模型
            messages (list): 上下文
            tools (list): 可使用工具

        Returns:
            dict: 原消息json
        """
        ...
    
    @abstractmethod
    async def generate_json_ample(self, model:str,remainder:dict)->ChatCompletion:
        """向发起请求,获取json,参数自定

        Args:
            model (str): 模型名称
            remainder (dict): 其他参数

        Returns:
            dict: 原消息json
        """
        ...
    
    @abstractmethod
    async def generate_json_ample_stream(self, model: str, remainder: dict) -> ChatCompletion:
        """向发起请求,获取json,参数自定,但是是以流式的方法处理数据，流式接受完成后返回总数据

        Args:
            model (str): 模型名称
            remainder (dict): 其他参数

        Returns:
            dict: 处理后兼容非流式的json数据
        """
        ...
    
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
                'tool_choice': "auto", #有的模型要开启这个才能调用工具
                'stream': False
                # "reasoning_effort": "high",
                # "extra_body": {
                #     "google": {
                #         "thinking_config": {
                #             "include_thoughts": True
                #         }
                #     }
                # }
            }
        )
        try:
            return data['choices'][0]['message']
        except EOFError:
            raise ValueError(data)

    async def generate_image(
        self,
        model: str,
        prompt: str,
        response_format: str = "b64_json",
        n: int = 1,
        size: str | None = None,
        quality: str | None = None,
        style: str | None = None,
        extra_body: dict | None = None,
        background: str | None = None,
        output_format: str | None = None,
        output_compression: int | None = None,
        **kwargs,
    ) -> list[str]:
        """调用图像生成接口(open_ai兼容)，返回图片数据列表

        Args:
            model: 图像生成模型名称
            prompt: 描述目标图像内容的文本提示词
            response_format: 返回图片的格式，可选值为 b64_json 或 url,默认 b64_json
            n: 本次请求生成的图片数量，默认为 1
            size: 图片尺寸
            quality: 图片质量
            style: 图片风格
            extra_body: 一些额外的参数
            background: 图片背景
            output_format: 输出图片格式
                可选: "png" | "jpeg" | "webp"
            output_compression: 输出图片压缩率 0-100(仅webp/jpeg 时有效)
            **kwargs: 传递给底层 API 的其他额外参数

        Returns:
            长度为 n 的字符串列表当 response_format="b64_json" 时，
            列表元素为 Base64 编码的图片字符串；当 response_format="url"
            时，列表元素为可直接访问的图片 URL

        Raises:
            ValueError: 当 API 返回错误或响应格式不符合预期时抛出
        """
        remainder: dict = {
            "prompt": prompt,
            "response_format": response_format,
            "n": n,
            **kwargs
        }
        if size is not None:
            remainder["size"] = size
        if quality is not None:
            remainder["quality"] = quality
        if style is not None:
            remainder["style"] = style
        if background is not None:
            remainder["background"] = background
        if extra_body is not None:
            remainder["extra_body"] = extra_body
        if output_format is not None:
            remainder["output_format"] = output_format
        if output_compression is not None:
            remainder["output_compression"] = output_compression

        data = await self.generate_json_ample(model, remainder=remainder)
        try:
            items = data["data"]
            if response_format == "url":
                return [item["url"] for item in items]
            return [item["b64_json"] for item in items]
        except (KeyError, TypeError):
            raise ValueError(data)

    def __str__(self):
        return f"<model_api,url:{self.base_url}>"