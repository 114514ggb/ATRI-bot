from ..Basics import Basics
import random

class itemAction():
    """根据需要执行对应的操作"""
    def __init__(self):
        self.basics = Basics()

    async def main(self,qq_TestGroup, data):
        """反射主函数"""
        for key in self.item_list.keys():
            if key in data:

                Value = str(data[key])

                if Value in self.item_list[key]:
                    await self.item_list[key][Value](self,qq_TestGroup, data)
                    return True
        
        return False

    async def poke(self,qq_TestGroup, data):
        """戳一戳的反馈"""
        if data['self_id'] == data['target_id']:
            reactivity_list = ["你揉我干嘛？哎呦( •̀ ω •́ )","不要柔了啊,痛吖喵!","呜喵！","( •̀ ω •́ )喵~","喵~(〃ω〃)","喵！（炸毛）","我的天！你居然柔我！喵！"]
            text = random.choice(reactivity_list)

            await self.basics.QQ_send_message.send_group_message(qq_TestGroup,text)
    
    sub_type = {
        'poke': poke,
    }

    user_id = {
        '168238719': None,
    }

    item_list = {
        'sub_type': sub_type,
        'user_id': user_id,
    }