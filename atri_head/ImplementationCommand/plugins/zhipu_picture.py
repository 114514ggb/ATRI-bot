from .example_plugin import example_plugin
from zhipuai import ZhipuAI
from ...ai_chat.api_key_bigModel import api_key


class zhipu_picture(example_plugin):
    """zhipu图片生成API"""
    register_order = ["/画图","/draw"]

    def __init__(self):
        super().__init__()
        self.client = ZhipuAI(api_key=api_key)
    
    async def main(self,user_input,qq_TestGroup,data):
        """画图主函数"""
        self.store(user_input,qq_TestGroup,data)
        self.basics.Command.verifyParameter(
            self.argument,
            parameter_quantity_max_1=0, parameter_quantity_min_1=0, 
            parameter_quantity_max_2=10, parameter_quantity_min_2=1,
        )

        prompt = " ".join(self.argument[1])

        response = self.client.images.generations(
            model="CogView-3-Flash", 
            prompt=prompt,
        )

        url = response.model_dump()['data'][0]['url']

        await self.basics.QQ_send_message.send_group_pictures(qq_TestGroup,url,local_Path_type=False)

    
    async def zhipu_picture(self, user_input, qq_TestGroup, data):
        """画图"""
        
        await self.main(user_input,qq_TestGroup,data)

        return "ok"

