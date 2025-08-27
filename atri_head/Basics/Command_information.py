from dataclasses import dataclass,field
from typing import Callable, List

@dataclass
class Command:
    """指令元数据容器"""
    name: str                               # 基础指令名 
    aliases: List[str]                      # 别名列表
    handler: Callable                       # 处理函数
    description: str = "默认描述"            # 指令描述
    parameter: List[List[int]] = field(default_factory=lambda: [[0, 0], [0, 0]])    # 获取参数数量范围，列表里的是取值的数量范围    
    authority_level: int = 1               # 需要的权限等级
    cooldown: int = 0                       # 冷却时间（秒）