import sqlite3
import re

class Permissions_management():
    root = [2631018780] #超级管理员 3
    administrator = [] #管理员 2 
    tourist = []  #游客 1
    blacklist = [] #黑名单 0

    def __init__(self):
        pass

    def administrator_add(self,user_id,people):
        """添加管理员:user_id参数要成为管理员的对象,people参数是请求这条命令的人"""
        if  people in self.root and user_id not in self.administrator+self.root+self.blacklist:
            if self.isQQ(user_id):
                self.administrator.append(user_id)
                return "添加成功"
            else:
                raise Exception("无法添加,不是合法的QQ号")
        else:
             raise Exception("无法添加")

    def administrator_delete(self,user_id,people):
        """删除管理员:user_id参数要删除的管理员,people参数是请求这条命令的人"""
        if  people in self.root and user_id in self.administrator:
                self.administrator.remove(user_id)
                return "删除成功"
        else:
            raise Exception("无法删除")
    
    def blacklist_add(self,user_id,people):
        """添加黑名单:user_id参数要加入黑名单的对象,people参数是请求这条命令的人"""
        if  people in self.root+self.administrator and user_id not in self.administrator+self.root+self.blacklist:
            if self.isQQ(user_id):
                self.blacklist.append(user_id)
                return "添加成功"
            else:
                raise Exception("无法添加,不是合法的QQ号")
        else:
             raise Exception("无法添加")
        
    def blacklist_delete(self,user_id,people):
        """删除黑名单:user_id参数要删除的对象,people参数是请求这条命令的人"""
        if  people in self.root+self.administrator and user_id not in self.root+self.administrator:
                self.blacklist.remove(user_id)
                return "删除成功"
        else:
             raise Exception("无法删除")

    def blacklist_intercept(self,people):
        """是否放行,不在黑名单的话返回True"""
        if people in self.blacklist:
            return False
        else:
            return True 
    
    def permissions_check(self):
        """查看现有管理权限"""
        return self.root,self.administrator

    def my_permissions(self, people):
        """查看自己的权限"""
        if people in self.root:
            return "root"
        elif people in self.administrator:
            return "administrator"
        elif people in self.blacklist:
            return "blacklist"
        else:
            return "tourist"

    def permissions(self, people, permission_level):
        """判断是否有权限"""
        if people in self.root:
            return True
        elif permission_level <= 2 and people in self.administrator:
            return True
        elif permission_level <= 1 and people not in self.blacklist:
            return True
        elif permission_level == 0:
            return True
        else:
            Exception("你没有这个权限")

    def isQQ(self,qq):
        """判断是否是qq号"""
        qq_expression = r'^[1-9][0-9]{4,14}$'
        if re.match(qq_expression,str(qq)):
            return True
        else:
            return False
        
    def synchronous_database(self,qq_id,permissions,add = True):
        """把添加或删除同步到数据库"""
        try:
            insert_sql = """
            INSERT INTO permissions (qq_id, permissions)
            VALUES (?, ?);
            """

            delete_sql = """
            DELETE FROM permissions
            WHERE qq_id = ?;
            """

            conn = sqlite3.connect("assets/ATRI.db")
            cursor  = conn.cursor()
            
            if add:
                cursor.execute(insert_sql,[qq_id,permissions])
            else:
                cursor.execute(delete_sql,[qq_id])

            conn.commit()
            cursor.close()
            conn.close()
        
            return "同步成功"
        except Exception as e:
            Exception(f"同步到数据库失败:{e}")
    
    def syncing_locally(self):
        """把数据库同步到本地"""
        try:
            conn = sqlite3.connect('assets/ATRI.db')
            cursor  = conn.cursor()

            cursor.execute("SELECT * FROM permissions")
            rows = cursor.fetchall()

            for row in rows:
                if row[1] == "管理员":
                    self.administrator.append(row[0])
                elif row[1] == "黑名单":
                    self.blacklist.append(row[0])

            cursor.close()
            conn.close()

            return "同步成功"
        except Exception as e:
            Exception(f"数据库同步到本地失败:{e}")
    