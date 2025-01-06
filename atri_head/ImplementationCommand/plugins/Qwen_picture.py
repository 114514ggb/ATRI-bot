from .example_plugin import example_plugin
import asyncio,aiohttp
from aiohttp import ClientError


class Qwen_picture(example_plugin):
    """Qwen图片生成API"""
    register_order = ["/画图","/draw"]

    style = {
        "默认":"<auto>",#默认值，由模型随机输出图像风格。
        "摄影":"<photography>",#摄影。
        "人像":"<portrait>",#人像写真。
        "卡通":"<3d cartoon>",#3D卡通。
        "动画":"<anime>",#动画。
        "油画":"<oil painting>",#油画。
        "水彩":"<watercolor>",#水彩。
        "素描":"<sketch>",#素描。
        "中国画":"<chinese painting>",#中国画。
        "插画":"<flat illustration>",#扁平插画。
    }

    API_KEY = "sk-bde63eefc4c9480aace5243c3455e038"
    BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
    HEADERS = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "X-DashScope-Async": "enable",
        "X-DashScope-WorkSpace": "llm-uzxl32mp3hscpy5x",
    }

    def __init__(self):
        super().__init__()
        # self.session = requests.Session()
        # self.session.headers.update(self.HEADERS)

    # def draw_request(self, prompt, style):
    #     """请求图片"""
    #     url = f"{self.BASE_URL}/services/aigc/text2image/image-synthesis"

    #     data = {
    #         "model": "wanx-v1", # 模型
    #         "input": {
    #             "prompt": prompt,
    #         },
    #         "parameters": {
    #             "style": style, # 图像风格
    #             "size": "1024*1024", # 图像尺寸
    #             "n": 1 # 生成图像数量
    #         }
    #     }

    #     try:
    #         response = self.session.post(url, json=data)
    #         response.raise_for_status()
    #         return json.loads(response.text)["output"]["task_id"]
    #     except RequestException as e:
    #         raise ValueError(f"画图请求失败: {e}")
    async def draw_request(self, prompt, style):
        """异步请求图片"""
        url = f"{self.BASE_URL}/services/aigc/text2image/image-synthesis"
        data = {
            "model": "wanx-v1",  # 模型
            "input": {"prompt": prompt},
            "parameters": {"style": style, "size": "1024*1024", "n": 1},
        }

        async with aiohttp.ClientSession(headers=self.HEADERS) as session:
            try:
                async with session.post(url, json=data) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result["output"]["task_id"]
            except ClientError as e:
                raise ValueError(f"画图请求失败: {e}")    
        
    # def draw_receive(self, task_id):
    #     """接收图片"""
    #     url = f"{self.BASE_URL}/tasks/{task_id}"

    #     try:
    #         response = self.session.get(url)
    #         response.raise_for_status()

    #         data = json.loads(response.text)["output"]
    #         if data["task_status"] == "SUCCEEDED":
    #             return data["results"][0]["url"]
    #         elif data["task_status"] in ["FAILED", "UNKNOWN"]:
    #             raise ValueError("画图请求成功，但是请求接收完成图片失败!")
    #         else:
    #             return None
            
    #     except RequestException as e:
    #         raise ValueError(f"请求接收图片失败: {e}")
            
    async def draw_receive(self, task_id):
        """异步接收图片"""
        url = f"{self.BASE_URL}/tasks/{task_id}"

        async with aiohttp.ClientSession(headers=self.HEADERS) as session:
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    output = data["output"]
                    if output["task_status"] == "SUCCEEDED":
                        return output["results"][0]["url"]
                    elif output["task_status"] in ["FAILED", "UNKNOWN"]:
                        raise ValueError("画图请求成功，但接收图片失败!")
                    else:
                        return None
            except ClientError as e:
                raise ValueError(f"请求接收图片失败: {e}")
        
    async def generate_and_get_image(self, qq_TestGroup, prompt, style):
        """请求生成并获取图片"""
        task_id = await self.draw_request(prompt, style)
        await self.basics.QQ_send_message.send_group_message(qq_TestGroup,f"已发起图片生成请求，任务ID: {task_id}")

        max_wait_times = 60     # 最大等待次数
        wait_interval = 1   # 每次等待间隔时间（秒）
        total_wait_time = 0

        for _ in range(max_wait_times):
            image_url = await self.draw_receive(task_id)
            if image_url:
                text = f"图片获取成功！\n从发起请求到获取图片共等待了: {total_wait_time} 秒\n图片链接url:{image_url}"
                await self.basics.QQ_send_message.send_group_message(qq_TestGroup,text)
                return image_url

            await asyncio.sleep(wait_interval)
            total_wait_time += wait_interval

        raise ValueError("超过最大请求次数，仍未请求到图片!")
    
    async def main(self,user_input,qq_TestGroup,data):
        """画图主函数"""
        self.store(user_input,qq_TestGroup,data)
        self.basics.Command.verifyParameter(
            self.argument,
            parameter_quantity_max_1=1, parameter_quantity_min_1=0, 
            parameter_quantity_max_2=10, parameter_quantity_min_2=1,
        )

        style = "<auto>"
        prompt= ' '.join(self.argument[1])

        if self.argument[0] != [] and self.argument[0][0] in self.style:
            style = self.style[self.argument[0][0]]

        url = await self.generate_and_get_image(qq_TestGroup, prompt, style)

        await self.basics.QQ_send_message.send_group_pictures(qq_TestGroup,url,local_Path_type=False)

    
    async def Qwen_picture(self, user_input, qq_TestGroup, data):
        """画图"""
        
        await self.main(user_input,qq_TestGroup,data)

        return "ok"

