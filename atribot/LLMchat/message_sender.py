"""负责把 AI 输出文本格式化并发送出去

格式化: LaTeX 公式→图片CQ码、表情标签→图片CQ码、回复引用前缀
发送: 实际调用 SendClientBase 发送，失败时自动降级为纯文本重试
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote

from atribot.common_utils import escape_cq_param
from atribot.core.logger import get_named_logger
from atribot.core.platform.send_client import SendClientBase
from atribot.core.service_container import ServiceBase
from atribot.LLMchat.emoji_system import EmojiCore

DEFAULT_URL_TEMPLATE = r"https://latex.codecogs.com/png.image?\dpi{150}&space;"
"""codecogs 公式图片 URL 模板，公式本体经 URL 编码后拼接到模板末尾"""

DEFAULT_MAX_FORMULA_LENGTH = 300
"""公式本体超过该长度时不渲染，保留原文"""

_MATH_HINT_PATTERN = re.compile(r"[\\^_{}=+<>|]")
"""行内 $...$ 的内容需包含这些数学特征字符之一才认定为公式，防止货币金额等误判"""


@dataclass(slots=True)
class FormulaMatch:
    """文本中匹配到的一段公式"""

    content: str
    """公式本体，不含定界符"""
    display: bool
    """是否块级公式"""
    start: int
    """在原文中的起始位置（含定界符）"""
    end: int
    """在原文中的结束位置（不含，含定界符）"""


# 匹配顺序: 块级定界符在前，行内在后；find_formulas 会丢弃与已匹配区间重叠的结果，
# 保证 $$..$$ 不会被行内 $..$ 规则重复拆分
_FORMULA_PATTERNS: tuple[tuple[re.Pattern[str], bool, bool], ...] = (
    (re.compile(r"\$\$(.+?)\$\$", re.DOTALL), True, False),
    (re.compile(r"\\\[(.+?)\\\]", re.DOTALL), True, False),
    (re.compile(r"\\\((.+?)\\\)", re.DOTALL), False, False),
    (re.compile(r"\$([^$\n]+?)\$"), False, True),
)
"""(正则, 是否块级, 是否需要数学特征校验)"""


def find_formulas(text: str) -> list[FormulaMatch]:
    """提取文本中的全部 LaTeX 公式

    Args:
        text (str): 待提取的文本

    Returns:
        list[FormulaMatch]: 按出现位置排序的公式列表
    """
    matches: list[FormulaMatch] = []

    for pattern, display, need_hint in _FORMULA_PATTERNS:
        for match in pattern.finditer(text):
            if need_hint and not _MATH_HINT_PATTERN.search(match.group(1)):
                continue

            start, end = match.span()
            if any(start < m.end and m.start < end for m in matches):
                continue

            matches.append(
                FormulaMatch(content=match.group(1), display=display, start=start, end=end)
            )

    matches.sort(key=lambda m: m.start)
    return matches


def replace_formulas(
    text: str,
    render: Callable[[FormulaMatch], str | None],
) -> str:
    """把文本中的公式替换为渲染结果

    Args:
        text (str): 原始文本
        render (Callable[[FormulaMatch], str | None]): 渲染函数，返回替换文本
            （如 CQ 码）；返回 None 表示放弃该公式的渲染，保留原文

    Returns:
        str: 替换后的文本
    """
    matches = find_formulas(text)
    if not matches:
        return text

    parts: list[str] = []
    cursor = 0
    for match in matches:
        replacement = render(match)
        if replacement is None:
            continue
        parts.append(text[cursor : match.start])
        parts.append(replacement)
        cursor = match.end
    parts.append(text[cursor:])

    return "".join(parts)


class CodecogsRenderer:
    """通过 codecogs 在线服务把公式渲染成图片 CQ 码

    未来的浏览器渲染器实现同样的 render 接口即可在 MessageSender 中替换使用
    """

    def __init__(self, max_formula_length: int = DEFAULT_MAX_FORMULA_LENGTH):
        self.max_formula_length = max_formula_length

    def render(self, match: FormulaMatch) -> str | None:
        """把公式渲染为 [CQ:image] 码

        Args:
            match (FormulaMatch): 公式匹配结果

        Returns:
            str | None: CQ 图片码；公式为空或超长时返回 None 保留原文
        """
        content = match.content.strip()
        if not content or len(content) > self.max_formula_length:
            return None

        url = DEFAULT_URL_TEMPLATE + quote(content, safe="")
        return f"[CQ:image,file={escape_cq_param(url)}]"


class MessageSender(ServiceBase):
    """AI 输出文本的格式化与发送"""

    def __init__(self, emoji_core: EmojiCore):
        self.emoji_core: EmojiCore = emoji_core
        self.formula_renderer = CodecogsRenderer()
        self.log = get_named_logger("MessageSender")

    def format_text(
        self,
        text: str,
        reply_id: str | int | None = None,
        max_emoji: int = 3,
    ) -> str:
        """单条文本转 CQ 消息：公式替换 → 表情标签替换 → 回复前缀

        Args:
            text (str): AI 输出的原始文本
            reply_id (str | int | None, optional): 回复引用消息 ID
            max_emoji (int, optional): 最大表情数量，超出部分自动移除，默认 3

        Returns:
            str: 转换后的带有 CQ 码的字符串
        """
        text = replace_formulas(text, self.formula_renderer.render)
        return self.emoji_core.parse_text_to_cqcode_with_emotion(
            text,
            self.emoji_core.emoji_file_dict,
            reply_id,
            max_emoji=max_emoji,
        )

    def format_text_list(
        self,
        text_list: list[str],
        reply_id: str | int | None = None,
        max_emoji: int = 3,
    ) -> list[str]:
        """文本列表转 CQ 消息列表，回复前缀只附加到第一条

        Args:
            text_list (list[str]): AI 输出的原始文本列表
            reply_id (str | int | None, optional): 回复引用消息 ID
            max_emoji (int, optional): 最大表情数量，超出部分自动移除，默认 3

        Returns:
            list[str]: 转换后的带有 CQ 码的列表，顺序与输入一致
        """
        rendered_list = [
            replace_formulas(text, self.formula_renderer.render)
            for text in text_list
        ]
        return self.emoji_core.parse_list_to_cqcode_with_emotion(
            rendered_list,
            self.emoji_core.emoji_file_dict,
            reply_id,
            max_emoji=max_emoji,
        )

    @staticmethod
    def fallback_text(text: str, reply_id: str | int | None = None) -> str:
        """发送失败降级用的纯文本：剥掉方括号标签，公式保留原文

        Args:
            text (str): AI 输出的原始文本
            reply_id (str | int | None, optional): 回复引用消息 ID

        Returns:
            str: 降级文本，剥掉标签后为空时返回空字符串
        """
        clean_text = re.sub(r"(?<!\\)\[.*?\]", "", text).strip()
        if clean_text and reply_id:
            clean_text = f"[CQ:reply,id={reply_id}]{clean_text}"

        return clean_text


    async def send_group_text(
        self,
        send_client: SendClientBase,
        group_id: int,
        text: str,
        reply_id: str | int | None = None,
    ) -> dict | None:
        """格式化并发送单条群文本消息，失败时自动降级重试

        Args:
            send_client (SendClientBase): 发送客户端
            group_id (int): 群号
            text (str): AI 输出的原始文本
            reply_id (str | int | None, optional): 回复引用消息 ID

        Returns:
            dict | None: 最后一次发送的结果
        """
        cq_message = self.format_text(text, reply_id=reply_id)
        results = await self._send_with_fallback(
            [cq_message],
            [text],
            send_func=lambda msg: send_client.send_group_msg(group_id, msg),
            reply_id=reply_id,
        )
        return results[0]

    async def send_group_text_list(
        self,
        send_client: SendClientBase,
        group_id: int,
        text_list: list[str],
        reply_id: str | int | None = None,
        delay: float = 0,
    ) -> list[dict | None]:
        """格式化并逐条发送群文本消息，每条失败时自动降级重试

        Args:
            send_client (SendClientBase): 发送客户端
            group_id (int): 群号
            text_list (list[str]): AI 输出的原始文本列表
            reply_id (str | int | None, optional): 回复引用消息 ID（降级重发时只附加到第一条）
            delay (float, optional): 每条消息发送后的延迟（秒）

        Returns:
            list[dict | None]: 各条消息的发送结果列表
        """
        return await self._send_with_fallback(
            self.format_text_list(text_list, reply_id=reply_id),
            text_list,
            send_func=lambda msg: send_client.send_group_msg(group_id, msg),
            reply_id=reply_id,
            delay=delay,
        )

    async def send_private_text(
        self,
        send_client: SendClientBase,
        user_id: int,
        text: str,
        reply_id: str | int | None = None,
    ) -> dict | None:
        """格式化并发送单条私聊文本消息，失败时自动降级重试

        Args:
            send_client (SendClientBase): 发送客户端
            user_id (int): 用户 ID
            text (str): AI 输出的原始文本
            reply_id (str | int | None, optional): 回复引用消息 ID

        Returns:
            dict | None: 最后一次发送的结果
        """
        cq_message = self.format_text(text, reply_id=reply_id)
        results = await self._send_with_fallback(
            [cq_message],
            [text],
            send_func=lambda msg: send_client.send_private_msg(user_id=user_id, message=msg),
            reply_id=reply_id,
        )
        return results[0]

    async def send_private_text_list(
        self,
        send_client: SendClientBase,
        user_id: int,
        text_list: list[str],
        reply_id: str | int | None = None,
        delay: float = 0,
    ) -> list[dict | None]:
        """格式化并逐条发送私聊文本消息，每条失败时自动降级重试

        Args:
            send_client (SendClientBase): 发送客户端
            user_id (int): 用户 ID
            text_list (list[str]): AI 输出的原始文本列表
            reply_id (str | int | None, optional): 回复引用消息 ID（降级重发时只附加到第一条）
            delay (float, optional): 每条消息发送后的延迟（秒）

        Returns:
            list[dict | None]: 各条消息的发送结果列表
        """
        return await self._send_with_fallback(
            self.format_text_list(text_list, reply_id=reply_id),
            text_list,
            send_func=lambda msg: send_client.send_private_msg(user_id=user_id, message=msg),
            reply_id=reply_id,
            delay=delay,
        )


    async def _send_with_fallback(
        self,
        cq_messages: list[str],
        original_texts: list[str],
        send_func: Callable[[str], object],
        reply_id: str | int | None = None,
        delay: float = 0,
    ) -> list[dict | None]:
        """逐条发送，失败时用降级纯文本重试，回复前缀只附加到第一条"""
        results: list[dict | None] = []

        for index, cq_message in enumerate(cq_messages):
            result: dict = await send_func(cq_message)

            if result and result.get("status") != "ok":
                self.log.warning(
                    "分条消息发送失败(index=%s,status=%s)，改用降级纯文本重发",
                    index,
                    result.get("status"),
                )
                clean_text = self.fallback_text(
                    original_texts[index],
                    reply_id=reply_id if index == 0 else None,
                )
                if clean_text:
                    result = await send_func(clean_text)

            results.append(result)

            await asyncio.sleep(delay)

        return results
