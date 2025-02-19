from atri_head.Basics import Basics,Command_information



basics = Basics()
async def query_mysql(argument,qq_TestGroup,data):
    
    minus_argument,other_argument = argument
    if basics.Command.isQQ(other_argument[0]):
        
        await basics.async_database.found_cursor()
        my_tuple = (await basics.async_database.get_user(other_argument[0]))
        await basics.async_database.close_cursor()
        
        if my_tuple:
            name = my_tuple[1]
            time = my_tuple[2].strftime("%Y-%m-%d %H:%M:%S")

            await basics.QQ_send_message.send_group_message(qq_TestGroup,f"数据库中[{name}]最后发言是在：\n{time}")
        else:
            await basics.QQ_send_message.send_group_message(qq_TestGroup,f"数据库中未找到用户{other_argument[0]}")
        
    else:
        Exception("请输入正确的QQ号")
        
command_main = Command_information(
    name="query_mysql",
    aliases=["query", "mysql", "查询"],
    handler=query_mysql,
    description="查询数据库,返回用户信息.目前只支持查询信息用户最后更新时间",
    authority_level=1, 
    parameter=[[0, 0], [1, 1]]
)