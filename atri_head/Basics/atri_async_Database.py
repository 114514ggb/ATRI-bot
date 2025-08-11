import aiomysql
from aiomysql import IntegrityError, Pool
from contextvars import ContextVar
from threading import Lock
import asyncio


class AtriDB_Async:
    """异步数据库操作类(连接池)"""
    _pool: Pool = None
    _lock = asyncio.Lock()
    _thread_lock = Lock()
    _close_lock = asyncio.Lock()
    _conn_var: ContextVar[aiomysql.Connection] = ContextVar("conn")
    _cursor_var: ContextVar[aiomysql.Cursor] = ContextVar("cursor")

        
    @classmethod
    async def create(cls, host, user, password, pool_minsize=2, pool_maxsize=8):
        """初始化连接池"""
        # with cls._thread_lock:
        if cls._pool is None:
            async with cls._lock:
                if cls._pool is None:
                    print("初始化数据库连接池...")
                    cls._pool = await aiomysql.create_pool(
                        host=host,
                        user=user,
                        password=password,
                        db='atri',
                        charset='utf8mb4',
                        autocommit=True,
                        minsize=pool_minsize,
                        maxsize=pool_maxsize,
                        pool_recycle=300  # 重连
                    )
                    print(f"连接池已创建（大小：{pool_minsize}-{pool_maxsize}）")
        return cls()
    
    @classmethod
    async def close_pool(cls):
        """关闭整个连接池"""
        async with cls._close_lock:
            if cls._pool:
                print("关闭数据库连接池...")
                cls._pool.close()
                await cls._pool.wait_closed()
                cls._pool = None
                print("连接池已完全关闭")
                
    async def __aenter__(self):
        """从连接池获取连接并创建游标"""
        self.conn = await self._pool.acquire()
        self.cursor = await self.conn.cursor()
        return self
     
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """归还连接到池中"""
        try:
            await self.cursor.close()
        except LookupError:
            pass #如果找不到则忽略
        finally:
            try:
                self._pool.release(self.conn)
            except LookupError:
                pass 
        self.conn = None
        self.cursor = None
        
    async def error_close(self):
        """立即触发连接释放"""
        await self.__aexit__(None, None, None)

    async def get_connection(self):
        """显式获取连接（用于需要长期保持连接的场景）"""
        if not self.conn:
            self.conn = await self._pool.acquire()
        return self.conn

    async def release_connection(self):
        """显式释放连接"""
        if self.conn:
            self._pool.release(self.conn)
            self.conn = None

    async def reconnect_pool(self,host, user, password, pool_minsize=2, pool_maxsize=8):
        """重建整个连接池"""
        async with self._lock:
            if self._pool:
                self._pool.close()
                await self._pool.wait_closed()
            self._pool = await aiomysql.create_pool(
                host=host,  
                user=user,
                password=password,
                db="atri",
                autocommit=True,
                minsize=pool_minsize,
                maxsize=pool_maxsize
            )

        
    async def _get_current_conn(self) -> None:
        """获取当前协程的数据库conn连接（自动重连）"""
        try:
            if self.conn.closed:
                #刷新conn
                self.conn.close()
                self.conn = await self._pool.acquire()

        except LookupError:
            # 未通过上下文管理器时自动获取
            self.conn = await self._pool.acquire()

                
    async def _auto_connect(self):
        """确保操作前有可用连接"""
        try:
            if self.cursor.closed:
                self.cursor = await self.conn.cursor()
        except LookupError:
            await self._get_current_conn()
            self.cursor = await self.conn.cursor()

            
    async def add_user(self, user_id, nickname):
        """添加用户"""
        try:
            await self._auto_connect()
            await self.cursor.execute(
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
            print(f"添加用户失败: {e}")
            return False
        
    async def get_user(self, user_id:int)->tuple:
        """查询单个用户"""
        await self._auto_connect()
        await self.cursor.execute(
            "SELECT * FROM users WHERE user_id = %s",
            (user_id,)
        )
        return await self.cursor.fetchone()
    
    async def add_group(self, group_id, group_name):
        """添加群组"""
        try:
            await self._auto_connect()
            await self.cursor.execute(
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
            print(f"添加群组失败: {e}")
            return False
        
    async def get_group(self, group_id):
        """查询单个群组"""
        await self._auto_connect()
        await self.cursor.execute(
            "SELECT * FROM user_group WHERE group_id = %s",
            (group_id,)
        )
        return await self.cursor.fetchone()

    async def get_all_group(self)->tuple:
        """查询所有群组"""
        await self._auto_connect()
        await self.cursor.execute(
            "SELECT * FROM user_group",
        )
        return await self.cursor.fetchall()
    
    async def add_message(self, message_id:int, user_id:int, group_id:int, timestamp:int, content:str)->bool:
        """
        添加消息
        :param timestamp: 支持datetime对象或时间戳（整数）
        """
        try:
            await self._auto_connect()
            await self.cursor.execute(
                """INSERT INTO message 
                (message_id, user_id, group_id, time, message_content)
                VALUES (%s, %s, %s, %s, %s)""",
                (message_id, user_id, group_id, timestamp, content)
            )
            return True
        except IntegrityError as e:
            print(f"添加消息失败，请检查外键约束: {e}")
            return False
        
    async def get_messages_by_user(self, user_id, limit=50)-> tuple:
        """查询用户最近消息"""
        await self._auto_connect()
        await self.cursor.execute(
            """SELECT * FROM message 
            WHERE user_id = %s 
            ORDER BY time DESC 
            LIMIT %s""",
            (user_id, limit)
        )
        return await self.cursor.fetchall()
    
    async def get_messages_by_group(self, group_id, limit=50)-> tuple:
        """查询群组最近消息"""
        await self._auto_connect()
        await self.cursor.execute(
            """SELECT * FROM message 
            WHERE group_id = %s 
            ORDER BY time DESC 
            LIMIT %s""",
            (group_id, limit)
        )
        return await self.cursor.fetchall()
    
    async def execute_SQL(self, sql:str, argument:tuple)-> tuple:
        """执行SQL语句"""
        await self._auto_connect()
        await self.cursor.execute(sql, argument)
        
        return await self.cursor.fetchall()
    
    @property
    def conn(self):
        """获取数据库连接"""
        return self._conn_var.get()
    
    @conn.setter
    def conn(self, value):
        """设置数据库连接"""
        self._conn_var.set(value)
        
    @property
    def cursor(self):
        """获取数据库游标"""
        return self._cursor_var.get()

    @cursor.setter
    def cursor(self, value):
        """设置数据库游标"""
        self._cursor_var.set(value)
    
if __name__ == "__main__":
    async def main():
        async with await AtriDB_Async.create('localhost', 'root', '180710') as db:
            # await db.add_user(123, 'test')
            print(await db.get_user(2631018780))
    
    asyncio.run(main())
    
"""
SELECT *
FROM meassage
WHERE group_id = group_id_value
ORDER BY time DESC
LIMIT 20;
"""