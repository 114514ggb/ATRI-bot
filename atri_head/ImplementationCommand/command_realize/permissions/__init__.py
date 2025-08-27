from atri_head.Basics import Basics,Command_information,Command


basics = Basics()
Command_ = Command()

async def permissions_my(argument,group_ID,data):
    """查看自己的权限"""
    message = "你现在的权限等级是: " + Command_.my_permissions(data['user_id'])
    await basics.QQ_send_message.send_group_message(group_ID,message)
    return True

command_main = Command_information(
    name="permissions",
    aliases=["我的权限", "permissions"],
    handler=permissions_my,
    description="查看自己的权限",
    authority_level=0, 
)