from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
from atribot.LLMchat.model_api.model_api_basics import model_api_basics
from dataclasses import dataclass
from typing import Dict
import json


@dataclass
class ai_api_connection:
    """
    用于描述对一个供应商的连接
    """
    name:str
    """连接供应商的名称"""
    model_list:list[Dict[str,str|bool]] = None
    """支持的模型信息list,里面的格式应该是{"name":"","visual_sense":False}"""
    base_url:str = ""
    """供应商api地址"""
    api_key:str = ""
    """验证token"""
    connection_object:model_api_basics|object = None
    """用于连接的实例"""
    model_parameter:dict = None
    """模型设置默认的参数"""

    def __post_init__(self):
        if self.model_list is None:
            self.model_list = []
        if self.connection_object is None:
            if self.base_url and self.api_key:
                self.connection_object = universal_ai_api(
                    base_url=self.base_url,
                    api_key=self.api_key
                )
            else:
                raise ValueError("api缺少初始化的值!")
        if self.model_parameter is not None:
            self.connection_object.update_parameters(self.model_parameter)
    
class ai_connection_manager:
    """ai供应商的api连接管理类"""
    
    def __init__(self):
        self.connections:Dict[str,ai_api_connection] = {}
        """管理维护的供应商字典"""
    
    async def initialize_connections(self, path: str) -> None:
        """读取文件然后初始化连接

        Args:
            path (str): 参数文件路径
        """
        print("初始化供应商连接")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config_data:dict = json.load(f)
            
            for api_config in config_data.get("api", []):
                api_config:dict
                try:
                    connection_object = await universal_ai_api.create(
                        base_url=api_config["base_url"],
                        api_key=api_config["api_key"]
                    )
                    
                    connection = ai_api_connection(
                        name=api_config["name"],
                        model_list=api_config.get("models", []),
                        model_parameter=api_config.get("model_parameter", {}),
                        connection_object = connection_object
                    )
                    
                    self.connections[api_config["name"]] = connection
                                        
                except (ValueError, TypeError) as e:
                    print(f"初始化 {api_config.get('name', '未知API')} 连接失败: {e}")
                    
            print("供应商连接已完成！\n")
                
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"初始化连接失败: {e}")
        

    def add_connection(self, **config) -> None:
        """添加一个供应商连接

        Args:
            config: 初始化ai_api_connection需要参数,必须要有name和connection_object
        """
        try:
            connection = ai_api_connection(
                name=config["name"],
                base_url=config.get("base_url", ""),
                api_key=config.get("api_key", ""),
                model_list=config.get("model_list", []),
                connection_object=config["connection_object"],
                model_parameter=config.get("model_parameter", None)
            )
            
            self.connections[config["name"]] = connection
            
        except KeyError as e:
            print(f"添加供应商失败: 缺少必要参数 {e}")

    async def del_connection(self, name: str) -> bool:
        """删除一个供应商连接

        Args:
            name (str): 供应商名称

        Returns:
            bool: 是否成功删除
        """
        if name in self.connections:
            await self.connections[name].connection_object.aclose()
            del self.connections[name]
            return True
        return False
    
    async def close(self):
        """关闭所有连接"""
        for _, conn in self.connections.items:
            conn:ai_api_connection
            await conn.connection_object.aclose()
            
    def get_filtration_connection(
        self,
        supplier_name: str = "",
        model_name: str = ""
    ) -> list[ai_api_connection]:
        """返回筛选的供应商,可根据model_name或supplier_name来筛选

        Args:
            supplier_name (str, optional): 供应商的名称. Defaults to "".
            model_name (str, optional): 模型的名称. Defaults to "".

        Returns:
            list[universal_ai_api]: 返回包含供应商连接的list，没有返回空list
        """
        if supplier_name:
            return [self.connections[supplier_name]]
        
        result = []
        
        for name, conn in self.connections.items():
            conn:ai_api_connection
            if supplier_name and name != supplier_name:
                continue
                
            if model_name:
                model_exists = any(
                    model["name"] == model_name 
                    for model in conn.model_list
                )
                if not model_exists:
                    continue
                    
            if conn.connection_object:
                result.append(conn.connection_object)
                
        return result
