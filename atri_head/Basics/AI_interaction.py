from gradio_client import Client
from ..ai_chat.chat_main import Chat_processing

class AI_interaction():

    def __init__(self,playRole):
        self.chat = Chat_processing(playRole)

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
        
