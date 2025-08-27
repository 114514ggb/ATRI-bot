from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.service_container import container
from atribot.core.types import rich_data
from typing import Dict, Tuple, List
import json



class data_manage():
    """处理或格式化一些数据的类"""
    
    def __init__(self):
        self.send_message:qq_send_message = container.get("SendMessage")

    @staticmethod
    def data_processing_text(data:Dict[str, int|str|Dict])->str:
        """处理原data里的message处理成纯test"""
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
    
    @staticmethod
    def rich_data_processing_rich_data(data:Dict[str, int|str|Dict])->rich_data:
        """处理原data里的message处理成rich_data

        Args:
            data (Dict[str, int | str | Dict]): 接收到的原始data

        Returns:
            rich_data
        """
        text_parts = []
        pure_text = []
        
        for message in data["message"]:
            
            message:Dict[str,str|dict]
            my_type:str = message.get("type")

            if my_type == "text":
                text_data = message.get("data", {}).get("text", "")
                text_parts.append(text_data)
                pure_text.append(text_data)
                
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

        return rich_data(
            data,
            "".join(text_parts),
            "".join(pure_text).strip()
        )
    
    
    async def data_processing_ai_chat_text(self,data:Dict[str, int|str|Dict])->Tuple[str,List[str]]:
        """用来解析成ai读的文本"

        Args:
            data (Dict[str, int | str | Dict]): 原始消息json

        Returns:
            Tuple[str,list[str]]: 文本和图片链接组成的Tuple
        """
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
                reply_text_parts = ["<reply_message>"]
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
                        
                text_parts.append("".join(reply_text_parts)+"</reply_message>")
                    
            
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
        
        return "".join(text_parts),image_urls