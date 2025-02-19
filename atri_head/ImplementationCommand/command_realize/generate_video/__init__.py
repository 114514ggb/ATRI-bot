from atri_head.Basics import Basics,Command_information
from atri_head.ai_chat import bigModel_api
import asyncio
import base64

class zhipu_video():
    """zhipu视频生成API"""
    register_order = ["/视频","/video"]
    model = "CogVideoX-Flash"
    # model = "CogVideoX-2" 

    def __init__(self):
        self.basics = Basics()
        self.client = bigModel_api.bigModel_api()

    def request_video(self,prompt,image_url = None):
        """请求视频"""
        if image_url:
            return self.client.tucson_video(prompt, image_url, self.model) #图生视频
        else:
            return self.client.vincennes_video(prompt, self.model) #文生视频

    async def acquire_video(self,video_id):
        """获取视频"""
        max_wait_times = 6000     # 最大等待次数
        wait_interval = 1   # 每次等待间隔时间（秒）
        total_wait_time = 0
        image_url = None

        for _ in range(max_wait_times):
            response = self.client.video_result_query(video_id)['video_result']

            if response:
                image_url = response[0]["url"]

            if image_url:
                return image_url,total_wait_time

            await asyncio.sleep(wait_interval)
            total_wait_time += wait_interval

        raise ValueError("超过最大请求次数，仍未请求到视频!")


    async def main(self,argument,qq_TestGroup,data):

        prompt = " ".join(argument[1])
        id = None

        for message in data["message"]:

            if message["type"] == "image":

                img_path = (await self.basics.QQ_send_message.send_img_details(message["data"]['file']))["data"]["file"]

                with open(img_path, 'rb') as img_file:
                    img_base = base64.b64encode(img_file.read()).decode('utf-8')

                    id = self.request_video(prompt,img_base)["id"]

        if id == None:
            id = self.request_video(prompt)["id"]

        await self.basics.QQ_send_message.send_group_message(qq_TestGroup,f"正在生成视频，请稍后...\n任务ID:{id}\n注意这个模型的效果不佳！不要预期太高！")

        image_url,total_wait_time = await self.acquire_video(id)

        await self.basics.QQ_send_message.send_group_message(qq_TestGroup,f"视频生成完成，耗时{total_wait_time}秒\nurl:{image_url}")

        await self.basics.QQ_send_message.send_group_video(qq_TestGroup, image_url,local_Path_type=False)
        
        return True
    

video = zhipu_video()

command_main = Command_information(
    name="zhipu_video",
    aliases=["视频","video"],
    handler=video.main,
    description="生成视频,支持文生和图片生成视频\n语法: /视频 [prompt] [picture]\n",
    authority_level=1,
    parameter=[[0,0],[1, 10]]
)

