from .permissions_management import Permissions_management
from .qq_send_message import QQ_send_message
from typing import Dict
import re
import json

class Command(Permissions_management):
    """有关指令和文本解析类"""
    
    def __init__(self):
        super().__init__()
        self.send_message = QQ_send_message()
        
    
    @staticmethod
    def verifyParameter(parameter_list, quantity_list):
        """
        验证参数长度。

        :param parameter_list: 参数列表，应包含两个子列表。
        :param quantity_list: 参数数量限制列表，每个元素是一个包含最小值和最大值的元组。
        :return: 验证通过的参数及其长度的两个list。
        """
        (min_appoint, max_appoint), (min_other, max_other) = quantity_list
        
        appointed_params = parameter_list[0]
        other_params = parameter_list[1]
        appointed_length = len(appointed_params)
        other_length = len(other_params)

        if not (min_appoint <= appointed_length <= max_appoint):
            raise ValueError(f"指定参数数量应在{min_appoint}到{max_appoint}之间，实际为{appointed_length}")
        if not (min_other <= other_length <= max_other):
            raise ValueError(f"其他参数数量应在{min_other}到{max_other}之间，实际为{other_length}")
        
        # 如果所有参数都符合要求，则返回参数及其长度
        return [appointed_params, appointed_length], [other_params, other_length]
    
    @staticmethod
    def processingParameter(command):
        """提取参数"""
        pattern_command_argumrnts = r'(?<=\s)-([^\s-]+)' #匹配参数'-'开头
        pattern_command_other_argumrnts = r'(?<=\s)([^/\s-]\S*)' #匹配命令其他参数

        command_argumrnts = re.findall(pattern_command_argumrnts, command)
        command_other_argumrnts = re.findall(pattern_command_other_argumrnts, command)

        return [command_argumrnts,command_other_argumrnts]

    @staticmethod
    def data_processing_text(data:Dict[str, int|str|Dict])->str:
        """处理原data里的message处理成纯text"""
        text_parts = []
        
        for message in data["message"]:
            
            message:Dict[str,str|dict]
            my_type:str = message.get("type")

            if my_type == "text":
                text_data = message.get("data", {}).get("text", "")
                text_parts.append(str(text_data))
                
            elif my_type == "image":
                summary = message.get("data", {}).get("summary", "")
                text_parts.append(f"[CQ:image,summary:{summary}" if summary else "[CQ:image]")
                
            elif my_type == "at":
                qq = message.get("data", {}).get("qq", "")
                text_parts.append(f"[CQ:at,qq={qq}]")
                
            elif my_type == "file":
                file = message.get("data", {}).get("file", "")
                text_parts.append(f"[CQ:file,name:{file}]")
                
            elif my_type == "face":
                face_text = message["data"]["raw"]["faceText"]
                text_parts.append(f"[CQ:face,prompt:{face_text}]" if face_text else "[CQ:face]")
                
            elif my_type == "json":
                try:
                    json_data:dict = json.loads(message.get('data', {}).get("data", "{}"))
                    prompt = json_data.get("prompt", "")
                    text_parts.append(f"[CQ:json,prompt:{prompt}]")
                except json.JSONDecodeError:
                    text_parts.append("[CQ:json]")
                    
            else:
                text_parts.append(f"[CQ:{my_type}]")

        return "".join(text_parts)
    
    
    async def data_processing_ai_chat_text(self,data:Dict[str, int|str|Dict])->list[str,list[str]]:
        """用来解析成ai读的文本"""
        text_parts = []
        image_urls = []
        img_count = 1
        
        for message in data["message"]:
            message:Dict[str,str|dict]
            my_type:str = message.get("type")
            
            if my_type == "text":
                text_data = message.get("data", {}).get("text", "")
                text_parts.append(str(text_data))
            
            elif my_type == "reply":#引用消息
                reply_data = (await self.send_message.get_msg_details(message["data"]["id"]))["data"]
                reply_text_parts = ["<quote_message>"]
                for reply_message in reply_data["message"]:
                    reply_message:Dict[str,str|dict]
                    reply_type:str = reply_message.get("type")
                    
                    if reply_type == "text":
                        text_data = reply_message.get("data", {}).get("text", "")
                        reply_text_parts.append(str(text_data))
                        
                    elif reply_type == "image":
                        reply_text_parts.append(f"[CQ:图片{img_count}]")
                        image_urls.append(reply_message["data"]["url"])
                        img_count += 1
                        
                    elif reply_type == "at":
                        qq = reply_message.get("data", {}).get("qq", "")
                        reply_text_parts.append(f"[CQ:at,qq={qq}]")
                        
                    elif reply_type == "file":
                        file = reply_message.get("data", {}).get("file", "")
                        reply_text_parts.append(f"[CQ:file,name:{file}]")
                        
                    elif reply_type == "face":
                        face_text = reply_message["data"]["raw"]["faceText"]
                        reply_text_parts.append(f"[CQ:face,prompt:{face_text}]" if face_text else "[CQ:face]")
                        
                    elif reply_type == "json":
                        try:
                            json_data:dict = json.loads(reply_message.get('data', {}).get("data", "{}"))
                            prompt = json_data.get("prompt", "")
                            reply_text_parts.append(f"[CQ:json,prompt:{prompt}]")
                        except json.JSONDecodeError:
                            reply_text_parts.append("[CQ:json]")
                            
                    else:
                        reply_text_parts.append(f"[CQ:{reply_type}]")
                        
                text_parts.append("".join(reply_text_parts)+"</quote_message>")
                    
            
            elif my_type == "at":
                qq = message.get("data", {}).get("qq", "")
                text_parts.append(f"[CQ:at,qq={qq}]")
                
            elif my_type == "face":
                face_text = message["data"]["raw"]["faceText"]
                text_parts.append(f"[CQ:face,prompt:{face_text}]" if face_text else "[CQ:face]")
            
            elif my_type == "image":
                text_parts.append(f"[CQ:图片{img_count}]")
                image_urls.append(message["data"]["url"])
                img_count += 1
                
            else:
                text_parts.append(f"[CQ:{my_type}]")
        
        return ["".join(text_parts),image_urls]