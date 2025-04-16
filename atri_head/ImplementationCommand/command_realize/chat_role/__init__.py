from atri_head.Basics import Basics,Command_information


basics = Basics()


async def toggleModel(argument,group_ID,data):
    """切换模型人物"""
    group_id = str(data["group_id"])
    
    if argument[0] != []:
        dash_argument = argument[0][0]
        if dash_argument in ["l","all"] :
            
            name_list = "可用扮演角色：\n"
            for key in basics.AI_interaction.chat.playRole_list.keys():
                name_list += key + "\n"
            
            await basics.QQ_send_message.send_group_merge_forward(group_ID, name_list)
            
        else:
            raise ValueError(f"无效dash参数\"{dash_argument}\"!")
        
    if argument[1] != []:
        playRole =  argument[1][0]
        if playRole in basics.AI_interaction.chat.playRole_list:
            basics.AI_interaction.chat.Default_playRole = basics.AI_interaction.chat.playRole_list[playRole]
            basics.AI_interaction.chat.reset_chat(group_id)
        else:
            raise Exception("没有这个角色!")

        await basics.QQ_send_message.send_group_message(group_ID,f"已切换为人物:{playRole}")


    return "ok"

command_main = Command_information(
    name="chat_role",
    aliases=["角色", "role"],
    handler=toggleModel,
    description="切换模型人物,none无人物,-l或-all参数",
    authority_level=3, 
    parameter=[[0, 1], [0, 1]]
)