"""Agent Skill 的数据模型。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class SkillProperties:
    """从 skill 的 SKILL.md 前置元数据解析出的属性。

    Attributes:
        name: 使用短横线连接的小写 skill 名称（必填）
        description: 该 skill 的功能以及模型应在何时使用它（必填）
        path:  该 skill 文件夹所在路径（必填）
        license: 该 skill 的许可证（可选）
        compatibility: 该 skill 的兼容性信息（可选）
        allowed_tools: 该 skill 所需的工具模式（可选，实验性）
        metadata: 客户端特定属性的键值对（默认为空字典；为空时从 to_dict() 输出中省略）
    """

    name: str
    """使用短横线连接的小写 skill 名称"""
    description: str
    """该 skill 的功能以及模型应在何时使用它"""
    path: Path
    """文件夹所在路径"""
    license: Optional[str] = None
    """该 skill 的许可证"""
    compatibility: Optional[str] = None
    """该 skill 的兼容性信息"""
    allowed_tools: Optional[str] = None
    """该 skill 所需的工具模式"""
    metadata: dict[str, str] = field(default_factory=dict)
    """客户端特定属性的键值对"""

    def to_dict(self) -> dict:
        """转换为字典，排除 None 值。"""
        result = {"name": self.name, "description": self.description}
        if self.license is not None:
            result["license"] = self.license
        if self.compatibility is not None:
            result["compatibility"] = self.compatibility
        if self.allowed_tools is not None:
            result["allowed-tools"] = self.allowed_tools
        if self.metadata:
            result["metadata"] = self.metadata
        return result