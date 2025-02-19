import aiomysql
from aiomysql import IntegrityError
import asyncio


class AtriDB_Async:
    def __init__(self):
        self.conn = None
        self.cursor = None
        
    @classmethod
    async def create(cls, host, user, password):
        """异步初始化方法"""
        print("初始化数据库连接...")
        self = cls()
        self.conn = await aiomysql.connect(
            host=host,
            user=user,
            password=password,
            db='atri',
            autocommit=True  # 开启自动提交
        )
        print("数据库连接完成!")
        return self
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.cursor = await self.conn.cursor()
        return self
     
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.cursor:
            await self.cursor.close()
            
    async def found_cursor(self):
        """创建游标"""
        if not self.cursor:
            self.cursor = await self.conn.cursor()
        return True
    
    async def close_cursor(self):
        """关闭游标"""
        if self.cursor:
            await self.cursor.close()
            self.cursor = None
        return True

    async def reconnect(self, host, user, password):
        """重新连接数据库"""
        if self.conn and not self.conn.closed:
            await self.conn.close()
            
        self.conn = await aiomysql.connect(
            host=host,
            user=user,
            password=password,
            db='atri',
            autocommit=True  
        )


    async def close(self):
        """手动关闭连接的方法"""
        if self.conn:
            await self.conn.close()
            
    async def add_user(self, user_id, nickname):
        """添加用户"""
        try:
            await self.cursor.execute(
                """
                    INSERT INTO users (user_id, nickname) 
                    VALUES (%s, %s) AS new
                    ON DUPLICATE KEY UPDATE 
                        nickname = new.VALUES(nickname),
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
        await self.cursor.execute(
            "SELECT * FROM users WHERE user_id = %s",
            (user_id,)
        )
        return await self.cursor.fetchone()
    
    async def add_group(self, group_id, group_name):
        """添加群组"""
        try:
            await self.cursor.execute(
                """
                    INSERT INTO user_group (group_id, group_name) 
                    VALUES (%s, %s) AS new
                    ON DUPLICATE KEY UPDATE 
                        group_name = new.VALUES(group_name)
                """,
                (group_id, group_name)
            )
            return True
        except IntegrityError as e:
            print(f"添加群组失败: {e}")
            return False
        
    async def get_group(self, group_id):
        """查询单个群组"""
        await self.cursor.execute(
            "SELECT * FROM user_group WHERE group_id = %s",
            (group_id,)
        )
        return await self.cursor.fetchone()
    
    async def add_message(self, message_id, user_id, group_id, timestamp, content):
        """
        添加消息
        :param timestamp: 支持datetime对象或时间戳（整数）
        """
        try:
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
        
    async def get_messages_by_user(self, user_id, limit=50)-> dict:
        """查询用户最近消息"""
        await self.cursor.execute(
            """SELECT * FROM message 
            WHERE user_id = %s 
            ORDER BY time DESC 
            LIMIT %s""",
            (user_id, limit)
        )
        return await self.cursor.fetchall()
    
    async def get_messages_by_group(self, group_id, limit=50)-> dict:
        """查询群组最近消息"""
        await self.cursor.execute(
            """SELECT * FROM message 
            WHERE group_id = %s 
            ORDER BY time DESC 
            LIMIT %s""",
            (group_id, limit)
        )
        return await self.cursor.fetchall()
    
    async def execute_SQL(self, sql:str, argument:tuple)-> dict:
        """执行SQL语句"""
        await self.cursor.execute(sql, argument)
        
        return await self.cursor.fetchall()
    
if __name__ == "__main__":
    async def main():
        async with await AtriDB_Async.create('localhost', 'root', '180710') as db:
            # await db.add_user(123, 'test')
            print(await db.get_user(123))
    
    asyncio.run(main())