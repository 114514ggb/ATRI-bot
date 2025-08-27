
# from ..ai_chat.chat_main import Chat_processing
from ..ai_chat.test_initiative_chat import initiative_chat
# from gradio_client import Client
import httpx
# import asyncio

"""
这里tts路径要手动改
"""

class AI_interaction():
    """一些和ai有关的API"""
    
    def __init__(self):
        # self.chat = Chat_processing(playRole)
        self.auto_response = initiative_chat()
        self.audio_count:int = 1
    

    # async def speech_synthesis(self, text:str):
    #     """语音合成,返回音频文件路径,长度不会超过500(已废弃)
        
    #     Args:
    #         text (str): 需要合成的文本

    #     Raises:
    #         RuntimeError: 超时错误

    #     Returns:
    #         str: 文件的在文件系统的路径
    #     """
    #     client = Client("http://localhost:9872/")
    #     job = client.submit(
    #                     "E:/ffmpeg/.......我为了夏生先生行动需要理由吗.mp3",
    #                     # "E:\\ffmpeg\\啊我真是太高性能了.mp3",	
    #                     # str (filepath on your computer (or URL) of file) in '请上传3~10秒内参考音频，超过会报错！' Audio component
    #                     "あ，私です夏生さんのために動く理由が必要なんですか",
    #                     # "あ、なんて高性能なの、私は！",	
    #                     # str in '参考音频的文本' Textbox component
    #                     "日文",	# str (Option from: ['中文', '英文', '日文', '中英混合', '日英混合', '多语种混合']) in '参考音频的语种' Dropdown component
    #                     text[:500],	# str in '需要合成的文本' Textbox component
    #                     "多语种混合",	# str (Option from: ['中文', '英文', '日文', '中英混合', '日英混合', '多语种混合']) in '需要合成的语种' Dropdown component
    #                     "凑四句一切",	# str in '怎么切' Radio component
    #                     30,	# float (numeric value between 1 and 100) in 'top_k' Slider component
    #                     1,	# float (numeric value between 0 and 1) in 'top_p' Slider component
    #                     1,	# float (numeric value between 0 and 1) in 'temperature' Slider component
    #                     False,	# bool in '开启无参考文本模式。不填参考文本亦相当于开启。' Checkbox component
    #                     fn_index=3
    #     )
        
    #     max_attempts = 60  # 最大尝试次数
    #     for _ in range(max_attempts):
    #         status = job.status()
            
    #         if status.success:
    #             result:str = job.result()

    #             return "/mnt/c" + result[2:].replace("\\", "/")
            
    #         await asyncio.sleep(0.5)
            
    #     raise RuntimeError("tts合成错误,可能是服务端超时，或内容太长,或输入不支持的语言.")

    async def get_tts_path(self,test:str,emotion:str="高兴",speed:float=1)->str:
        """tts文本合成语音
        
        Args:
            text (str): 需要合成的文本,支持中日英韩，但是目前不要输入韩文
            emotion (str): 音频的情感,枚举值：高兴,机械,平静
            speed (float): 语速，取值范围0.6~1.65,默认1
            
        Raises:
            ValueError: 抛出包含错误信息的json

        Returns:
            str: 返回wav文件的相对路径
        """
        # raise ValueError("语音因为资源分配问题暂时被关了,不要再尝试使用")
        
        api_url = "http://127.0.0.1:9880"
        
        emotion_list = {
            "高兴":{
                "refer_wav_path": "E:/ffmpeg/ああ、なんて高性能なんでしょ、私は.mp3",
                "prompt_text": "ああ、なんて高性能なんでしょ、私は",
                "prompt_language": "ja"
            },
            "机械":{
                "refer_wav_path": "E:/ffmpeg/あ，私です夏生さんのために動く理由が必要なんですか.mp3",
                "prompt_text": "あ，私です夏生さんのために動く理由が必要なんですか",
                "prompt_language": "ja"
            },            
            "平静":{
                "refer_wav_path": "E:/ffmpeg/夏生さんが望むのでしたら.mp3",
                "prompt_text": "夏生さんが望むのでしたら",
                "prompt_language": "ja"
            }
        }
        
        if emotion not in emotion_list:
            raise ValueError(f"不支持的情感:{emotion}")
        
        if len(test) > 100:
            raise ValueError(f"输入不能超过100个字符,当前有{len(test)}个")
        
        payload = {
            "text": test,
            "text_language": "auto",
            "top_k": 20,
            "top_p": 0.6,
            "temperature": 0.6,
            "speed": speed,
            "inp_refs": ["E:/ffmpeg/ああ、なんて高性能なんでしょ、私は.mp3","E:/ffmpeg/あ，私です夏生さんのために動く理由が必要なんですか.mp3",]#辅助音频
        } | emotion_list[emotion]
        
        try:
            async with httpx.AsyncClient() as session:
                response = await session.post(api_url, json=payload)
                if response.status_code == 200:
                    # print("成功获取音频数据")
                    audio_bytes = response.read()
                    audio_relatively = f"TTS_output/output{self.audio_count}.wav"
                    
                    if self.audio_count != 10:
                        self.audio_count += 1
                    else:
                        self.audio_count = 1
                    
                    with open(f"E:/程序文件/python/ATRI/document/audio/{audio_relatively}", "wb") as f:
                        f.write(audio_bytes)
                        
                    return audio_relatively
                else:
                    error_data = response.json()
                    # print("TTS请求失败:", error_data)
                    raise ValueError(f"TTS请求失败{error_data}")
        except EOFError:
            raise ValueError("该功能未启用！")
                        