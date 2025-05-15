from atri_head.Basics import Basics,Command_information
from datetime import datetime


basics = Basics()
group_print = basics.QQ_send_message.send_group_message

async def query_mysql(argument, group_ID, data):
    def format_timedelta(delta):
        """将时间差格式化为'X天Y小时Z分钟A秒'的字符串"""
        days = delta.days
        seconds = delta.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}小时")
        if minutes > 0:
            parts.append(f"{minutes}分钟")
        if seconds > 0 or not parts:  # 至少显示秒数
            parts.append(f"{seconds}秒")
        
        return "".join(parts) + "前" if parts else "刚刚"

    minus_argument, other_argument = argument

    if basics.Command.isQQ(other_argument[0]):
        sql_days = """
SELECT
  SUM(CASE WHEN time >= UNIX_TIMESTAMP() - 86400 THEN 1 ELSE 0 END) AS daily_count,
  SUM(CASE WHEN time >= UNIX_TIMESTAMP() - 604800 THEN 1 ELSE 0 END) AS weekly_count,
  SUM(CASE WHEN time >= UNIX_TIMESTAMP() - 2592000 THEN 1 ELSE 0 END) AS monthly_count,
  COUNT(*) AS total_count,
  MIN(time) AS earliest_time
FROM message
WHERE user_id = %s
"""
        async with basics.async_database as db:
            my_tuple = await db.get_user(other_argument[0])
            daye = await db.execute_SQL(
                sql=sql_days,
                argument=(other_argument[0],)
            )
            
        number_days = str(daye[0][0])
        week_daye = str(daye[0][1])
        month_daye = str(daye[0][2])
        total_count = str(daye[0][3])
        earliest_time = daye[0][4]
        
        if my_tuple:
            name = my_tuple[1]
            last_time: datetime = my_tuple[2]
            time = last_time.strftime("%Y-%m-%d %H:%M:%S")
            current_time = datetime.now()

            last_active_diff = format_timedelta(current_time - last_time)
            earliest_date = datetime.fromtimestamp(earliest_time)
            earliest_diff = format_timedelta(current_time - earliest_date)
            days_since_earliest = (current_time - earliest_date).days

            activity_level = evaluate_activity(
                int(number_days), int(week_daye), int(month_daye),
                int(total_count), days_since_earliest)

            activity_score = calculate_activity_score(
                int(number_days), int(week_daye), int(month_daye),
                int(total_count), days_since_earliest)

            trend = evaluate_trend(int(number_days), int(week_daye), int(month_daye))

            await group_print(
                group_ID,
                f"✨【QQ用户活跃报告】✨\n"
                f"----------------------------------------\n"
                f"👤 基础信息\n"
                f"  名称: {name}\n"
                f"  最后发言时间: {time}\n"
                f"  上次发言: {last_active_diff}\n"
                f"\n"
                f"⏳ 时间轴\n"
                f"  📅 最早消息日期: {earliest_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  📆 最早距今: {earliest_diff}\n"
                f"\n"
                f"📊 活跃数据\n"
                f"  ▫️ 平均每日消息: {int(total_count)/max(days_since_earliest, 1):.1f}\n"
                f"  ▫️ 近1天: {number_days}条\n"
                f"  ▫️ 近7天: {week_daye}条\n"
                f"  ▫️ 近30天: {month_daye}条\n"
                f"  ▫️ 总消息数: {total_count}条\n"
                f"\n"
                f"📈 综合评价\n"
                f"  ⭐ 活跃度: {activity_level}\n"
                f"  🔢 评分: {activity_score}/100\n"
                f"  🔁 趋势: {trend}\n"
                f"----------------------------------------"
            )
        else:
            await group_print(group_ID, f"数据库中未找到用户{other_argument[0]}")
    else:
        Exception("请输入正确的QQ号")
        
        
def evaluate_activity(daily, weekly, monthly, total, days_since_earliest):
    """等级评价"""
    avg_daily = total / max(1, days_since_earliest)
    
    if daily == 0:
        return "潜水员(近期无发言)"
    elif daily <= 3:
        level = "偶尔冒泡"
    elif daily <= 10:
        level = "普通活跃"
    elif daily <= 30:
        level = "高度活跃"
    else:
        level = "话痨"
    
    if days_since_earliest > 31:
        if avg_daily > 5:
            level += "+长期活跃"
        elif avg_daily < 1:
            level += "+长期潜水"
    
    return level        
        
        
def calculate_activity_score(daily, weekly, monthly, total, days_since_earliest):
    """综合评分系统"""
    # 权重分配
    weights = {
        'daily': 0.4,
        'weekly': 0.3,
        'monthly': 0.2,
        'consistency': 0.1
    }
    
    daily_norm = min(daily / 50, 1)  
    weekly_norm = min(weekly / 300, 1)
    monthly_norm = min(monthly / 1000, 1)
    consistency = min(total / max(1, days_since_earliest * 5), 1)  
    
    score = (
        daily_norm * weights['daily'] +
        weekly_norm * weights['weekly'] +
        monthly_norm * weights['monthly'] +
        consistency * weights['consistency']
    ) * 100
    
    return round(score, 1)
        
        
def evaluate_trend(daily, weekly, monthly):
    """趋势分析评价"""
    weekly_avg = weekly / 7
    monthly_avg = monthly / 30
    
    if daily > monthly_avg * 1.5:
        trend = "活跃度上升↑↑"
    elif daily < monthly_avg * 0.5:
        trend = "活跃度下降↓↓"
    else:
        trend = "活跃度稳定→"
    
    if weekly_avg > monthly_avg * 1.2:
        trend += "(近期更活跃)"
    elif weekly_avg < monthly_avg * 0.8:
        trend += "(近期较沉默)"
    
    return trend



command_main = Command_information(
    name="query_mysql",
    aliases=["query", "mysql", "查询"],
    handler=query_mysql,
    description="查询数据库,返回用户信息.目前只支持查询信息用户一些信息",
    authority_level=1, 
    parameter=[[0, 0], [1, 1]]
)