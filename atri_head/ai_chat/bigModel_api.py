from zhipuai import ZhipuAI
from .api_key_bigModel import api_key

class bigModel_api:
    """智谱AI大模型API"""    
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
    '''交互消息列表,上下文'''

    def __init__(self,tools = [None]):
        self.client = ZhipuAI(
            api_key=api_key, 
        )
        self.tools = tools

    def alter_parameters(self, parameters, value):
        """修改模型参数"""
        self.model_parameters[parameters] = value
        return self.model_parameters
    
    def del_messages(self):
        """删除消息"""
        self.messages = []
        return True
    
    def append_message_text(self,messages,role,content):
        """添加文本消息,role为角色,content为内容"""
        messages.append({"role": role,"content": content})
        return True
    
    def append_message_image(self,messages:list,image_url, text="请描述这个图片", role = "user"):
        """添加带图片消息,role为角色,image_url为图片链接,text为问题文字"""
        messages.append({
            "role": role,
            "content": [
                {"type": "image_url","image_url": {"url": image_url}},
                {"type": "text","text": text}
            ]  
        })

        return True

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
            frequency_penalty = self.model_parameters['frequency_penalty'],
            top_p = self.model_parameters['top_p'],
            temperature = self.model_parameters['temperature'],
            max_tokens = self.model_parameters['max_tokens'],
        )

        return completion.model_dump()
    
    def generate_text_tools(self, my_model, my_messages, response_format  = None):
        """请求生成文本,带工具,可带格式，带自定义参数"""
        completion = self.client.chat.completions.create(
            model = my_model, 
            messages = my_messages,
            stream = self.model_parameters['stream'],
            frequency_penalty = self.model_parameters['frequency_penalty'],
            top_p = self.model_parameters['top_p'],
            temperature = self.model_parameters['temperature'],
            max_tokens = self.model_parameters['max_tokens'],
            response_format = response_format,
            tools = self.tools,
        )

        return completion.model_dump()
    
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
            duration=10,  # 视频时长，可选5秒或10秒
            fps=30,  # 帧率，可选为30或60
        )

        return completion.model_dump()
    
    def video_result_query(self,video_id):
        """查询视频生成结果"""
        completion = self.client.videos.retrieve_videos_result(id=video_id)

        return completion.model_dump()