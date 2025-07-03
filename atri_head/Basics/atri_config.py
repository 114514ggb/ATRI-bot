import json



# class ConfigObject:
#     """
#     将字典转换为点操作符访问的对象
#     支持嵌套字典和列表的递归转换
#     """
#     def __init__(self, data):
#         if isinstance(data, dict):
#             for key, value in data.items():
#                 if isinstance(value, (dict, list)):
#                     setattr(self, key, ConfigObject(value))
#                 else:
#                     setattr(self, key, value)
#         elif isinstance(data, list):
#             for index, item in enumerate(data):
#                 if isinstance(item, (dict, list)):
#                     data[index] = ConfigObject(item)
#             self.__dict__ = data
#         else:
#             self.__dict__ = data

#     def __repr__(self):
#         return str(self.__dict__)
    
#     def __iter__(self):
#         """在包装列表/字典时使ConfigObject可迭代"""
#         if isinstance(self.__dict__, list):
#             return iter(self.__dict__)
#         elif isinstance(self.__dict__, dict):
#             return ((k, v) for k, v in self.__dict__.items())
#         else:
#             raise TypeError(f"{type(self).__name__} 对象不可迭代")

class ConfigObject(dict):
    """
    将字典转换为点运算符访问的对象
    继承自 dict，支持字典的所有操作
    只递归处理嵌套字典，不处理列表
    """
    def __init__(self, data=None):
        super().__init__()
        if data:
            for key, value in data.items():
                self[key] = ConfigObject(value) if isinstance(value, dict) else value

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"配置项 '{name}' 不存在")

    def __setattr__(self, name, value):
        self[name] = ConfigObject(value) if isinstance(value, dict) else value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            raise AttributeError(f"配置项 '{name}' 不存在")


class ConfigLoader:
    """
    加载和解析JSON配置文件
    支持点操作符访问配置项
    """
    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        self._config = ConfigObject(config_data)
        
    def __getattr__(self, name):
        """通过点操作符访问配置项"""
        if hasattr(self._config, name):
            return getattr(self._config, name)
        raise AttributeError(f"配置项 '{name}' 不存在")

    @property
    def all_config(self):
        """获取整个配置对象"""
        return self._config
    
class atri_config(ConfigLoader):
    """提供项目的配置参数"""
    def __init__(self):
        super().__init__("assets/config.json")
        
        
if __name__ == "__main__":
    Config = atri_config()
    print(Config.all_config)
    print(Config.network.connection_type)
