from .permissions_management import Permissions_management
from typing import Dict
import re
import json

class Command(Permissions_management):
    """有关指令的文本解析"""
    
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
                text_parts.append(summary if summary else "[image]")
                
            elif my_type == "at":
                qq = message.get("data", {}).get("qq", "")
                text_parts.append(f"[@{qq}]")
                
            elif my_type == "file":
                file = message.get("data", {}).get("file", "")
                text_parts.append(f"[\"file\":{file}]")
                
            elif my_type == "face":
                face_text = message.get("data", {}).get('raw', {}).get('faceText')
                text_parts.append(face_text if face_text is not None else "[unknown_face]")
                
            elif my_type == "json":
                try:
                    json_data:dict = json.loads(message.get('data', {}).get("data", "{}"))
                    prompt = json_data.get("prompt", "")
                    text_parts.append(f"[json_prompt:{prompt}]")
                except json.JSONDecodeError:
                    text_parts.append("[json]")
                    
            else:
                text_parts.append(f"[{my_type}]")

        return "".join(text_parts)