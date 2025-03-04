
from ..ai_chat.chat_main import Chat_processing
from ..ai_chat.test_initiative_chat import initiative_chat


class AI_interaction():
    """一些和ai有关的API"""
    
    def __init__(self,playRole):
        self.chat = Chat_processing(playRole)
        self.auto_response = initiative_chat()
    

    def speech_synthesis(self, text):
        """语音合成,返回音频文件路径"""
        return self.chat.tool_calls.text_to_speech(text)
        
