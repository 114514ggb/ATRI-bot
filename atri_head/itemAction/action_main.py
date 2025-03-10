from ..Basics import Basics
import random

class itemAction():
    """根据需要执行对应的操作"""
    def __init__(self):
        self.basics = Basics()
        self.listeners = [
            self.poke, #戳一戳
            self.initiative_chat, #自动回复
        ]
        """监听器list"""

    async def main(self,qq_TestGroup, data):
        """反射主函数"""
        for item in self.listeners:
            if await item(qq_TestGroup, data) == True:
                return True
            
        return False
        
    async def poke(self,qq_TestGroup, data):
        """戳一戳的反馈"""
        if 'sub_type' in data and data['sub_type'] == "poke" and data['self_id'] == data['target_id']:
            reactivity_list = ["你揉我干嘛？哎呦( •̀ ω •́ )","不要揉了啊,痛吖喵!","呜喵！","( •̀ ω •́ )喵~","喵~(〃ω〃)","喵！（炸毛）","我的天！你居然揉我！喵！","(〃ω〃)喵~","你揉我干嘛！,自己揉自己啊！喵！","揉脸打咩！(〃ω〃)喵~","喵~再揉脸要坏掉了","尾巴要秃了啦！快住手喵！(＞﹏＜)","别揉耳朵啦！会聋掉的喵！(｀Д´)","揉揉按摩禁止！会痒到炸毛的喵！(//∇//)","喵~请继续！(ฅ´ω`ฅ)"]
            text = random.choice(reactivity_list)

            await self.basics.QQ_send_message.send_group_message(qq_TestGroup,text)
            return True
        
        return False
    
    async def initiative_chat(self,qq_TestGroup, data):
        """自动判断回复群消息"""
        if qq_TestGroup == 984466158 and "message" in data:
            ai_response = await self.basics.AI_interaction.auto_response.chat_main(
                data=data,
                user_text = self.basics.Command.data_processing_text(data)
                )
            # print("AI回复",ai_response)
            if ai_response:
                await self.basics.QQ_send_message.send_group_message(qq_TestGroup,ai_response)
                return True
                
        return False


    def add_listener(self, callback):
        """添加监听器"""
        self.listeners.append(callback)
        return True

    def remove_listener(self, callback):
        """移除监听器"""
        try:
            self.listeners.remove(callback)
            return True
        except ValueError:
            return False