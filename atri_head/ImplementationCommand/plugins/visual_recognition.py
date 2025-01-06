from .example_plugin import example_plugin
from ...ai_chat.bigModel_api import bigModel_api
import aiohttp
import base64

class visual_recognition(example_plugin):
    """用于视觉识别"""
    register_order = ["/visual","/识图"]

    model="glm-4v-flash"

    def __init__(self):
        super().__init__()
        self.openai = bigModel_api()

    def Request_answer(self):
        """请求回答"""
        return self.openai.generate_text(self.model, self.openai.messages)
    
    async def main(self,qq_TestGroup,user_input,data):
        self.store(user_input,qq_TestGroup,data)
        self.basics.Command.verifyParameter(
            self.argument,
            parameter_quantity_max_1=0, parameter_quantity_min_1=0, 
            parameter_quantity_max_2=100, parameter_quantity_min_2=0,
        )

        for message in data["message"]:

            if message["type"] == "image":
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=64,verify_ssl=False)) as session:
                    async with session.get(message["data"]['url']) as response:
                        if response.status == 200:
                            data = await response.read()
                            img_base = base64.b64encode(data.read()).decode('utf-8')

                            self.openai.append_message_image(
                                img_base,
                                ' '.join(self.argument[1])
                            )

                            assistant_output = self.Request_answer()

                            await self.basics.QQ_send_message.send_group_message(qq_TestGroup, assistant_output)
                            return
                        else:
                            raise Exception("无法下载图片，状态码: {response.status}")

        raise Exception("未找到图片")

    async def visual_recognition(self, user_input, qq_TestGroup, data):
        
        await self.main(qq_TestGroup,user_input,data)

        return "ok"