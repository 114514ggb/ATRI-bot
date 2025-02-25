from atri_head.Basics import Basics,Command_information


basics = Basics()


async def kill(argument,qq_TestGroup,data):
    """清除记忆"""
    group_id = data[group_id]
    message_list:list = basics.AI_interaction.chat.all_group_messages_list[group_id]
    if len(message_list) >= 2:
        message_list = []
        await basics.QQ_send_message.send_group_message(qq_TestGroup,"ATRI的记忆已经被清除,重新开始对话吧!😊")
        return "ok"
    else:
        await basics.QQ_send_message.send_group_message(qq_TestGroup,"Type Error:\n ATRI已经没有记忆了,所以当然什么也没有发生!😓")
        return "no"
    
command_main = Command_information(
    name="kill",
    aliases=["失忆", "kill"],
    handler=kill,
    description="清除记忆",
)
