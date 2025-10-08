from atribot.core.service_container import container
from atribot.core.db.async_db_basics import AsyncDatabaseBase
import logging
import sqlite3
import re

class permissions_management:

    PERM_LEVEL_ROOT = 3
    PERM_LEVEL_ADMIN = 2
    PERM_LEVEL_TOURIST = 1
    PERM_LEVEL_BLACKLIST = 0

    ROLE_ROOT = "root"
    ROLE_ADMIN = "administrator"
    ROLE_TOURIST = "tourist"
    ROLE_BLACKLIST = "blacklist"

    def __init__(self):
        self.db: AsyncDatabaseBase = container.get("database")
        self.logging: logging.Logger = container.get("log")
        
        # 初始超级管理员ID
        self.root = {2631018780} 
        self.administrator = set()
        self.blacklist = set()

    def _get_user_permission_level(self, user_id):
        """内部辅助方法：获取用户的权限等级
        
        Args:
            user_id (int|str): 要查询的用户ID
            
        Returns:
            int: 用户权限等级，对应PERM_LEVEL_*常量"""
        if user_id in self.root:
            return self.PERM_LEVEL_ROOT
        if user_id in self.administrator:
            return self.PERM_LEVEL_ADMIN
        if user_id in self.blacklist:
            return self.PERM_LEVEL_BLACKLIST
        return self.PERM_LEVEL_TOURIST

    def _get_user_role(self, user_id):
        """获取用户的角色名称
        
        Args:
            user_id (int|str): 要查询的用户ID
            
        Returns:
            str: 用户角色名称，对应ROLE_*常量"""
        level = self._get_user_permission_level(user_id)
        if level == self.PERM_LEVEL_ROOT:
            return self.ROLE_ROOT
        if level == self.PERM_LEVEL_ADMIN:
            return self.ROLE_ADMIN
        if level == self.PERM_LEVEL_BLACKLIST:
            return self.ROLE_BLACKLIST
        return self.ROLE_TOURIST

    def _modify_permission(self, target_user_id, operator_id, target_list, required_level, action='add'):
        """抽象通用方法来处理权限变更
        
        Args:
            target_user_id (int|str): 目标用户ID
            operator_id (int|str): 操作者用户ID
            target_list (set): 要修改的目标权限集合
            required_level (int): 执行操作所需的最低权限等级
            action (str, optional): 操作类型，'add'或'remove'。默认为'add'
            
        Raises:
            PermissionError: 当操作者权限不足时
            ValueError: 当用户ID不合法或操作无效时
        """
        operator_level = self._get_user_permission_level(operator_id)
        
        if operator_level < required_level:
            raise PermissionError("操作失败：您的权限不足。")

        if not self.is_qq(target_user_id):
            raise ValueError(f"无法操作：{target_user_id} 不是一个合法的QQ号。")
            
        target_role = self._get_user_role(target_user_id)
        
        if action == 'add':
            if target_role in [self.ROLE_ROOT, self.ROLE_ADMIN]:
                 raise ValueError(f"无法添加：用户 {target_user_id} 已经是管理员或更高权限。")
            if target_user_id in target_list:
                raise ValueError(f"无法添加：用户 {target_user_id} 已在该列表中。")
            
            target_list.add(target_user_id)
            self.logging.info(f"操作成功：用户 {target_user_id} 已被 {operator_id} 添加到目标列表。")

        elif action == 'remove':
            if target_user_id not in target_list:
                raise ValueError(f"无法删除：用户 {target_user_id} 不在该列表中。")
                
            target_list.remove(target_user_id)
            self.logging.info(f"操作成功：用户 {target_user_id} 已被 {operator_id} 从目标列表移除。")
        else:
            raise ValueError("无效的操作类型。")

    def add_administrator(self, user_id, operator_id):
        """添加管理员
        
        Args:
            user_id (int|str): 要设为管理员的用户ID
            operator_id (int|str): 执行此操作的用户ID
            
        Raises:
            PermissionError: 当操作者权限不足时
            ValueError: 当用户ID不合法或用户已是管理员时
        """
        self._modify_permission(user_id, operator_id, self.administrator, self.PERM_LEVEL_ROOT, 'add')

    def delete_administrator(self, user_id, operator_id):
        """删除管理员
        
        Args:
            user_id (int|str): 要移除的管理员ID
            operator_id (int|str): 执行此操作的用户ID
            
        Raises:
            PermissionError: 当操作者权限不足时
            ValueError: 当用户ID不合法或用户不是管理员时
        """
        self._modify_permission(user_id, operator_id, self.administrator, self.PERM_LEVEL_ROOT, 'remove')

    def add_to_blacklist(self, user_id, operator_id):
        """添加用户到黑名单
        
        Args:
            user_id (int|str): 要加入黑名单的用户ID
            operator_id (int|str): 执行此操作的用户ID
            
        Raises:
            PermissionError: 当操作者权限不足时
            ValueError: 当用户ID不合法或用户已在黑名单时
        :param operator_id: 执行此操作的用户ID
        """
        self._modify_permission(user_id, operator_id, self.blacklist, self.PERM_LEVEL_ADMIN, 'add')

    def remove_from_blacklist(self, user_id, operator_id):
        """从黑名单中移除用户
        
        Args:
            user_id (int|str): 要移除的黑名单用户ID
            operator_id (int|str): 执行此操作的用户ID
            
        Raises:
            PermissionError: 当操作者权限不足或尝试移除管理员时
            ValueError: 当用户ID不合法或用户不在黑名单时
        """

        if self._get_user_permission_level(user_id) >= self.PERM_LEVEL_ADMIN:
            raise PermissionError("无法将管理员或更高权限者从黑名单移除（他们本身也不应在黑名单中）")
        self._modify_permission(user_id, operator_id, self.blacklist, self.PERM_LEVEL_ADMIN, 'remove')

    def check_access(self, user_id):
        """检查用户是否被拦截。不在黑名单中则返回True，表示允许访问
        
        Args:
            user_id (int|str): 要检查的用户ID
            
        Returns:
            bool: True表示允许访问，False表示被拦截
        """
        return self._get_user_permission_level(user_id) > self.PERM_LEVEL_BLACKLIST

    def view_permissions(self):
        """查看现有的权限划分情况
        
        Returns:
            tuple: 包含两个集合的元组 (root_set, admin_set)
        """
        self.logging.info(f"Root: {self.root}, Administrator: {self.administrator}")
        return self.root, self.administrator

    def get_my_permission(self, user_id):
        """查看自己的权限角色
        
        Args:
            user_id (int|str): 要查询的用户ID
            
        Returns:
            str: 用户角色名称，对应ROLE_*常量
        """
        role = self._get_user_role(user_id)
        return role

    def has_permission(self, user_id, required_level):
        """判断用户是否有执行某个操作所需的权限
        
        Args:
            user_id (int|str): 要检查的用户ID
            required_level (int): 执行操作所需的最低权限等级
            
        Returns:
            bool: True表示权限足够
            
        Raises:
            PermissionError: 当用户权限不足时
        """
        user_level = self._get_user_permission_level(user_id)
        if user_level >= required_level:
            return True
        else:
            raise PermissionError(f"权限不足：需要等级 {required_level}，但用户 {user_id} 只有等级 {user_level}。")

    def is_qq(self, qq):
        """判断是否是合法的QQ号
        
        Args:
            qq (int|str): 要检查的QQ号
            
        Returns:
            bool: True表示是合法QQ号，False表示不合法"""
        return bool(re.fullmatch(r'[1-9]\d{4,14}', str(qq)))

    def synchronous_database(self,qq_id,permissions,add = True):
        """把添加或删除同步到数据库"""
        try:
            insert_sql = "INSERT INTO permissions (qq_id, permissions) VALUES (?, ?);"
            delete_sql = "DELETE FROM permissions WHERE qq_id = ?;"

            conn = sqlite3.connect("assets/ATRI.db")
            cursor  = conn.cursor()
            
            if add:
                cursor.execute(insert_sql,[qq_id,permissions])
            else:
                cursor.execute(delete_sql,[qq_id])

            conn.commit()
        except Exception as e:

            self.logging.error(f"同步到数据库失败: {e}", exc_info=True)
            raise IOError(f"同步到数据库失败:{e}")
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()
        self.logging.info(f"数据库同步成功: QQ {qq_id}。")
    
    def syncing_locally(self):
        """把数据库同步到本地"""
        try:
            conn = sqlite3.connect('assets/ATRI.db')
            cursor  = conn.cursor()

            cursor.execute("SELECT * FROM permissions")
            rows = cursor.fetchall()

            for qq_id, permission in rows:
                if permission == "管理员":
                    self.administrator.add(qq_id)
                elif permission == "黑名单":
                    self.blacklist.add(qq_id)

            self.logging.info("从数据库同步权限到本地成功。")
        except Exception as e:
            self.logging.error(f"数据库同步到本地失败: {e}", exc_info=True)
            raise IOError(f"数据库同步到本地失败:{e}")
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()
    