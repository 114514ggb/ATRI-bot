from atribot.core.service_container import container
from contextvars import ContextVar
from aiomysql import IntegrityError,Pool
from typing import Optional, Tuple, Any
from logging import Logger
import asyncio
from abc import ABC, abstractmethod


class AsyncDatabaseBase(ABC):
    """异步数据库连接池抽象基类"""
    _pool: Optional[Pool] = None
    _init_lock = asyncio.Lock()
    _context_conn: ContextVar[Optional[Any]] = ContextVar('conn', default=None)
    _context_cursor: ContextVar[Optional[Any]] = ContextVar('cursor', default=None)
    
    def __init__(self):
        self.log: Logger = container.get("log")
    
    @classmethod
    @abstractmethod
    async def create(cls, **kwargs) -> "AsyncDatabaseBase":
        """创建连接池"""
        pass
    
    @classmethod
    @abstractmethod
    async def close_pool(cls):
        """关闭连接池"""
        pass
    
    @abstractmethod
    async def __aenter__(self):
        """获取连接和游标"""
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """释放连接回池"""
        pass
    
    @abstractmethod
    async def _execute_with_pool(
        self, 
        query: str,
        params: Tuple = None, 
        fetch_type: str = None
    ) -> Any:
        """使用连接池执行SQL"""
        pass
    
    async def execute_SQL(self, sql: str, argument: Tuple = None) -> Tuple:
        """执行SQL语句"""
        return await self._execute_with_pool(sql, argument, fetch_type="all")
    
    async def add_user(self, user_id: int, nickname: str) -> bool:
        """添加用户"""
        try:
            await self._execute_with_pool(
                """
                INSERT INTO users (user_id, nickname) 
                VALUES (%s, %s) AS new
                ON DUPLICATE KEY UPDATE 
                    nickname = new.nickname,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (user_id, nickname)
            )
            return True
        except IntegrityError as e:
            self.log.error(f"添加用户失败: {e}")
            return False
    
    async def get_user(self, user_id: int) -> Optional[Tuple]:
        """查询单个用户"""
        return await self._execute_with_pool(
            "SELECT * FROM users WHERE user_id = %s",
            (user_id,),
            fetch_type="one"
        )
    
    async def add_group(self, group_id: int, group_name: str) -> bool:
        """添加群组"""
        try:
            await self._execute_with_pool(
                """
                INSERT INTO user_group (group_id, group_name) 
                VALUES (%s, %s) AS new
                ON DUPLICATE KEY UPDATE 
                    group_name = new.group_name
                """,
                (group_id, group_name)
            )
            return True
        except IntegrityError as e:
            self.log.error(f"添加群组失败: {e}")
            return False
    
    async def get_group(self, group_id: int) -> Optional[Tuple]:
        """查询单个群组"""
        return await self._execute_with_pool(
            "SELECT * FROM user_group WHERE group_id = %s",
            (group_id,),
            fetch_type="one"
        )
    
    async def get_all_group(self) -> Tuple:
        """查询所有群组"""
        return await self._execute_with_pool(
            "SELECT * FROM user_group",
            fetch_type="all"
        )
    
    async def add_message(
        self, 
        message_id: int, 
        user_id: int, 
        group_id: int,
        timestamp: int, 
        content: str
    ) -> bool:
        """添加消息"""
        try:
            await self._execute_with_pool(
                """INSERT INTO message 
                (message_id, user_id, group_id, time, message_content)
                VALUES (%s, %s, %s, %s, %s)""",
                (message_id, user_id, group_id, timestamp, content)
            )
            return True
        except IntegrityError as e:
            self.log.error(f"添加消息失败: {e}")
            return False
    
    async def get_messages_by_user(self, user_id: int, limit: int = 50) -> Tuple:
        """查询用户最近消息"""
        return await self._execute_with_pool(
            """SELECT * FROM message 
            WHERE user_id = %s 
            ORDER BY time DESC 
            LIMIT %s""",
            (user_id, limit),
            fetch_type="all"
        )
    
    async def get_messages_by_group(self, group_id: int, limit: int = 50) -> Tuple:
        """查询群组最近消息"""
        return await self._execute_with_pool(
            """SELECT * FROM message 
            WHERE group_id = %s 
            ORDER BY time DESC 
            LIMIT %s""",
            (group_id, limit),
            fetch_type="all"
        )