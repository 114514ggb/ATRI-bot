from atri_head.Basics import Basics,Command_information


basics = Basics()


async def kill(argument,group_ID,data):
    """清除记忆"""
    await basics.ai_chat_manager.reset_group_chat(group_ID)
    await basics.QQ_send_message.send_group_message(group_ID,"ATRI的记忆已经被清除,重新开始对话吧!😊")
    return "ok"

    
command_main = Command_information(
    name="kill",
    aliases=["失忆", "kill"],
    handler=kill,
    description="清除记忆",
)
