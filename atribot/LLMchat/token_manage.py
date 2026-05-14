import traceback
from logging import Logger
from typing import Optional

from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.service_container import container


class TokenManager:
    """Token 消耗统计日志与管理服务"""

    def __init__(self):
        self.log:Logger = container.get("log")
        self.db:AsyncPostgreSQL = container.get("database")

    async def record_token_usage(
        self,
        user_id: Optional[int],
        group_id: Optional[int],
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        model_name: str
    ) -> bool:
        """记录 Token 使用量统计"""
        try:
            async with self.db as db:
                await db.execute_with_pool(
                    """
                    INSERT INTO token_statistics (user_id, group_id, model, prompt_tokens, completion_tokens, total_tokens)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    (user_id, group_id, model_name, prompt_tokens, completion_tokens, total_tokens)
                )
            return True
        except Exception as e:
            self.log.error(f"记录 token 消耗统计失败: {e}\n{traceback.format_exc()}")
            return False

    async def get_token_statistics(self, user_id: Optional[int] = None, group_id: Optional[int] = None) -> dict:
        """获取 Token 使用量统计"""
        try:
            query = "SELECT SUM(prompt_tokens) as prompt_tokens, SUM(completion_tokens) as completion_tokens, SUM(total_tokens) as total_tokens FROM token_statistics WHERE 1=1"
            params = []
            if user_id is not None:
                params.append(user_id)
                query += f" AND user_id = ${len(params)}"
            if group_id is not None:
                params.append(group_id)
                query += f" AND group_id = ${len(params)}"
            async with self.db as db:    
                row = await db.execute_with_pool(query, tuple(params), fetch_type="one")
            
            return {
                "prompt_tokens": row["prompt_tokens"] if row and row["prompt_tokens"] else 0,
                "completion_tokens": row["completion_tokens"] if row and row["completion_tokens"] else 0,
                "total_tokens": row["total_tokens"] if row and row["total_tokens"] else 0
            }
        except Exception as e:
            self.log.error(f"获取 token 消耗统计失败: {e}\n{traceback.format_exc()}")
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    async def get_period_token_statistics(self, user_id: Optional[int] = None, group_id: Optional[int] = None, days: int = 30) -> dict:
        """获取指定时间范围内的 Token 使用量统计"""
        try:
            query = "SELECT SUM(prompt_tokens) as prompt_tokens, SUM(completion_tokens) as completion_tokens, SUM(total_tokens) as total_tokens FROM token_statistics WHERE created_at >= NOW() - $1 * interval '1 day'"
            params = [days]
            if user_id is not None:
                params.append(user_id)
                query += f" AND user_id = ${len(params)}"
            if group_id is not None:
                params.append(group_id)
                query += f" AND group_id = ${len(params)}"
                
            row = await self.db.execute_with_pool(query, tuple(params), fetch_type="one")
            
            return {
                "prompt_tokens": row["prompt_tokens"] if row and row["prompt_tokens"] else 0,
                "completion_tokens": row["completion_tokens"] if row and row["completion_tokens"] else 0,
                "total_tokens": row["total_tokens"] if row and row["total_tokens"] else 0
            }
        except Exception as e:
            self.log.error(f"获取时期 token 消耗统计失败: {e}\n{traceback.format_exc()}")
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    async def get_daily_token_breakdown(self, user_id: Optional[int] = None, group_id: Optional[int] = None, days: int = 7) -> list:
        """获取最近N天按天的消耗明细"""
        try:
            query = """
            SELECT DATE(created_at) as date, SUM(total_tokens) as daily_total
            FROM token_statistics 
            WHERE created_at >= CURRENT_DATE - $1 * interval '1 day'
            """
            params = [days]
            if user_id is not None:
                params.append(user_id)
                query += f" AND user_id = ${len(params)}"
            if group_id is not None:
                params.append(group_id)
                query += f" AND group_id = ${len(params)}"
            
            query += " GROUP BY DATE(created_at) ORDER BY DATE(created_at) ASC"
            
            async with self.db as db:
                rows = await db.execute_with_pool(query, tuple(params), fetch_type="all")
            return rows if rows else []
        except Exception as e:
            self.log.error(f"获取按日 token 消耗明细失败: {e}\n{traceback.format_exc()}")
            return []

    async def get_model_token_breakdown(self, user_id: Optional[int] = None, group_id: Optional[int] = None, days: int = 7) -> list:
        """获取最近N天按模型的消耗明细"""
        try:
            query = """
            SELECT model, SUM(total_tokens) as model_total
            FROM token_statistics 
            WHERE created_at >= CURRENT_DATE - $1 * interval '1 day'
            """
            params = [days]
            if user_id is not None:
                params.append(user_id)
                query += f" AND user_id = ${len(params)}"
            if group_id is not None:
                params.append(group_id)
                query += f" AND group_id = ${len(params)}"
            
            query += " GROUP BY model ORDER BY SUM(total_tokens) DESC"
            async with self.db as db:
                rows = await db.execute_with_pool(query, tuple(params), fetch_type="all")
            return rows if rows else []
        except Exception as e:
            self.log.error(f"获取按模型 token 消耗明细失败: {e}\n{traceback.format_exc()}")
            return []
