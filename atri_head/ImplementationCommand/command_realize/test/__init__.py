from atri_head.Basics import Basics,Command_information


basics = Basics()

async def test(argument,group_ID,data):
    """测试参数等"""
    [argument_1, argument_2] = argument
    
    if argument_1 and argument_1[0] == "exe":
        exec(" ".join(argument_2))

    # message = "'-'开头参数:"+', '.join(argument_1)+"\n其他参数:"+', '.join(argument_2)
    
    # await basics.QQ_send_message.send_group_merge_forward(group_ID, "ATRI接收到的参数有:\n"+message)
    # await basics.QQ_send_message.send_group_message(group_ID,"ATRI接收到的参数有:\n"+message+"\n要exec语句为:"+argument_2[0])

    return "ok"

command_main = Command_information(
    name="test",
    aliases=["测试", "test"],
    handler=test,
    description="测试用命令",
    authority_level=3,
    parameter=[[0, 9], [0, 9]]
)
