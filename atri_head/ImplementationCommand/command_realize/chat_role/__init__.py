from atri_head.Basics import Basics,Command_information


basics = Basics()


async def toggleModel(argument,qq_TestGroup,data):
    """切换模型人物"""
    playRole = argument[1][0]
    group_id = str(data["group_id"])

    if playRole in basics.AI_interaction.chat.playRole_list:
        basics.AI_interaction.chat.Default_playRole = basics.AI_interaction.chat.playRole_list[playRole]
        basics.AI_interaction.chat.reset_chat(group_id)
    else:
        raise Exception("没有这个角色")

    await basics.QQ_send_message.send_group_message(qq_TestGroup,f"已切换为人物:{playRole}")

    return "ok"

command_main = Command_information(
    name="chat_role",
    aliases=["角色", "role"],
    handler=toggleModel,
    description="切换模型人物,none无人物",
    authority_level=3, 
    parameter=[[0, 0], [1, 1]]
)