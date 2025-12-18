from atribot.core.db.atri_async_postgresql import atriAsyncPostgreSQL
from atribot.core.service_container import container
from typing import Dict, Any
from logging import Logger
import json




class UserSystem:
    """
    用户信息系统类，负责管理和存储用户的基本信息
    包括获取基础用户信息结构、从数据库获取和保存用户信息等功能
    """
    
    
    def __init__(self):
        self.logger:Logger = container.get("log")
        self.database:atriAsyncPostgreSQL = container.get("database")
        self.base_json_data = self.get_base_user_json()
        """参考的基础用户信息结构"""

    
    @staticmethod
    def get_base_user_json() -> dict[str, Any]:
        """
        返回基础用户JSON结构，用于给AI提供用户基本信息概况
        
        Returns:
            dict: 包含用户信息的字典，结构如下：
                - appellation: list[str] - 用户的称呼列表
                - relation: str - 用户与AI的关系描述
                - personality: str - 用户性格简要描述
                - recent_topics: str - 最近讨论的话题摘要
                - evaluation: str - 对用户的评价或观察
                - prefs: dict - 偏好设置
                    - style: str - 偏好交流风格
                    - avoid: str - 需要避免的内容
        """
        return {
            "appellation": ["用户常用称呼1", "用户常用称呼2"],
            "relation": "例如：朋友/助手/导师/同学等关系描述",
            "personality": "简要描述性格特点，如：外向幽默、内敛谨慎等",
            "recent_topics": "最近几次对话的主要话题，用自然语言描述。",
            "evaluation": "对用户的观察和评价",
            "prefs": {
                "style": "偏好的交流风格",
                "avoid": "需要避免的话题或表达方式"
            }
        }
    
    
    def _safe_truncate(self, text: str, max_bytes: int) -> str:
        """
        按字节数限制截断字符串，保留末尾部分。
        处理中英文混合情况，防止半个字符乱码。
        """
        if not isinstance(text, str):
            return text
            
        encoded = text.encode('utf-8')
        
        if len(encoded) <= max_bytes:
            return text

        truncated_bytes = encoded[-max_bytes:]
        
        return truncated_bytes.decode('utf-8', errors='ignore')
    
    def _recursive_update(self, base: dict, update: dict, max_bytes: int = 900) -> bool:
        """
        递归更新字典，只更新base中已存在的键值对。
        
        该方法遵循以下规则：
        1. 只更新base字典中已存在的键，忽略update中新增的键
        2. 只有新旧值的类型一致时才进行更新，防止类型错误
        3. 如果值是字典类型，则递归进入内部进行更新
        4. 只有当值确实发生变化时才视为更新
        5. 则保留最新的 max_bytes 大小的内容,注:一个中文字符3byte英文1byte
        
        Args:
            base (dict): 基础字典，将被更新的目标字典
            update (dict): 包含更新数据的字典
            
        Returns:
            bool: 
                - True: 至少有一个值被成功更新
                - False: 没有发生任何更改
                
        Examples:
            >>> base = {"a": 1, "b": {"c": 2}, "d": "hello"}
            >>> update = {"a": 10, "b": {"c": 20}, "e": 999}
            >>> _recursive_update(base, update)
            True
            >>> print(base)  # base变为 {"a": 10, "b": {"c": 20}, "d": "hello"}
            
        Note:
            - 键"e"被忽略，因为base中不存在
            - 嵌套字典"b"被递归更新
        """
        has_changed = False

        for key, new_val in update.items():
            if key not in base:
                continue

            current_val = base[key]

            if isinstance(current_val, dict) and isinstance(new_val, dict):
                if self._recursive_update(current_val, new_val):
                    has_changed = True
            
            elif isinstance(current_val, type(new_val)):
                final_val = new_val
                
                if isinstance(new_val, str):
                    final_val = self._safe_truncate(new_val, max_bytes)
                    
                if current_val != final_val:
                    base[key] = final_val
                    has_changed = True

        return has_changed
    
    async def update_user_info(self, user_id: int, current_info: Dict[str, Any], new_info_json: Dict[str, Any]) -> bool:
        """
        更新用户信息，合并新信息到现有信息中。
        
        该方法执行以下步骤：
        1. 从数据库获取当前用户信息
        2. 使用递归更新方法合并新信息到现有信息
        3. 如果有任何更改，则保存更新后的信息回数据库
        
        Args:
            user_id (int): 要更新的用户ID
            current_info (Dict[str, Any]): 当前用户信息字典
            new_info_json (Dict[str, Any]): 包含新用户信息的字典
            
        Returns:
            bool: 
                - True: 用户信息有更新并已保存
                - False: 用户信息无变化，未进行保存
                
        Raises:
            DatabaseError: 数据库操作失败时抛出
            ValueError: 参数无效时抛出
        """
        if self._recursive_update(current_info, new_info_json):
            await self.save_user_info(user_id, current_info)
            return True
        
        return False
    
    async def get_user_info(self,user_id:int) -> Dict[str, Any]:
        """
        根据用户ID从数据库获取用户信息。
        通过查询user_info表，检索指定用户的信息记录。
        如果用户不存在，将返回基础用户信息结构的副本。
        
        Args:
            user_id (int): 要查询的用户ID
            
        Returns:
            Dict[str, Any]: 包含用户信息的字典，字段来自数据库的info列
            如果用户不存在，返回空
            
        Raises:
            DatabaseError: 数据库操作失败时抛出
            ValueError: 参数无效时抛出
        """
        sql = """
        SELECT 
            info
        FROM user_info
        WHERE user_id = $1
        """
        async with self.database as db:
            if data := await db.execute_with_pool(
                    query = sql,
                    params = (user_id,),
                    fetch_type = "one"
                ):
                return json.loads(data[0])
        return self.base_json_data.copy()
            
                        
    async def save_user_info(self, user_id: int, info: Dict[str, Any]) -> None:
        """
        保存或更新用户信息到数据库。
        
        使用PostgreSQL的UPSERT操作（ON CONFLICT）：
        - 如果user_id不存在，则插入新记录
        - 如果user_id已存在，则更新现有记录的info字段和last_updated时间戳
        
        Args:
            user_id (int): 要保存的用户ID
            info (Dict[str, Any]): 要保存的用户信息字典
            
        Returns:
            None: 该函数不返回任何值
            
        Raises:
            DatabaseError: 数据库操作失败时抛出
            ValueError: 参数无效时抛出
            
        Note:
            - 使用CURRENT_TIMESTAMP自动设置更新时间
            - info字典将被序列化后存储到数据库
            - 使用参数化查询防止SQL注入
        """
        sql = """
        INSERT INTO user_info (user_id, info)
        VALUES ($1, $2)
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            info = EXCLUDED.info
        """
        
        async with self.database as db:
            await db.execute_with_pool(
                query = sql,
                params = (user_id, json.dumps(info))
            )