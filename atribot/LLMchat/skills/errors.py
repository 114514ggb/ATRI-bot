"""Skill 相关的异常。"""


class SkillError(Exception):
    """所有 skill 相关错误的基异常。"""

    pass


class ParseError(SkillError):
    """当 SKILL.md 解析失败时引发。"""

    pass


class ValidationError(SkillError):
    """当 skill 属性无效时引发。

    Attributes:
        errors: 验证错误消息列表（可能仅包含一条）
    """

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors if errors is not None else [message]