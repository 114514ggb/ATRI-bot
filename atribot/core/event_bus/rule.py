import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from atribot.core.type.bot_types import Message


class Rule(ABC):
    """规则抽象基类

    Usage:
        class MyRule(Rule):
            rule_type: ClassVar[str] = "custom"

            async def match(self, msg: Message) -> bool:
                return ...
    """

    rule_type: ClassVar[str] = "base"
    """规则类型标识，供 EventBus 两级索引用"""

    @abstractmethod
    async def match(self, msg: Message) -> bool:
        """判断消息是否满足此规则

        Args:
            msg: 待匹配的消息信封

        Returns:
            True 表示匹配成功
        """
        ...


class AlwaysRule(Rule):
    """始终匹配的规则"""

    rule_type: ClassVar[str] = "always"

    async def match(self, msg: Message) -> bool:
        return True


class CommandRule(Rule):
    """命令规则：匹配以 prefix + command 开头的消息

    Usage:
        CommandRule("help")           # 匹配 /help
        CommandRule("ping", prefix="!")   # 匹配 !ping
    """

    rule_type: ClassVar[str] = "command"

    def __init__(self, command: str, prefix: str = "/") -> None:
        self._command = command
        self._prefix = prefix

    async def match(self, msg: Message) -> bool:
        text = getattr(msg.event, "pure_text", "").strip()
        if not text:
            return False
        return text.startswith(f"{self._prefix}{self._command}")

    @property
    def prefix(self) -> str:
        """命令前缀"""
        return self._prefix

    @property
    def command(self) -> str:
        """命令名称"""
        return self._command

    def __repr__(self) -> str:
        return f"CommandRule({self._prefix}{self._command!r})"


class RegexRule(Rule):
    """正则规则：对消息文本执行正则搜索

    Usage:
        RegexRule(r"^天气")          # 以"天气"开头
        RegexRule(r"来张.*图")       # 包含模式
    """

    rule_type: ClassVar[str] = "regex"

    def __init__(self, pattern: str, flags: int = 0) -> None:
        self._re = re.compile(pattern, flags)
        self._pattern = pattern

    async def match(self, msg: Message) -> bool:
        text = getattr(msg.event, "raw_message", "")
        if not text:
            return False
        return bool(self._re.search(text))

    @property
    def pattern(self) -> str:
        """正则表达式"""
        return self._pattern

    def __repr__(self) -> str:
        return f"RegexRule({self._pattern!r})"


class GroupRule(Rule):
    """群组规则：匹配指定群号"""

    rule_type: ClassVar[str] = "group"

    def __init__(self, group_id: int) -> None:
        self._group_id = group_id

    async def match(self, msg: Message) -> bool:
        return msg.group_id == self._group_id

    @property
    def group_id(self) -> int:
        """目标群号"""
        return self._group_id

    def __repr__(self) -> str:
        return f"GroupRule({self._group_id})"


class UserRule(Rule):
    """用户规则：匹配指定用户"""

    rule_type: ClassVar[str] = "user"

    def __init__(self, user_id: int) -> None:
        self._user_id = user_id

    async def match(self, msg: Message) -> bool:
        return msg.user_id == self._user_id

    @property
    def user_id(self) -> int:
        """目标用户 QQ"""
        return self._user_id

    def __repr__(self) -> str:
        return f"UserRule({self._user_id})"


class AndRule(Rule):
    """逻辑与：所有子规则都匹配时才匹配"""

    rule_type: ClassVar[str] = "composite"

    def __init__(self, *rules: Rule) -> None:
        if not rules:
            raise ValueError("AndRule 至少需要一个子规则")
        self._rules = rules

    async def match(self, msg: Message) -> bool:
        for r in self._rules:
            if not await r.match(msg):
                return False
        return True

    @property
    def rules(self) -> tuple[Rule, ...]:
        """子规则元组"""
        return self._rules

    def __repr__(self) -> str:
        inner = ", ".join(repr(r) for r in self._rules)
        return f"AndRule({inner})"


class OrRule(Rule):
    """逻辑或：任一子规则匹配时即匹配"""

    rule_type: ClassVar[str] = "composite"

    def __init__(self, *rules: Rule) -> None:
        if not rules:
            raise ValueError("OrRule 至少需要一个子规则")
        self._rules = rules

    async def match(self, msg: Message) -> bool:
        for r in self._rules:
            if await r.match(msg):
                return True
        return False

    @property
    def rules(self) -> tuple[Rule, ...]:
        """子规则元组"""
        return self._rules

    def __repr__(self) -> str:
        inner = ", ".join(repr(r) for r in self._rules)
        return f"OrRule({inner})"


class NotRule(Rule):
    """逻辑非：子规则不匹配时匹配"""

    rule_type: ClassVar[str] = "composite"

    def __init__(self, rule: Rule) -> None:
        self._rule = rule

    async def match(self, msg: Message) -> bool:
        return not await self._rule.match(msg)

    @property
    def rule(self) -> Rule:
        """子规则"""
        return self._rule

    def __repr__(self) -> str:
        return f"NotRule({self._rule!r})"
