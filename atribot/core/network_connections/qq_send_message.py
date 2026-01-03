from atribot.core.network_connections.WebSocketClient import WebSocketClient
from atribot.core.network_connections.WebSocketServer import WebSocketServer
from atribot.core.service_container import container
from typing import Optional
from logging import Logger
import json
import aiohttp
# import asyncio
"""
文件支持的格式：
- 本地路径: "file://<绝对路径>", 如 "file://D:/a.jpg"
- 网络路径: "http://<URL>" 或 "https://<URL>", 如 "http://example.com/image.png"
- Base64编码: "base64://<编码字符串>", 如 "base64://iVBORw0KGgo..."
"""


class qq_send_message():
    """qq接口有关的请求发送器"""
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(qq_send_message, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        token = "ATRI114514",
        http_base_url = "http://localhost:8080",
        connection_type = "http",
        File_root_directory:str = ""
    ):
        if not hasattr(self, "_initialized"):
            self.File_root_directory = File_root_directory
            self.logger:Logger = container.get("log")
            
            if connection_type == "http":
                
                self.access_token = token
                self.http_base_url = http_base_url
                self.headers = {
                    'Content-Type':'application/json',
                    'Authorization': 'Bearer '+self.access_token,
                }
                self.client = aiohttp.ClientSession(headers=self.headers)
                self._send_impl = self._send_http_strategy
                
            elif connection_type in ["WebSocket","WebSocket_client","WebSocket_server"]:
                
                self.websocket:WebSocketClient | WebSocketServer = container.get("WebSocket")
                self._send_impl = self._send_ws_strategy
                
            else:
                raise Exception("连接类型错误")
                
            self.connection_type = connection_type # 连接类型
            self.logger.info("当前连接类型为"+connection_type+"\n")
            self._initialized = True
    
    async def _send_http_strategy(self, url: str, payload: dict, echo: bool = False) -> Optional[dict]:
        """HTTP 发送策略"""
        try:
            async with self.client.post(f"{self.http_base_url}/{url}", json=payload) as response:
                if response.status == 200:
                    self.logger.info("http请求发送成功")
                    return await response.json()
                else:
                    self.logger.info(f"http发送请求失败 {response.status} {await response.text()}")
                    return None
        except aiohttp.ClientError as e:
            self.logger.error("http请求失败:", e)
            return None

    async def _send_ws_strategy(self, url: str, payload: dict, echo: bool = False) -> Optional[dict]:
        """WebSocket 发送策略"""
        message = {
            "action": url,
                # 'access_token': self.access_token,
            "params": payload
        }

        try:

            if reply := await self.websocket.send(message,echo):
                return reply
            # self.logger.info("WC请求发送成功")
            return None
            
        except Exception as e:
            self.logger.error("WC发送请求失败:", e)
    
    async def async_send(self, url, payload, echo = False)->dict|None:
        """通用的发送异步请求,返回json"""
        return await self._send_impl(url, payload, echo)

    async def send_group_message(self,group_id: int, message:str|list):
        """
            发送群聊文字消息\n
            message可以是str也可以是包含混合消息的list,str会解析CQ码
        """
        url = "send_group_msg"
        
        params = {
            "group_id": group_id,
            "message": message,
        }

        await self.async_send(url,params)
        # self.send(url,params)

    async def send_group_reply_msg(self,group_id:int, message:str, reply_message_id:int):
        """发送群聊回复消息"""
        params = [
            {
                "type": "reply",#这个必须第一个
                "data": {
                    "id": reply_message_id
                }
            },
            {
                "type": "text",
                "data": {
                    "text": message
                }
            }
        ]
        
        await self.send_group_message(group_id, params)

        
    async def send_group_merge_text(
        self,
        group_id: int, 
        message: str,
        source: str = "男娘秘籍",
        preview: str = "ATRI:晚上一个人偷偷看[图片]"
    ):
        """
            发送群合并转发消息\n
            目前支持发一条文字消息\n
            目的是用来防止过长的消息刷屏，合并转发比较优雅:)
            Args:
                group_id:群号 
                message:消息内容
                source:标题
                preview:预览
        """
        api_url = "send_group_forward_msg"
        
        payload = {
            "group_id": group_id,
            "messages": [
                {
                    "type": "node",
                    "data": {
                        "user_id": "3889393615",
                        "nickname": "ATRI-亚托莉",
                        "content": [
                        {
                            "type": "text",
                            "data": {
                                "text": message
                            }
                        }
                        ]
                    }
                }
            ],
            "news": [
                {
                "text": preview
                }
            ],
            "prompt": "果然是群聊天记录", #外显
            "summary": "点击即看", #底下文本
            "source": source #内容
        }
        
        await self.async_send(api_url,payload)
        
    async def send_group_merge_forward(
        self,
        group_id: int, 
        input_messages: list[list[dict]],
        source: str = "男娘秘籍",
        preview: str = "ATRI:晚上一个人偷偷看[图片]"
    ):
        """
            发送群合并转发消息
            Args:
                group_id:群号 
                input_messages:多条消息内容
                source:标题
                preview:预览
        """
        api_url = "send_group_forward_msg"
        
        messages = []
        
        for message in input_messages:
            messages.append(
                {
                    "type": "node",
                    "data": {
                        "user_id": "3889393615",
                        "nickname": "ATRI-亚托莉",
                        "content": message
                    }
                }
            )
        
        payload = {
            "group_id": group_id,
            "messages": messages,
            "news": [
                {
                "text": preview
                }
            ],
            "prompt": "果然是群聊天记录", #外显
            "summary": "点击即看", #底下文本
            "source": source #内容
        }
        
        await self.async_send(api_url,payload)
    
    async def send_group_poke(self,group_id, user_id):
        """发送群戳一戳"""
        api_url = "group_poke"
        
        payload ={
            "group_id": group_id,
            "user_id": user_id
        }
        
        await self.async_send(api_url,payload)
    
    async def send_group_json(self,group_id: int, json: json):
        """发送群JSON"""
        payload =[
            {
                "type": "json",
                "data": json
            }
        ]
        
        await self.send_group_message(group_id, payload)
        
    async def send_group_music(
            self,
            group_id:str|int,
            type: str, 
            id: str = None, 
            url: str = None, 
            image: str = None,
            singer: str = None,
            title: str = None,
            content: str = None
        ):
        """
        用于分享音乐
        Args:
            type: 音乐平台(qq、163、kugou、kuwo、migu、custom)
            id: 音乐ID(平台非custom时必填)
            url: 音乐链接(custom时必填)
            image: 封面图片(custom时必填)
            singer: 歌手(可选)
            title: 标题(可选)
            content: 内容描述(可选)
        """
        
        if type != "custom" and not id:
                    raise ValueError("当 type 不是 'custom' 时，id 必须提供")
        if type == "custom" and (not url or not image):
            raise ValueError("当 type 是 'custom' 时，url 和 image 必须提供")
        
        data = {
            "type": type,
            "id": id,
            "url": url,
            "image": image,
            "singer": singer,
            "title": title,
            "content": content
        }       
        
        message = [{
                "type": "music",
                "data": {k:v for k,v in data.items() if v is not None}
            }
        ]
        
        await self.send_group_message(group_id,message)
        
    
    async def set_group_add_request(self,flag: str, approve: bool, reason: str = "不行哦!"):
        """
            处理加群请求\n
            Args:
                flag: 请求id\n
                approve: 是否同意\n
                reason: 拒绝理由(可选)
        """
        api_url = "set_group_add_request"

        if approve:
            payload = {
                "flag": flag,
                "approve": approve
            }
        else:
            payload = {
                "flag": flag,
                "approve": approve,
                "reason": reason
            }

        await self.async_send(api_url,payload)
   
   
    async def set_group_ban(self,group_id:str|int, user_id:str|int, duration:int = 1800)->dict:
        """
            禁言群成员\n
            Args:
                group_id: 群号\n
                user_id: 要禁言的成员QQ号\n
                duration: 禁言时长(单位:秒)
            Returns:
                dict: 返回结果详情
        """
        api_url = "set_group_ban"

        payload = {
            "group_id": group_id,
            "user_id": user_id,
            "duration": duration
        }

        return await self.async_send(api_url,payload,echo = True)
   

    async def send_group_pictures(self,group_id,url_img = "img_ATRI.png",default = False, local_Path_type = True, get_return = False)->dict|None:
        """发送群图片,默认图片为img_ATRI.png还有可开启默认路径"""
        if default:
            url_img = f"{self.File_root_directory}img/{url_img}"

        return await self.group_message_request(group_id,"image",url_img,local_Path_type,get_return = get_return)


    async def send_group_audio(self,group_id,url_audio = "Atri my dear moments.mp3",default = False,local_Path_type = True):
        """发送群语音"""
        if default: 
            url_audio = f"{self.File_root_directory}audio/{url_audio}"
    
        await self.group_message_request(group_id,"record",url_audio,Path_type=local_Path_type)
    
    async def send_group_video(self,group_id,url_video = "ATRIの珍贵录像.mp4",default = False,local_Path_type = True):
        """发送群视频"""
        if default: 
            url_video = f"{self.File_root_directory}video/{url_video}"

        await self.group_message_request(group_id,"video",url_video,Path_type=local_Path_type)

    async def send_group_file(self,group_id,url_file = "ATRI的文件.txt",default = False,local_Path_type = True):
        """发送群文件"""
        url = "send_group_msg"
        
        payload = {
            "group_id": group_id,
            "message": [
                {
                    "type": "file",
                    "data": {
                        "file": f"{'file://' if local_Path_type else ''}{f"{self.File_root_directory}file/{url_file}" if default else url_file}"
                    }
                }
            ],
        }
                
        await self.async_send(url=url,payload=payload)
        # self.send(url,payload)

    async def get_img_details(self,file_id):
        """获取图片消息详情"""
        url = "get_image"

        payload = {
            "file_id": file_id,
        }

        return await self.async_send(url=url,payload=payload,echo= True)
    
    async def get_stranger_info(self,qq_id:str)->dict:
        """获取账号信息

        Args:
            qq_id (str): qq号

        Returns:
            dict: 返回账号信息
        """
        url = "get_stranger_info"

        payload = {
            "user_id": qq_id,
        }

        return await self.async_send(url=url,payload=payload,echo= True)

    async def get_recordg_details(self,
            file:str,
            file_id:str,
            out_format:str = "mp3"
        ):
        """获取语音消息详情。

        该异步方法用于获取语音文件的相关信息，包括但不限于格式转换后的输出。

        Args:
            file (str): 文件路径。
            file_id (str): 文件ID,用于标识不同的语音记录。
            out_format (str, optional): 输出格式。支持的枚举值有'mp3', 'amr', 'wma',
                'm4a', 'spx', 'ogg', 'wav', 'flac'。默认值为'mp3'。
        """
        url = "get_recordg"

        payload = {
            "file": file,
            "file_id": file_id,
            "out_format": out_format
        }
        
        return await self.async_send(url=url,payload=payload,echo= True)
    
    async def get_msg_details(self,message_id:str):
        """获取消息详情"""
        url = "get_msg"

        payload = {
            "message_id": message_id,
        }

        return await self.async_send(url=url,payload=payload,echo= True)
    
    async def get_group_info(self,group_id:int)->dict:
        """获取群信息"""
        
        url = "get_group_info"
        payload = {
            "group_id": group_id,
        }
        
        return await self.async_send(url=url,payload=payload,echo= True)
            
        
    async def group_message_request(self,group_id,type,file_url,Path_type = True, get_return:bool = False)->None:
        """
        发送单个,非文字群消息
                
        Args:
            group_id:群号
            type:类型
            file_url:文件目录/url
            Path_type:是否是文件
            get_return:是否返回发送状态
        """

        url = "send_group_msg"
        payload ={
            "group_id": group_id,
            "message": [
                {
                    "type": type,
                    "data": {
                        "file": "file://"+file_url if Path_type else file_url
                    }
                }
            ],
        }

        return await self.async_send(url=url,payload=payload,echo=get_return)


    async def Send_personal_message(self,qq_id, data,type):
        """发送私聊消息"""
        url = "send_private_msg"
        payload = {
            "user_id": qq_id,
            "message": [
                {
                    "type": type,
                    "data": data,
                }
            ],
        }

        await self.async_send(url=url,params=payload)
        # self.send(url,payload)

    async def send_personal_text(self,qq_id,text):
        """发送私聊文字消息"""
        data = {"text":text}
        await self.Send_personal_message(qq_id,data,"text")

    async def send_personal_pictures(self,qq_id,url_img = "img_ATRI.png",default = False):
        """发送私聊图片,默认图片为img_ATRI.png还有可开启默认路径"""

        data = {"file": "file://"+f"{self.File_root_directory}img/{url_img}" if default else url_img}

        await self.Send_personal_message(qq_id,data,"image")

    async def send_personal_audio(self,qq_id,url_audio = "Atri my dear moments.mp3",default = False):
        """发送私聊语音"""

        data = {"file": "file://"+ f"{self.File_root_directory}audio/{url_audio}" if default else url_audio}

        await self.Send_personal_message(qq_id,data,"record")
