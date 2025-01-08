import json
import httpx

class QQ_send_message():
    access_token = ""
    base_url = "" # API地址
    File_root_directory = "E:/程序文件/python/ATRI/document/"

    def __init__(self,token,base_url):
        self.access_token = token
        self.base_url = base_url
        self.headers = {
            'Content-Type':'application/json',
            'Authorization': 'Bearer '+self.access_token,
        }

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
        
    async def async_send(self, url, payload):
        """发送异步请求,返回json"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=payload, headers=self.headers)
                if response.status_code == 200:
                    print("消息发送成功")
                    return response.json()
                else:
                    print(f"发送消息失败 {response.status_code} {response.text}")
        except httpx.HTTPError as e:
            print("请求失败:", e)

    async def send_group_message(self,group_id, message):
        """发送群聊文字消息"""
        url = f"{self.base_url}/send_group_msg"
        
        params = json.dumps({
            "group_id": group_id,
            "message": message,
        })

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
            

        url = f"{self.base_url}/send_group_msg"
        payload =json.dumps({
            "group_id": qq_TestGroup,
            "message": [
                {
                    "type": "file",
                    "data": {
                    "file": Path_type+url_file
                    }
                }
            ],
        })
        
        await self.async_send(url=url,payload=payload)
        # self.send(url,payload)

    async def send_img_details(self,file_id):
        """获取图片消息详情"""
        url = f"{self.base_url}/get_image"

        payload = json.dumps({
            "file": file_id,
        })

        return await self.async_send(url=url,payload=payload)
        

    async def group_message_request(self,group_id,type,file_url,Path_type = True):
        """发送单个,非文字群消息"""

        if Path_type:
            Path_type = "file://"
        else:
            Path_type = ""

        url = f"{self.base_url}/send_group_msg"
        payload =json.dumps({
            "group_id": group_id,
            "message": [
                {
                    "type": type,
                    "data": {
                    "file": Path_type+file_url
                    }
                }
            ],
        })

        await self.async_send(url=url,payload = payload)
        # self.send(url,payload)

    async def Send_personal_message(self,qq_id, data,type):
        """发送私聊消息"""
        url = f"{self.base_url}/send_private_msg"
        payload = json.dumps({
            "user_id": qq_id,
            "message": [
                {
                    "type": type,
                    "data": data,
                }
            ],
        })

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