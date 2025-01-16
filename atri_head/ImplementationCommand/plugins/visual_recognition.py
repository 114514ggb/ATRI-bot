from .example_plugin import example_plugin
from ...ai_chat.bigModel_api import bigModel_api
import base64

class visual_recognition(example_plugin):
    """用于视觉识别"""
    register_order = ["/visual","/识图"]

    model="glm-4v-flash"
    messages = []

    def __init__(self):
        self.openai = bigModel_api()

    def Request_answer(self):
        """请求回答"""
        return self.openai.generate_text(self.model, self.messages)

    @example_plugin.store_verify_parameters(
        parameter_quantity_max_1=0,parameter_quantity_min_1=0,
        parameter_quantity_max_2=100,parameter_quantity_min_2=0,
    )
    async def main(self,qq_TestGroup,user_input,data,basics):

        for message in data["message"]:

            if message["type"] == "image":

                img_path = (await self.basics.QQ_send_message.send_img_details(message["data"]['file_id']))["data"]["file"]

                with open(img_path, 'rb') as img_file:
                    img_base = base64.b64encode(img_file.read()).decode('utf-8')

                string = ' '.join(self.other_argument)
                if string == "":
                    string = "请详细描述这个图片，如果上面有文字也要详细说清楚"
                    
                self.messages = []
                self.openai.append_message_image(
                    messages = self.messages,
                    image_url = img_base,
                    text = string,
                )

                assistant_output = self.Request_answer()

                text = assistant_output['choices'][0]['message']['content']

                await self.basics.QQ_send_message.send_group_message(qq_TestGroup, text)
                return


        raise Exception("未找到图片")

    async def visual_recognition(self, user_input, qq_TestGroup, data):
        
        await self.main(qq_TestGroup,user_input,data)

        return "ok"