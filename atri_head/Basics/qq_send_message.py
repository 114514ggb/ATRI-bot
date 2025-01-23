import json
import httpx
import uuid
import asyncio
from ..Basics.WebSocketClient import WebSocketClient

class QQ_send_message():
    _instance = None
    File_root_directory = "E:/程序文件/python/ATRI/document/"
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(QQ_send_message, cls).__new__(cls)
        return cls._instance

    def __init__(self,token = "ATRI114514",http_base_url = "http://localhost:8080",connection_type = "http"):
        if not hasattr(self, "_initialized"):
            if connection_type == "http":

                self.access_token = token
                self.http_base_url = http_base_url
                self.headers = {
                    'Content-Type':'application/json',
                    'Authorization': 'Bearer '+self.access_token,
                }

            elif connection_type == "WebSocket":
                self.websocketClient = WebSocketClient()
            else:
                print("连接类型错误")
                raise Exception("连接类型错误")
                
            self.connection_type = connection_type # 连接类型
            self._initialized = True

    # def send(self, url, payload):
    #     """发送请求"""
    #     try:
    #         response = requests.post(url, payload, headers=self.headers)
    #         if response.status_code == 200:
    #             print("消息发送成功")
    #         else:
    #             print(f"发送消息失败{response.status_code}{response.text}")
    #     except requests.RequestException as e:
    #         print("请求失败:", e)
        
    async def async_send(self, url, payload, echo = None):
        """发送异步请求,返回json"""
        if self.connection_type == "http":
            url = f"{self.http_base_url}/{url}"
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, data=json.dumps(payload), headers=self.headers)
                    if response.status_code == 200:
                        print("消息发送成功")
                        return response.json()
                    else:
                        print(f"发送消息失败 {response.status_code} {response.text}")
            except httpx.HTTPError as e:
                print("请求失败:", e)
        else:

            message = {
                "action": url,
                 # 'access_token': self.access_token,
                "params": payload
            }

            if echo != None:
                message["echo"] = echo

            try:

                await self.websocketClient.websocket.send(json.dumps(message))
                print("消息发送成功")
                
            except Exception as e:
                print("发送消息失败:", e)

    async def send_group_message(self,group_id, message):
        """发送群聊文字消息"""
        url = "send_group_msg"
        
        params = {
            "group_id": group_id,
            "message": message,
        }

        await self.async_send(url,params)
        # self.send(url,params)

    async def send_group_pictures(self,group_id,url_img = "img_ATRI.png",default = False, local_Path_type = True):
        """发送群图片,默认图片为img_ATRI.png还有可开启默认路径"""
        if default:
            url_img = f"{self.File_root_directory}img/{url_img}"

        await self.group_message_request(group_id,"image",url_img,local_Path_type)

    async def send_group_audio(self,qq_TestGroup,url_audio = "Atri my dear moments.mp3",default = False,local_Path_type = True):
        """发送群语音"""
        if default: 
            url_audio = f"{self.File_root_directory}audio/{url_audio}"
    
        await self.group_message_request(qq_TestGroup,"record",url_audio,Path_type=local_Path_type)
    
    async def send_group_video(self,qq_TestGroup,url_video = "ATRIの珍贵录像.mp4",default = False,local_Path_type = True):
        """发送群视频"""
        if default: 
            url_video = f"{self.File_root_directory}video/{url_video}"

        await self.group_message_request(qq_TestGroup,"video",url_video,Path_type=local_Path_type)

    async def send_group_file(self,qq_TestGroup,url_file = "ATRI的文件.txt",default = False,local_Path_type = True):
        """发送群文件"""
        if default: 
            url_file = f"{self.File_root_directory}file/{url_file}"
            
        Path_type = ""

        if local_Path_type:
            Path_type = "file://"
            

        url = "send_group_msg"
        payload ={
            "group_id": qq_TestGroup,
            "message": [
                {
                    "type": "file",
                    "data": {
                    "file": Path_type+url_file
                    }
                }
            ],
        }
        
        await self.async_send(url=url,payload=payload)
        # self.send(url,payload)

    async def send_img_details(self,file_id):
        """获取图片消息详情"""
        url = "get_image"

        payload = {
            "file_id": file_id,
        }

        if self.connection_type == "http":
            return await self.async_send(url=url,payload=payload)
        else:
            request_id = str(uuid.uuid4())
            await self.async_send(url=url,payload=payload,echo = request_id)

            return await self.websocketClient.gain_echo(request_id)
            
        

    async def group_message_request(self,group_id,type,file_url,Path_type = True):
        """发送单个,非文字群消息"""

        if Path_type:
            Path_type = "file://"
        else:
            Path_type = ""

        url = "send_group_msg"
        payload ={
            "group_id": group_id,
            "message": [
                {
                    "type": type,
                    "data": {
                    "file": Path_type+file_url
                    }
                }
            ],
        }

        await self.async_send(url=url,payload = payload)
        # self.send(url,payload)

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
        if default:
            url_img = f"{self.File_root_directory}img/{url_img}"

        data = {"file": "file://"+url_img}

        await self.Send_personal_message(qq_id,data,"image")

    async def send_personal_audio(self,qq_id,url_audio = "Atri my dear moments.mp3",default = False):
        """发送私聊语音"""
        if default: 
            url_audio = f"{self.File_root_directory}audio/{url_audio}"

        data = {"file": "file://"+url_audio}

        await self.Send_personal_message(qq_id,data,"record")