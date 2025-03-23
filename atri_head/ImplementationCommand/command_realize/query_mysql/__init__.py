from atri_head.Basics import Basics,Command_information
from datetime import datetime


basics = Basics()
group_print = basics.QQ_send_message.send_group_message

async def query_mysql(argument,group_ID,data):
    
    minus_argument,other_argument = argument

    if basics.Command.isQQ(other_argument[0]):
        sql_days = """
SELECT
  SUM(CASE WHEN time >= UNIX_TIMESTAMP() - 86400 THEN 1 ELSE 0 END) AS daily_count,
  SUM(CASE WHEN time >= UNIX_TIMESTAMP() - 604800 THEN 1 ELSE 0 END) AS weekly_count
FROM message
WHERE user_id = %s
"""
        async with basics.async_database as db:
            
            my_tuple = await db.get_user(other_argument[0])
            daye = await db.execute_SQL(
                sql = sql_days,
                argument = (other_argument[0])
            )
        
        number_days = str(daye[0][0])
        week_daye = str(daye[0][1])
        
        if my_tuple:
            name = my_tuple[1]
            last_time:datetime = my_tuple[2]
            time = last_time.strftime("%Y-%m-%d %H:%M:%S")
            

            current_time = datetime.now()
            delta = current_time - last_time
            
            days = delta.days
            seconds = delta.seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60

            time_parts = []
            if days > 0:
                time_parts.append(f"{days}天")
            if hours > 0:
                time_parts.append(f"{hours}小时")
            if minutes > 0:
                time_parts.append(f"{minutes}分钟")
                
            if not time_parts:
                if delta.total_seconds() < 60:  
                    time_diff = "刚刚"
                else:  
                    time_diff = f"{int(delta.total_seconds()//60)}分钟前"
            else:

                if len(time_parts) > 1:
                    time_diff = "".join(time_parts[:-1]) + f"{time_parts[-1]}前"
                else:
                    time_diff = "".join(time_parts) + "前"

            await group_print(group_ID,
                f"数据库中[{name}]最后发言是在：\n{time}\n上次发言:{time_diff}\n近1天消息:{number_days}条\n近7天消息:{week_daye}条"
                )
            
        else:
            await group_print(group_ID,f"数据库中未找到用户{other_argument[0]}")
        
    else:
        Exception("请输入正确的QQ号")
        
command_main = Command_information(
    name="query_mysql",
    aliases=["query", "mysql", "查询"],
    handler=query_mysql,
    description="查询数据库,返回用户信息.目前只支持查询信息用户一些信息",
    authority_level=1, 
    parameter=[[0, 0], [1, 1]]
)