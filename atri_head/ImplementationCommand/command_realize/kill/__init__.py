from atri_head.Basics import Basics,Command_information


basics = Basics()


async def kill(argument,qq_TestGroup,data):
    """清除记忆"""
    if len(basics.AI_interaction.chat.messages) > 1:
        basics.AI_interaction.chat.reset_chat()
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
