import aiomysql
from aiomysql import IntegrityError, Pool
from atribot.core.service_container import container
from contextvars import ContextVar
from typing import Optional, Tuple
from logging import Logger
import asyncio


class atriAsyncMySQL:
    """msyql异步数据库连接池"""
    _pool: Optional[Pool] = None
    _init_lock = asyncio.Lock()
    _context_conn: ContextVar[Optional[aiomysql.Connection]] = ContextVar('conn', default=None)
    _context_cursor: ContextVar[Optional[aiomysql.Cursor]] = ContextVar('cursor', default=None)
    
    def __init__(self):
        self.log: Logger = container.get("log")

    
    @classmethod
    async def create(
        cls, 
        host: str, 
        user: str, 
        password: str, 
        pool_minsize: int = 2, 
        pool_maxsize: int = 8
    ) -> "atriAsyncMySQL":
        """推荐初始创建连接池（单例模式）的方法"""
        log: Logger = container.get("log")
        
        if cls._pool is None:
            async with cls._init_lock:
                if cls._pool is None:
                    log.info("初始化数据库连接池...")
                    cls._pool = await aiomysql.create_pool(
                        host=host,
                        user=user,
                        password=password,
                        db='atri',
                        charset='utf8mb4',
                        autocommit=True,
                        minsize=pool_minsize,
                        maxsize=pool_maxsize,
                        pool_recycle=300
                    )
                    log.info(f"连接池已创建（大小：{pool_minsize}-{pool_maxsize}）")
        return cls()
    
    @classmethod
    async def close_pool(cls):
        """关闭连接池"""
        if cls._pool:
            cls._pool.close()
            await cls._pool.wait_closed()
            cls._pool = None
    
    async def __aenter__(self):
        """获取连接和游标"""
        if not self._pool:
            raise RuntimeError("连接池未初始化，请先调用 create() 方法")
        
        self._conn = await self._pool.acquire()
        self._cursor = await self._conn.cursor()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """释放连接回池"""
        if self._cursor:
            await self._cursor.close()
            self._cursor = None
        
        if self._conn and self._pool:
            self._pool.release(self._conn)
            self._conn = None
    
    async def _execute_with_pool(
            self, 
            query: str,
            params: Tuple = None, 
            fetch_type: str = None
        ) -> any:
        """
        使用连接池执行 SQL 语句，并根据 fetch_type 返回结果。

        Args:
            query (str): 需要执行的 SQL 语句。
            params (Tuple, optional): SQL 语句的参数，用于防止 SQL 注入。默认为 None。
            fetch_type (str, optional): 指定返回结果的类型。
                - "one": 返回查询结果的第一条记录。
                - "all": 返回查询结果的所有记录。
                - 其他值或不传: 不返回查询结果，仅返回 True 表示执行成功。

        Returns:
            any: 根据 fetch_type 返回不同的结果：
                - fetch_type == "one": 返回查询结果的第一条记录（通常是一个元组或字典）。
                - fetch_type == "all": 返回查询结果的所有记录（通常是列表嵌套元组或字典）。
                - 其他情况: 返回 True，表示 SQL 执行成功。

        Raises:
            RuntimeError: 如果连接池未初始化（即 self._pool 为 None）。
        """
        if hasattr(self, '_cursor') and self._cursor and not self._cursor.closed:

            await self._cursor.execute(query, params)
            if fetch_type == "one":
                return await self._cursor.fetchone()
            elif fetch_type == "all":
                return await self._cursor.fetchall()
            return True
        

        if not self._pool:
            raise RuntimeError("连接池未初始化")
        
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                if fetch_type == "one":
                    return await cursor.fetchone()
                elif fetch_type == "all":
                    return await cursor.fetchall()
                return True
    
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
    
    async def execute_SQL(self, sql: str, argument: Tuple) -> Tuple:
        """执行SQL语句"""
        return await self._execute_with_pool(sql, argument, fetch_type="all")

