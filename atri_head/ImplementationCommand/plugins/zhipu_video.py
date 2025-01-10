from .example_plugin import example_plugin
from ...ai_chat.bigModel_api import bigModel_api
import asyncio
import base64

class zhipu_video(example_plugin):
    """zhipu视频生成API"""
    register_order = ["/视频","/video"]

    def __init__(self):
        super().__init__()
        self.client = bigModel_api()

    def request_video(self,prompt,image_url = None):
        """请求视频"""
        if image_url:
            return self.client.tucson_video(prompt, image_url) #图生视频
        else:
            return self.client.vincennes_video(prompt) #文生视频

    async def acquire_video(self,video_id):
        """获取视频"""
        max_wait_times = 300     # 最大等待次数
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


    async def main(self,user_input,qq_TestGroup,data):
        self.store(user_input,qq_TestGroup,data)
        self.basics.Command.verifyParameter(
            self.argument,
            parameter_quantity_max_1=0, parameter_quantity_min_1=0, 
            parameter_quantity_max_2=10, parameter_quantity_min_2=1,
        )

        prompt = " ".join(self.argument[1])
        id = None

        for message in data["message"]:

            if message["type"] == "image":

                img_path = (await self.basics.QQ_send_message.send_img_details(message["data"]['file_id']))["data"]["file"]

                with open(img_path, 'rb') as img_file:
                    img_base = base64.b64encode(img_file.read()).decode('utf-8')

                    id = self.request_video(prompt,img_base)["id"]

        if id == None:
            id = self.request_video(prompt)["id"]

        await self.basics.QQ_send_message.send_group_message(qq_TestGroup,f"正在生成视频，请稍后...\n任务ID:{id}\n注意这个模型的效果不佳！不要预期太高！")

        image_url,total_wait_time = await self.acquire_video(id)

        await self.basics.QQ_send_message.send_group_message(qq_TestGroup,f"视频生成完成，耗时{total_wait_time}秒\nurl:{image_url}")

        await self.basics.QQ_send_message.send_group_video(qq_TestGroup, image_url,local_Path_type=False)

    async def zhipu_video(self, user_input, qq_TestGroup, data):

        await self.main(user_input, qq_TestGroup, data)

        return "ok"
