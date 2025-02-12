from atri_head.Basics import Basics,Command_information


basics = Basics()


async def permissions_my(argument,qq_TestGroup,data):
    """查看自己的权限"""
    message = "你现在的权限等级是: " + basics.Command.my_permissions(data['user_id'])
    await basics.QQ_send_message.send_group_message(qq_TestGroup,message)
    return True

command_main = Command_information(
    name="permissions",
    aliases=["我的权限", "permissions"],
    handler=permissions_my,
    description="查看自己的权限",
    authority_level=0, 
)