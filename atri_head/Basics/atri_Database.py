import pymysql

class AtriDB:
    """数据库操作类"""
    def __init__(self, host, user, password):
        print("Connecting to database...\n")
        try:
            self.conn = pymysql.connect(
                host=host,
                user=user,
                password=password,
                database='atri',
                cursorclass=pymysql.cursors.DictCursor
            )
            print("Connected to database.\n")
        except pymysql.err.OperationalError as e:
            print(f"连接数据库失败: {e}\n")
    
    def __enter__(self):
        self.cursor = self.conn.cursor()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.commit()
            self.cursor.close()
            self.conn.close()
    
    def add_user(self, user_id, nickname):
        """添加用户"""
        try:
            self.cursor.execute(
                "INSERT INTO users (user_id, nickname) VALUES (%s, %s)",
                (user_id, nickname)
            )
            return True
        except pymysql.err.IntegrityError as e:
            print(f"添加用户失败: {e}")
            return False
    
    def get_user(self, user_id):
        """查询单个用户"""
        self.cursor.execute(
            "SELECT * FROM users WHERE user_id = %s",
            (user_id,)
        )
        return self.cursor.fetchone()
    
    def add_group(self, group_id, group_name):
        """添加群组"""
        try:
            self.cursor.execute(
                "INSERT INTO user_group VALUES (%s, %s)",
                (group_id, group_name)
            )
            return True
        except pymysql.err.IntegrityError as e:
            print(f"添加群组失败: {e}")
            return False
    
    def get_group(self, group_id):
        """查询单个群组"""
        self.cursor.execute(
            "SELECT * FROM user_group WHERE group_id = %s",
            (group_id,)
        )
        return self.cursor.fetchone()
    
    def add_message(self, message_id, user_id, group_id, timestamp, content):
        """
        添加消息
        :param timestamp: 支持datetime对象或时间戳（整数）
        """
        try:
            self.cursor.execute(
                """INSERT INTO message 
                (message_id, user_id, group_id, time, message_content)
                VALUES (%s, %s, %s, %s, %s)""",
                (message_id, user_id, group_id, timestamp, content)
            )
            return True
        except pymysql.err.IntegrityError as e:
            print(f"添加消息失败，请检查外键约束: {e}")
            return False
    
    def get_messages_by_user(self, user_id, limit=50):
        """查询用户最近消息"""
        self.cursor.execute(
            """SELECT * FROM message 
            WHERE user_id = %s 
            ORDER BY time DESC 
            LIMIT %s""",
            (user_id, limit)
        )
        return self.cursor.fetchall()
    
    def get_messages_by_group(self, group_id, limit=50):
        """查询群组最近消息"""
        self.cursor.execute(
            """SELECT * FROM message 
            WHERE group_id = %s 
            ORDER BY time DESC 
            LIMIT %s""",
            (group_id, limit)
        )
        return self.cursor.fetchall()