import time

class build_prompt:
    """
        构造prompt的类\n
        对model的环境和prompt进行封装
    """
    prompt = ""
    """model输出要求"""
    
    model_environment = ""
    """model输出的环境"""
    
    
    def __init__(self, prompt = "", model_environment = ""):
        self.prompt = prompt
        self.model_environment = model_environment

    def get_prompt(self):
        return self.prompt

    def get_model_environment(self):
        return self.model_environment

    def set_prompt(self, prompt):
        self.prompt = prompt

    def set_model_name(self, model_environment):
        self.model_environment = model_environment

    def build_prompt(self, context:str, chat_history:str = "")-> str:
        """
        构造用来回复的嵌入式prompt
        """
        prompt = f"现在的时间是:{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if self.model_environment != "":
            prompt += f"对话环境:{self.model_environment}\n\n"
            
        if chat_history != "":
            prompt += f"chat_history:{chat_history}\n\n"
        
        prompt += f"需要响应的内容:<BEGIN>{context}<FINISH>\n\n"
        
        if self.prompt != "":
            prompt += f"system_prompt:{self.prompt}\n\n"
        
        return prompt
    
    def build_group_user_Information(self, data:dict)-> str:
        """ 构造群用户信息 """
        return str(
            {
                "qq_id":data['user_id'], #qq号
                "group_name":data['group_name'],#群昵称
                "nick_name":data['sender']['nickname'],#user昵称
            }
        )
        
    def build_user_Information(self, data:dict)-> str:
        """ 构造用户消息 """
        return str(
            {
                "qq_id":data['user_id'], #qq号
                "nick_name":data['sender']['nickname'],#user昵称
                "message":data['raw_message'] #消息内容
            }
        )
    
    
    
