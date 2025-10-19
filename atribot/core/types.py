from dataclasses import dataclass
from typing import Dict,List,Any



class ToolCallsStopIteration(Exception):
    """结束工具调用异常"""
    def __init__(self, message:str = ""):
        if message:
            super().__init__(f"'tool_calls_end': {message}")
        else:
            super().__init__("end tool call")


@dataclass
class rich_data():
    """一般处理消息"""
    primeval:dict
    """原始消息"""
    text:str = ""
    """解析过的qq的文本"""
    pure_text:str = ""
    """消息的文本部分"""
    
    
@dataclass
class Context():
    """对话上下文"""
    messages: List[Dict[str, Any]] = None
    """原始的上下文"""
    user_max_record: int = 20
    """user最多消息条数限制"""
    Play_role:str = ""
    """模型人物提示词"""

    def __post_init__(self):
        if self.messages is None:
            self.messages = []
    
    def __getitem__(self, index):
        return self.get_messages()[index]
    
    def __len__(self):
        return len(self.get_messages())
    
    def __iter__(self):
        return iter(self.get_messages())
    
    def __contains__(self, item):
        return item in self.get_messages()
    
    def __reversed__(self):
        return reversed(self.get_messages())
    
    def __str__(self):
        return str(self.get_messages())
    
    def __repr__(self):
        return repr(self.get_messages())
    
    def append(self, dict:Dict[str, Any])->None:
        """添加内容"""
        self.messages.append(dict)
        
    def extend(self, Iterable:List)->None:
        """用可迭代对象来扩展列表"""
        self.messages.extend(Iterable)
    
    def get_messages(self)->List[Dict[str, Any]]:
        """获取当前的上下文

        Returns:
            List[Dict[str, Any]]: 上下文list
        """
        if self.Play_role:
            return [{"role": "system", "content": self.Play_role}]+self.messages
        return self.messages
    
    def add_message(self, role:str, content:str|list, tool_call_id:int = None)->None:
        """添加消息

        Args:
            role (str): 消息枚举值"user", "assistant", "system", "tool"
            content (str): 内容
            tool_call_id (int): 工具id,当类型为tool时可能需要
        """
        if tool_call_id:
            self.messages.append({
                "role": role, 
                "content": content,
                "tool_call_id": tool_call_id
            })
            return
        
        self.messages.append({"role": role, "content": content})
        
    def add_img_message(self, role:str, text:str, image_urls: list)->None:
        """添加带图片消息

        Args:
            role (str): 消息枚举值"user", "assistant", "system", "tool"
            text (str): 文本内容
            image_urls (list): 图片的 URL 列表，每个 URL 都会被作为独立的图片项添加到 content 
        """
        self.messages.append({
            "role": role,
            "content": [{"type": "image_url", "image_url": {"url": url}} for url in image_urls] + [{"type": "text", "text": text}]
        })
    
    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})
        
    def add_assistant_message(self, content: str|None) -> None:
        """添加助手消息"""
        self.messages.append({"role": "assistant", "content": content})
        
    def add_assistant_tool_message(self, content: str|None,tool_calls:List[Dict] = None) -> None:
        """添加助手调用工具消息"""
        self.messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        
    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        self.messages.append({"role": "system", "content": content})
        
    def add_tool_message(self, content: str, tool_call_id:int = None) -> None:
        """添加工具消息"""
        self.messages.append({"role": "tool", "content": content, "tool_call_id": tool_call_id})
        
    def record_validity_check(self)->None:
        """针对消息条数的验证,需要显示调用"""
        if sum(1 for msg in self.messages if msg["role"] == "user") > self.user_max_record:
            self.messages = self.messages[-self.user_max_record:]
        
    def clear(self)->None:
        """清除上下文"""
        self.messages.clear()

    def get_context_forecast_token(self)->int:
        """获取仅供参考的当前上下文的token(默认里面都是中文)

        Returns:
            int: 大概token数,误差应该挺大的
        """
        return int(len(str(self.get_messages()))*1.2)