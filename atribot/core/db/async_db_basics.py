import asyncio
from abc import ABC, abstractmethod
from contextvars import ContextVar
from logging import Logger
from typing import Any, Literal, Optional, Tuple

from aiomysql import Pool

from atribot.core.service_container import container


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
    async def __aenter__(self)->'AsyncDatabaseBase':
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
        fetch_type: Literal["one","all"] | None = None
    ) -> Any:
        """使用连接池执行SQL,会自动获取浮标"""
        pass
    
    @abstractmethod
    async def execute_with_pool(
        self, 
        query: str,
        params: Tuple = None, 
        fetch_type: Literal["one","all"] | None = None
    ) -> Any:
        """使用连接池执行SQL,需要手动获取浮标,用于多条语句的情况下"""
        pass
    
    async def execute_SQL(self, sql: str, argument: Tuple = None) -> Tuple:
        """执行SQL语句"""
        return await self._execute_with_pool(sql, argument, fetch_type="all")

    @abstractmethod
    async def add_user(self):
        pass
    
    @abstractmethod
    async def add_message(self):
        pass

    @abstractmethod
    async def add_group(self):
        pass
    
    @abstractmethod
    async def get_user(self):
        pass