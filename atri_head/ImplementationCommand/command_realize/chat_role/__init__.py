from atri_head.Basics import Basics,Command_information


basics = Basics()


async def toggleModel(argument,group_ID,data):
    """切换模型人物"""
    
    group_ID = str(group_ID)
    if argument[0] != []:
        dash_argument = argument[0][0]
        if dash_argument in ["l","all"] :
            
            name_list = "可用扮演角色：\n"
            for key in basics.ai_chat_manager.play_role_list.keys():
                name_list += key + "\n"
            
            await basics.QQ_send_message.send_group_merge_forward(
                group_ID, 
                name_list,
                source = "可用人设"
            )
            
        else:
            raise ValueError(f"无效dash参数\"{dash_argument}\"!")
        
    if argument[1] != []:
        playRole =  argument[1][0]
        if playRole in basics.ai_chat_manager.play_role_list:
            await basics.ai_chat_manager.set_group_role(group_ID,playRole)
            await basics.ai_chat_manager.reset_group_chat(group_ID)
        else:
            raise Exception("没有这个角色!")

        await basics.QQ_send_message.send_group_message(group_ID,f"已切换为人物:{playRole}")


    return "ok"

command_main = Command_information(
    name="chat_role",
    aliases=["角色", "role"],
    handler=toggleModel,
    description="切换模型人物,切换会清除上下文,none无人物,-l或-all参数查看可扮演list",
    authority_level=2, 
    parameter=[[0, 1], [0, 1]]
)