import time

class build_prompt:
    """
        构造prompt的类\n
        对model的上下文环境的prompt进行封装
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
            prompt += f"QQ_chat_history:<BEGIN>{chat_history}<FINISH>\n\n"
        
        prompt += f"需要响应的内容:<BEGIN>{context}<FINISH>\n\n"
        
        if self.prompt != "":
            prompt += f"system_prompt:<BEGIN>{self.prompt}<FINISH>\n\n"
        
        return prompt
    
    def build_group_user_Information(self, data:dict)-> str:
        """ 构造群用户信息 """
        return str(
            {
                "qq_id":data['user_id'], #qq号
                "group_name":data['group_name'],#群昵称
                "nick_name":data['sender']['nickname'],#user昵称
                "message":data['raw_message'] #消息内容
            }
        )
        
    def build_user_Information(data:dict, message:str)-> str:
        """ 构造用户消息 """
        return str(
            {
                "qq_id":data['user_id'], #qq号
                "nick_name":data['sender']['nickname'],#user昵称
                "message":message #消息内容
            }
        )
    
    def append_playRole(content,messages:list):
        """添加扮演的角色，固定为列表的第一个元素"""
        if content != "":
             messages.insert(0, {"role": "system","content": content})
        return messages
    
    def append_message_text(messages:list,role:str,content:str):
        """添加文本消息,role为角色,content为内容"""
        messages.append({"role": role,"content": content})
        return messages
    
    def append_message_image(messages:list,image_url, text="请详细描述这个图片，如果上面有文字也要详细说清楚", role = "user"):
        """添加带图片消息,role为角色,image_url为图片链接,text为问题文字"""
        messages.append({
            "role": role,
            "content": [
                {"type": "image_url","image_url": {"url": image_url}},
                {"type": "text","text": text}
            ]  
        })

        return messages
    
    def append_message_tool(messages:list ,tool_content:str ,tool_call_id:str):
        """ 添加工具消息 """
        messages.append({
            "role": "tool",
            "content": tool_content,
            "tool_call_id": tool_call_id,
        })
        
        return messages

    def append_tag_hint(text:str, tag_prompt:str, tag_list:list ,tag_symbol:str = "[内容]")->str:
        """向原有提示词添加可输出标签提示"""
        text += "\n\n可以在输出中加入带有如下内容的标签:" + str(tag_list) + \
            "\n标签格式是:" + tag_symbol +\
            "\n这是用来" + tag_prompt + "\n"
        
        return text
