
from ..ai_chat.chat_main import Chat_processing

class AI_interaction():

    def __init__(self,playRole):
        self.chat = Chat_processing(playRole)

    def speech_synthesis(self, text):
        """语音合成,返回音频文件路径"""
        return self.chat.tool_calls.text_to_speech(text)
        
