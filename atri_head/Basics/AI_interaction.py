
# from ..ai_chat.chat_main import Chat_processing
from ..ai_chat.test_initiative_chat import initiative_chat
from gradio_client import Client

class AI_interaction():
    """一些和ai有关的API"""
    
    def __init__(self):
        # self.chat = Chat_processing(playRole)
        self.auto_response = initiative_chat()
    

    def speech_synthesis(self, text):
        """语音合成,返回音频文件路径"""
        client = Client("http://localhost:9872/")
        result:str = client.predict(
                        "E:\\ffmpeg\\.......我为了夏生先生行动需要理由吗.mp3",
                        # "E:\\ffmpeg\\啊我真是太高性能了.mp3",	
                        # str (filepath on your computer (or URL) of file) in '请上传3~10秒内参考音频，超过会报错！' Audio component
                        "あ，私です夏生さんのために動く理由が必要なんですか",
                        # "あ、なんて高性能なの、私は！",	
                        # str in '参考音频的文本' Textbox component
                        "日文",	# str (Option from: ['中文', '英文', '日文', '中英混合', '日英混合', '多语种混合']) in '参考音频的语种' Dropdown component
                        text,	# str in '需要合成的文本' Textbox component
                        "多语种混合",	# str (Option from: ['中文', '英文', '日文', '中英混合', '日英混合', '多语种混合']) in '需要合成的语种' Dropdown component
                        "凑四句一切",	# str in '怎么切' Radio component
                        30,	# float (numeric value between 1 and 100) in 'top_k' Slider component
                        1,	# float (numeric value between 0 and 1) in 'top_p' Slider component
                        1,	# float (numeric value between 0 and 1) in 'temperature' Slider component
                        False,	# bool in '开启无参考文本模式。不填参考文本亦相当于开启。' Checkbox component
                        fn_index=3
        )
        # C:/Users/Administrator/AppData/Local/Temp/gradio/5f162adfba8e02d5aece25be4ac80d91925eba90/audio.wav
        #/mnt/e/Users/Administrator/AppData/Local/Temp/gradio/5f162adfba8e02d5aece25be4ac80d91925eba90/audio.wav
        return "/mnt/c" + result[2:].replace("\\", "/")
        
    def image_recognition(self,url)->str:
        """图像描述成文字(未完成)"""
        pass
