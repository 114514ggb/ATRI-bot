import json

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
    print(type(Config.group_white_list))
