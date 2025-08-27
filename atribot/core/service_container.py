from typing import Dict, Any


class DIContainer:
    _instance = None
    _services: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, name: str, service: Any):
        """注册服务"""
        self._services[name] = service
    
    def get(self, name: str) -> Any:
        """获取服务"""
        if name not in self._services:
            raise ValueError(f"Service {name} not found")
        return self._services[name]
    
    def exists(self, name: str) -> bool:
        """检查服务是否存在"""
        return name in self._services
    
    
    
container = DIContainer()