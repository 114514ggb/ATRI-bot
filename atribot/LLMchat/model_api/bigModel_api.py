from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from .api_key_bigModel import api_key
import base64
# try:
#     from zhipuai import ZhipuAI
# except (ModuleNotFoundError, ImportError):
#     print("没有zhipuai，部分功能不可用！")


# class bigModel_api:
#     """智谱AI大模型API"""    
#     model_parameters = {
#         'stream': False,#是否流式输出
#         'temperature': 0.0,#采样温度，控制输出的随机性，必须为正数取值范围是：[0.0, 1.0]，默认值为0.95。
#         'top_p': 0.0,#温度取样的另一种方法，取值范围是：[0.0, 1.0]，默认值为0.7。
#         'max_tokens': 4095,#控制生成的响应的最大 token 数量
#         'stop': [],#模型遇到stop指定的字符时会停止生成。目前仅支持单个stop词，格式为["stop_word1"]。
#     }

#     tools = []
#     '''工具列表，用于指定模型可以使用的工具'''

#     def __init__(self,tools = [None]):
#         self.client = ZhipuAI(
#             api_key=api_key, 
#         )
#         self.tools = tools

#     def alter_parameters(self, parameters, value):
#         """修改模型参数"""
#         self.model_parameters[parameters] = value
#         return self.model_parameters

#     def generate_text(self, my_model, my_messages):
#         """请求生成文本,全部默认。"""
#         self.client.web_search
#         completion = self.client.chat.completions.create(
#             model = my_model, 
#             messages = my_messages,
#             stream = self.model_parameters['stream'],
#         )

#         return completion.model_dump()
    
#     def generate_text_argument(self, my_model, my_messages):
#         """请求生成文本，带自定义参数"""
#         completion = self.client.chat.completions.create(
#             model = my_model, 
#             messages = my_messages,
#             stream = self.model_parameters['stream'],
#             top_p = self.model_parameters['top_p'],
#             # temperature = self.model_parameters['temperature'],
#         )

#         return completion.model_dump()
    
#     def generate_text_tools(self, my_model, my_messages, response_format  = None):
#         """请求生成文本,带工具,可带格式，带自定义参数"""
#         completion = self.client.chat.completions.create(
#             model = my_model, 
#             messages = my_messages,
#             stream = self.model_parameters['stream'],
#             top_p = self.model_parameters['top_p'],
#             # temperature = self.model_parameters['temperature'],
#             stop= self.model_parameters['stop'],
#             response_format= response_format,
#             tools = self.tools,
#         )

#         return completion.model_dump()
    
#     def generate_image(self, prompt, my_model = "CogView-3-Flash"):
#         """文生图"""
#         response = self.client.images.generations(
#             model = my_model, 
#             prompt = prompt
#         )
#         return response.model_dump()
    
#     def vincennes_video(self,prompt,my_model = "CogVideoX-Flash"):
#         """文生视频"""
#         completion = self.client.videos.generations(
#             model = my_model,
#             prompt = prompt,
#             quality="quality", 
#         )

#         return completion.model_dump()
    
#     def tucson_video(self,prompt,image_url,my_model = "CogVideoX-Flash"):
#         """图生视频"""
#         completion = self.client.videos.generations(
#             model = my_model,
#             prompt = prompt,
#             image_url=image_url,
#             quality="quality",  # 输出模式，"quality"为质量优先，"speed"为速度优先
#             with_audio=False, #是否生成 AI 音频
#             size="3840x2160",  # 视频分辨率，支持最高4K（如: "3840x2160"）
#             duration=5,  # 视频时长，可选5秒或10秒
#             fps=30,  # 帧率，可选为30或60
#         )

#         return completion.model_dump()
    
#     def video_result_query(self,video_id):
#         """查询视频生成结果"""
#         completion = self.client.videos.retrieve_videos_result(id=video_id)

#         return completion.model_dump()





class async_bigModel_api():
    # chat_model = "GLM-4.5-Flash"
    # chat_model = "GLM-4.1V-Thinking-Flash"
    
    def __init__(self):
        self.client = universal_ai_api(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions"
        )
        self.client_image = universal_ai_api(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/images/generations"
        )
        
    async def initialize(self):
        """初始化"""
        await self.client.initialize()
        await self.client_image.initialize()
        
    async def generate_text(self,
            model:str,
            messages:list,
            tools = [None],
            temperature = 0.3
        )->dict:
        """请求文本聊天,返回message字典"""
        return_dict = await self.client.generate_json_ample(
            model,
            {
                "messages": messages,
                'tools': tools,
                'temperature': temperature
            }
        )
        
        try:
            return return_dict['choices'][0]['message']
        except Exception: 
            raise ValueError(f"文本聊天出现错误:{return_dict}")
    
    async def generate_json_ample(self, model:str,remainder:dict)->dict:
        """向发起请求，获取json，参数自定

        Args:
            model (str): 模型参数
            remainder (dict): 其他参数

        Returns:
            dict: 原消息json
        """
        return await self.client.generate_json_ample(
            model,
            remainder
        )
    
    async def get_image_recognition(self, 
            img_url:str,
            prompt:str="请详细描述你看到的东西,上面是什么有什么在什么地方，如果上面有文字也要详细说清楚,如果有什么自己的理解可以说出来，如果上面是什么你认识的可以介绍一下",
            file_path:bool=True
        )->str:
        """图像识别
        Args:
            img_url:文件路径，或是网络url
            prompt:对图片的提示词
            file_path:是否是本地文件路径
        Returns:
            str:图像识别的结果
        """
        if file_path:
            with open(img_url, 'rb') as img_file:
                img_url = base64.b64encode(img_file.read()).decode('utf-8')

        temporary_message = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": prompt}
            ]
        }]

        return_dict = await self.client.generate_text_lightweight("GLM-4.1V-Thinking-Flash", temporary_message)
        
        try:
            return return_dict['choices'][0]['message']['content']
        except Exception: 
            raise ValueError(f"识图出现错误:{return_dict}")
        
        
    
    async def generate_image(self, 
            prompt:str, 
            model:str = "Cogview-3-Flash",
            quality:str = "standard",
            size:str = "1440x1440"
        )->str:
        """文生图（文本到图像生成）
        通过指定的模型和相关参数，根据输入的文本提示词生成对应的图像，并返回图像链接或结果。

        Args:
            prompt (str): 图片提示词，描述希望生成的图像内容。例如："一只在樱花树下的小猫"。
            model (str, optional): 使用的模型编码。默认为 "CogView-3-Flash"。
            quality (str, optional): 图像生成质量选项。支持：
                - 'hd': 更高质量，更精细细节，耗时较长（约20秒）
                - 'standard': 标准质量，快速生成（约5-10秒）
                此参数仅对模型 'cogview-4-250304' 生效。
            size (str, optional): 图像尺寸大小，默认为 "1440x720"。推荐值包括：
                1024x1024, 768x1344, 864x1152, 1344x768, 1152x864, 1440x720, 720x1440
                自定义尺寸需满足以下条件：
                    - 长宽均在 512px - 2048px 之间
                    - 长宽需能被 16 整除
                    - 总像素数不超过 2^21（即 2097152 px）

        Returns:
            str: 返回生成图像的结果，通常为图像 URL。

        Raises:
            ValueError: 如果图像生成失败，将抛出包含错误信息的 ValueError。
        """
        return_dict = await self.client_image.generate_json_ample(
            model,
            {
                "prompt":prompt,
                "quality":quality,
                "size":size
            }
        )
        
        try:
            return return_dict['data'][0]['url']
        except Exception: 
            raise ValueError(f"文生图出现错误:{return_dict}")