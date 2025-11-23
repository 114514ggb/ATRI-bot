import asyncpg
from typing import Optional, Tuple, Any, List
import asyncio
from asyncpg import Record
from contextvars import ContextVar,Token
from asyncpg.exceptions import UniqueViolationError, ForeignKeyViolationError
from atribot.core.db.async_db_basics import AsyncDatabaseBase


class atriAsyncPostgreSQL(AsyncDatabaseBase):
    """PostgreSQL异步数据库实现"""
    
    _pool: Optional[asyncpg.Pool] = None
    _init_lock = asyncio.Lock()
    _context_conn: ContextVar[Optional[asyncpg.Connection]] = ContextVar('conn', default=None)
    _context_token: ContextVar[Optional[Token]] = ContextVar('token', default=None)
    
    def __init__(self):
        super().__init__()
        self._conn_token = None
    
    @classmethod
    async def create(
        cls, 
        host: str = "localhost",
        port: int = 5432,
        user: str = "atri",
        password: str = "180710",
        database: str = "atri",
        min_size: int = 2,
        max_size: int = 8,
        **kwargs
    ) -> "atriAsyncPostgreSQL":
        """
        创建并初始化一个 PostgreSQL 连接池（单例模式）。

        Args:
            host (str): 数据库主机地址，默认为 "localhost"。
            port (int): 数据库端口，默认为 5432。
            user (str): 数据库用户名，默认为 "postgres"。
            password (str): 数据库密码，默认为空字符串。
            database (str): 数据库名称，默认为 "postgres"。
            min_size (int): 连接池最小连接数，默认为 2。
            max_size (int): 连接池最大连接数，默认为 8。
            **kwargs: 其他传递给 `asyncpg.create_pool` 的关键字参数，如 `command_timeout`、`server_settings` 等。

        Returns:
            atriAsyncPostgreSQL: 返回当前类的一个实例，后续可通过该实例执行 SQL。

        Raises:
            Exception: 如果连接池创建失败
        """
        
        async with cls._init_lock:
            if cls._pool is None:
                try:
                    cls._pool = await asyncpg.create_pool(
                        host=host,
                        port=port,
                        user=user,
                        password=password,
                        database=database,
                        min_size=min_size,
                        max_size=max_size,
                        **kwargs
                    )
                except Exception as e:
                    raise Exception(f"创建数据库连接池失败: {e}")
                cls().log.info(f"PostgreSQL连接池已创建（大小：{min_size}-{max_size}）")
            return cls()
    
    @classmethod
    async def close_pool(cls):
        """关闭连接池"""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
    
    async def __aenter__(self):
        """获取连接"""
        if self._pool is None:
            raise RuntimeError("数据库连接池未初始化")
        
        if self._context_conn.get() is not None:
            return self
        
        conn = await self._pool.acquire()
        token = self._context_conn.set(conn)
        self._context_token.set(token)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """释放连接回池"""
        token = self._context_token.get()
        if token is not None:
            conn = self._context_conn.get()
            if conn:
                await self._pool.release(conn)
            self._context_conn.reset(token)
            self._context_token.set(None)
    
    def get_connection(self) -> asyncpg.Connection:
        """获取当前上下文连接"""
        conn = self._context_conn.get()
        if conn is None:
            raise RuntimeError("未在异步上下文管理器中使用数据库连接")
        return conn
    
    async def _execute_with_pool(
        self, 
        query: str,
        params: Tuple = None, 
        fetch_type: str = None
    ) -> Record|None:
        """使用连接池执行SQL,会自动处理%s转换成$1"""
        
        conn = self._context_conn.get()
        temp_conn = None
        
        try:
            # 如果没有上下文连接，临时获取一个
            if conn is None:
                temp_conn = await self._pool.acquire()
                conn = temp_conn
            
            # 转换占位符兼容原有语句
            query = self._convert_query_placeholders(query) if params else query
            args = params or ()
            
            if fetch_type == "one":
                return await conn.fetchrow(query, *args)
            elif fetch_type == "all":
                return await conn.fetch(query, *args)
            else:
                await conn.execute(query, *args)
                return True
                
        except (UniqueViolationError, ForeignKeyViolationError) as e:
            self.log.error(f"数据库约束冲突: {e}")
            raise
        except Exception as e:
            self.log.error(f"SQL执行错误: {e}, 查询: {query}, 参数: {params}")
            raise
        finally:
            if temp_conn:
                await self._pool.release(temp_conn)
                
    async def execute_with_pool(
        self, 
        query: str,
        params: Tuple = None, 
        fetch_type: str = None
    ) -> Record|None:
        """使用连接池执行SQL,需要提前获取浮标,用于多条语句的情况下"""
        
        conn = self._context_conn.get()
        
        try:

            args = params or ()
            
            if fetch_type == "one":
                return await conn.fetchrow(query, *args)
            elif fetch_type == "all":
                return await conn.fetch(query, *args)
            else:
                await conn.execute(query, *args)
            
                return True
                
                
        except (UniqueViolationError, ForeignKeyViolationError) as e:
            self.log.error(f"数据库约束冲突: {e}")
            raise
        except Exception as e:
            self.log.error(f"SQL执行错误: {e}, 查询: {query}, 参数: {params}")
            raise

    async def executemany_with_pool(
        self,
        query: str,
        args_list: List[Tuple]
    ) -> None:
        """
        批量执行同一条 SQL，利用 asyncpg 原生 executemany
        Args:
            query: 含有占位符的 SQL，例如
                INSERT INTO atri_memory (group_id,user_id,event_time,event,event_vector)
                VALUES ($1,$2,$3,$4,$5)
            args_list: 每条记录对应的参数元组
        """
        conn = self._context_conn.get()
        try:
            await conn.executemany(query, args_list)
        except (UniqueViolationError, ForeignKeyViolationError) as e:
            self.log.error(f"数据库约束冲突: {e}")
            raise
        except Exception as e:
            self.log.error(f"SQL executemany 错误: {e}, 查询: {query}")
            raise
    
    
    def _convert_query_placeholders(self, query: str) -> str:
        """将 %s 占位符转换为 $1, $2 格式"""
        parts = query.split('%s')
        if len(parts) == 1:
            return query
        
        new_parts = []
        for i, part in enumerate(parts):
            new_parts.append(part)
            if i < len(parts) - 1:
                new_parts.append(f"${i+1}")
        
        return ''.join(new_parts)

    async def add_user(self, user_id: int, nickname: str) -> bool:
        """添加用户"""
        await self._execute_with_pool(
            """
            INSERT INTO users (user_id, nickname) 
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET 
                nickname = EXCLUDED.nickname,
                last_updated = CURRENT_TIMESTAMP
            """,
            (user_id, nickname)
        )
        return True
    
    async def add_group(self, group_id: int, group_name: str) -> bool:
        """添加群组"""
        await self._execute_with_pool(
            """
            INSERT INTO user_group (group_id, group_name) 
            VALUES ($1, $2)
            ON CONFLICT (group_id) DO UPDATE SET 
                group_name = EXCLUDED.group_name
            """,
            (group_id, group_name)
        )
        return True
        
    async def add_message(
        self, 
        message_id: int, 
        user_id: int, 
        group_id: int,
        timestamp: int, 
        content: str
    ) -> bool:
        """添加消息"""
        await self._execute_with_pool(
            """INSERT INTO message 
            (message_id, user_id, group_id, time, message_content)
            VALUES ($1, $2, $3, $4, $5)""",
            (message_id, user_id, group_id, timestamp, content)
        )
        return True

    async def execute_transaction(self, queries: List[Tuple[str, Tuple]]) -> bool:
        """执行事务"""
        conn = self.get_connection()
        async with conn.transaction():
            try:
                for query, params in queries:
                    if params:
                        query = self._convert_query_placeholders(query)
                        await conn.execute(query, *params)
                    else:
                        await conn.execute(query)
                return True
            except Exception as e:
                self.log.error(f"事务执行失败: {e}")
                return False
            