from datetime import datetime, timedelta

from atribot.common_utils import is_qq
from atribot.core.db.async_db_basics import AsyncDatabaseBase
from atribot.core.platform.send_client import SendClientBase
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope


class UserActivityAnalyzer:
    """
    QQ用户活跃度分析器
    
    提供用户消息统计、活跃度分析和报告生成功能
    """
    
    def __init__(self):
        self.db: AsyncDatabaseBase = container.get("database")
    
    async def query_mysql(self, message_data: MessageEventEnvelope, user_id: int) -> None:
        """查询MySQL数据库并生成用户活跃度报告

        Args:
            message_data (dict): 默认传入data
            user_id (int, optional): _description_. Defaults to 0.

        Raises:
            ValueError: user_id参数错误
        """
        user_id = user_id if user_id else message_data.user_id
        group_id = message_data.group_id
        
        if not is_qq(user_id):
            raise ValueError("请输入正确的QQ号")
            
        if not await self._process_user_data(message_data.send_client, user_id, group_id):
            await message_data.send_client.send_group_msg(group_id, f"数据库中未找到qq:{user_id}")
    
    async def _process_user_data(self, send_client: SendClientBase, user_id: str, group_id: int) -> bool:
        """
        处理用户数据并生成报告
        
        Args:
            user_id: 用户QQ号
            group_id: 群组ID
            
        Returns:
            bool: 是否成功找到用户
        """

        sql_combined = """
        SELECT
          SUM(CASE WHEN time >= EXTRACT(EPOCH FROM NOW()) - 86400 THEN 1 ELSE 0 END) AS daily_count,
          SUM(CASE WHEN time >= EXTRACT(EPOCH FROM NOW()) - 604800 THEN 1 ELSE 0 END) AS weekly_count,
          COUNT(*) AS monthly_count, 
          (SELECT MIN(time) FROM message WHERE user_id = $1) AS earliest_time
        FROM message
        WHERE user_id = $1 AND time >= EXTRACT(EPOCH FROM NOW()) - 2592000
        """
        
        async with self.db as db:
            my_tuple = await db.get_user(user_id)
            if not my_tuple:
                return False
                
            stats_data = await db.execute_SQL(sql=sql_combined, argument=(user_id,))
        
        return await self._generate_report(send_client, group_id, my_tuple, stats_data)
    
    async def _generate_report(self, send_client: SendClientBase, group_id: int, user_data: tuple, stats_data: tuple):
        """
        生成并发送用户活跃度报告
        
        Args:
            group_id: 群组ID
            user_data: 用户基础数据元组
            stats_data: 统计数据元组 (daily, weekly, monthly, earliest_time)
        """
        number_days = stats_data[0][0] or 0
        week_daye = stats_data[0][1] or 0
        month_daye = stats_data[0][2] or 0
        earliest_time = stats_data[0][3]
        
        name = user_data[1]
        last_time: datetime = user_data[2]
        time = last_time.strftime("%Y-%m-%d %H:%M:%S")
        current_time = datetime.now()

        last_active_diff = self._format_timedelta(current_time - last_time)
        if earliest_time:
            earliest_date = datetime.fromtimestamp(earliest_time)
            earliest_diff = self._format_timedelta(current_time - earliest_date)
            days_since_earliest = (current_time - earliest_date).days
        else:
            # 如果找不到最早发言时间，默认设为当前时间或做特殊处理
            earliest_date = current_time
            earliest_diff = "无记录"
            days_since_earliest = 0

        actual_days = min(days_since_earliest, 30)
        
        activity_level = self._evaluate_activity(
            number_days, month_daye, actual_days, days_since_earliest)

        activity_score = self._calculate_activity_score(
            number_days, week_daye, month_daye,
            month_daye, actual_days)

        trend = self._evaluate_trend(number_days, week_daye, month_daye)

        await send_client.send_group_msg(
            group_id,
            f"✨ QQ用户活跃报告 ✨\n"
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
            f"  ▫️ 平均每日消息(近30天): {month_daye/max(actual_days, 1):.1f}\n"
            f"  ▫️ 近1天: {number_days}条\n"
            f"  ▫️ 近7天: {week_daye}条\n"
            f"  ▫️ 近30天: {month_daye}条\n"
            f"\n"
            f"📈 综合评价\n"
            f"  ⭐ 活跃度: {activity_level}\n"
            f"  🔢 评分: {activity_score}/100\n"
            f"  🔁 趋势: {trend}\n"
            f"----------------------------------------"
        )
        return True
    
    def _format_timedelta(self, delta: timedelta) -> str:
        """
        将时间差格式化为'X天Y小时Z分钟A秒'的字符串
        
        Args:
            delta: 时间差对象
            
        Returns:
            str: 格式化后的时间字符串
        """
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
        if seconds > 0 or not parts:
            parts.append(f"{seconds}秒")
        
        return "".join(parts) + "前" if parts else "刚刚"
    
    def _evaluate_activity(self, daily: int, total_30d: int, actual_days: int, days_since_earliest: int) -> str:
        """
        评估用户活跃度等级
        
        Args:
            daily: 每日消息数
            total_30d: 近30天消息总数
            actual_days: 实际统计天数(不超过30)
            days_since_earliest: 最早消息距今天数
            
        Returns:
            str: 活跃度等级描述
        """
        avg_daily = total_30d / max(1, actual_days)
        
        if daily == 0:
            return "潜水员(近期无发言)"
        elif daily <= 5:
            level = "偶尔冒泡"
        elif daily <= 25:
            level = "普通活跃"
        elif daily <= 50:
            level = "高度活跃"
        else:
            level = "话痨"
        
        if days_since_earliest > 30:
            if avg_daily > 5:
                level += "+长期活跃"
            elif avg_daily < 1:
                level += "+长期潜水"
        
        return level
    
    def _calculate_activity_score(self, daily: int, weekly: int, monthly: int, total_30d: int, actual_days: int) -> float:
        """
        计算用户活跃度评分
        
        Args:
            daily: 每日消息数
            weekly: 每周消息数
            monthly: 每月消息数
            total_30d: 近30天消息总数
            actual_days: 实际统计天数(不超过30)
            
        Returns:
            float: 活跃度评分(0-100)
        """
        weights = {
            'daily': 0.4,
            'weekly': 0.3,
            'monthly': 0.2,
            'consistency': 0.1
        }
        
        daily_norm = min(daily / 50, 1)  
        weekly_norm = min(weekly / 300, 1)
        monthly_norm = min(monthly / 1000, 1)
        consistency = min(total_30d / max(1, actual_days * 5), 1)
        
        score = (
            daily_norm * weights['daily'] +
            weekly_norm * weights['weekly'] +
            monthly_norm * weights['monthly'] +
            consistency * weights['consistency']
        ) * 100
        
        return round(score, 1)
    
    def _evaluate_trend(self, daily: int, weekly: int, monthly: int) -> str:
        """
        评估用户活跃趋势
        
        Args:
            daily: 每日消息数
            weekly: 每周消息数
            monthly: 每月消息数
            
        Returns:
            str: 趋势描述
        """
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