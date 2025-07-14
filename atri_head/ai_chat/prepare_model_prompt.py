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

    def build_prompt(self, context:str = "", chat_history:str = "")-> str:
        """
        构造用来回复的嵌入式prompt
        """
        prompt = f"现在的时间是:{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if self.model_environment != "":
            prompt += f"<对话环境>{self.model_environment}</对话环境>\n\n"
            
        if chat_history != "":
            prompt += f"<QQ_chat_history>{chat_history}</QQ_chat_history>\n\n"
        
        if self.prompt != "":
            prompt += f"<prompt>{self.prompt}</prompt>\n\n"
        
        if context != "":   
            prompt += f"需要回答的:<user_input>{context}</user_input>\n\n"
        
        return prompt
    
    @staticmethod
    def build_group_user_Information(data:dict)-> str:
        """ 构造群用户信息 """
        return str(
            {
                "qq_id":data['user_id'], #qq号
                "group_name":data['group_name'],#群昵称
                "nick_name":data['sender']['nickname'],#user昵称
                "message":data['raw_message'] #消息内容
            }
        )
    
    @staticmethod    
    def build_user_Information(data:dict, message:str)-> str:
        """ 构造用户消息 """
        return str(
            {
                "qq_id":data['user_id'], #qq号
                "nick_name":data['sender']['nickname'],#user昵称
                "message":message #消息内容
            }
        )
    
    @staticmethod
    def append_playRole(content,messages:list):
        """添加扮演的角色，固定为列表的第一个元素"""
        if content != "":
             messages.insert(0, {"role": "system","content": content})
        return messages
    
    @staticmethod
    def append_message_text(messages:list,role:str,content:str):
        """
        添加文本消息.
        
        Args:
            messages (list):消息list 
            role (str): 消息角色。
            content (str):content为内容
        """
        messages.append({"role": role,"content": content})
        return messages
    
    @staticmethod
    def append_message_image(messages: list, image_urls: list, text="请详细描述这个图片，如果上面有文字也要详细说清楚", role: str = "user"):
        """
        添加带图片的消息到 messages 列表中。
        
        Args:
            messages (list): 当前的消息列表，每个元素是一个字典，表示一条消息。
            image_urls (list): 图片的 URL 列表，每个 URL 都会被作为独立的图片项添加到 content 中。
            text (str): 对图片的描述或提问内容，默认为“请详细描述这个图片，如果上面有文字也要详细说清楚”。
            role (str): 消息角色，通常是 'user' 或 'assistant'，默认为 'user'。
            
        Returns:
            list: 更新后的 messages 列表，包含新增的消息内容。
        """
        # print({
        #     "role": role,
        #     "content": [{"type": "image_url", "image_url": {"url": url}} for url in image_urls] + [{"type": "text", "text": text}]
        # })
        messages.append({
            "role": role,
            "content": [{"type": "image_url", "image_url": {"url": url}} for url in image_urls] + [{"type": "text", "text": text}]
        })

        return messages
    
    @staticmethod
    def append_message_tool(messages:list ,tool_content:str ,tool_call_id:str):
        """ 添加工具消息 """
        messages.append({
            "role": "tool",
            "content": tool_content,
            "tool_call_id": tool_call_id,
        })
        
        return messages

    @staticmethod
    def append_tag_hint(text:str, tag_prompt:str, tag_list:list ,tag_symbol:str = "[内容]")->str:
        """向原有提示词添加可输出标签提示"""
        text += "\n\n可以在输出中加入带有如下内容的标签:" + str(tag_list) + \
            "\n标签格式是:" + tag_symbol +\
            "\n这是用来" + tag_prompt + "\n"
        
        return text
