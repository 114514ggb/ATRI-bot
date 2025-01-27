from zhipuai import ZhipuAI
from .api_key_bigModel import api_key

class bigModel_api:
    """智谱AI大模型API"""    
    model_parameters = {
        'stream': False,#是否流式输出
        'temperature': 0.95,#采样温度，控制输出的随机性，必须为正数取值范围是：[0.0, 1.0]，默认值为0.95。
        'top_p': 0.5,#温度取样的另一种方法，取值范围是：[0.0, 1.0]，默认值为0.7。
        'max_tokens': 4095,#控制生成的响应的最大 token 数量
        'stop': [],#模型遇到stop指定的字符时会停止生成。目前仅支持单个stop词，格式为["stop_word1"]。
    }

    tools = []
    '''工具列表，用于指定模型可以使用的工具'''

    def __init__(self,tools = [None]):
        self.client = ZhipuAI(
            api_key=api_key, 
        )
        self.tools = tools

    def alter_parameters(self, parameters, value):
        """修改模型参数"""
        self.model_parameters[parameters] = value
        return self.model_parameters
    
    def append_playRole(self,content,messages:list):
        """添加扮演的角色，固定为列表的第一个元素"""
        if content != "":
            messages.append({"role": "system","content": content})
        return messages
    
    def append_message_text(self,messages:list,role:str,content:str):
        """添加文本消息,role为角色,content为内容"""
        messages.append({"role": role,"content": content})
        return messages
    
    def append_message_image(self,messages:list,image_url, text="请详细描述这个图片，如果上面有文字也要详细说清楚", role = "user"):
        """添加带图片消息,role为角色,image_url为图片链接,text为问题文字"""
        messages.append({
            "role": role,
            "content": [
                {"type": "image_url","image_url": {"url": image_url}},
                {"type": "text","text": text}
            ]  
        })

        return messages

    def generate_text(self, my_model, my_messages):
        """请求生成文本,全部默认。"""
        completion = self.client.chat.completions.create(
            model = my_model, 
            messages = my_messages,
            stream = self.model_parameters['stream'],
        )

        return completion.model_dump()
    
    def generate_text_argument(self, my_model, my_messages):
        """请求生成文本，带自定义参数"""
        completion = self.client.chat.completions.create(
            model = my_model, 
            messages = my_messages,
            stream = self.model_parameters['stream'],
            top_p = self.model_parameters['top_p'],
            # temperature = self.model_parameters['temperature'],
        )

        return completion.model_dump()
    
    def generate_text_tools(self, my_model, my_messages, response_format  = None):
        """请求生成文本,带工具,可带格式，带自定义参数"""
        completion = self.client.chat.completions.create(
            model = my_model, 
            messages = my_messages,
            stream = self.model_parameters['stream'],
            top_p = self.model_parameters['top_p'],
            # temperature = self.model_parameters['temperature'],
            stop= self.model_parameters['stop'],
            response_format= response_format,
            tools = self.tools,
        )

        return completion.model_dump()
    
    def generate_image(self, prompt, my_model = "CogView-3-Flash"):
        """文生图"""
        response = self.client.images.generations(
            model = my_model, 
            prompt = prompt
        )
        return response.model_dump()
    
    def vincennes_video(self,prompt,my_model = "CogVideoX-Flash"):
        """文生视频"""
        completion = self.client.videos.generations(
            model = my_model,
            prompt = prompt,
            quality="quality", 
        )

        return completion.model_dump()
    
    def tucson_video(self,prompt,image_url,my_model = "CogVideoX-Flash"):
        """图生视频"""
        completion = self.client.videos.generations(
            model = my_model,
            prompt = prompt,
            image_url=image_url,
            quality="quality",  # 输出模式，"quality"为质量优先，"speed"为速度优先
            with_audio=False, #是否生成 AI 音频
            size="1920x1080",  # 视频分辨率，支持最高4K（如: "3840x2160"）
            duration=5,  # 视频时长，可选5秒或10秒
            fps=30,  # 帧率，可选为30或60
        )

        return completion.model_dump()
    
    def video_result_query(self,video_id):
        """查询视频生成结果"""
        completion = self.client.videos.retrieve_videos_result(id=video_id)

        return completion.model_dump()