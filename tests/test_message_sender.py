from urllib.parse import quote

from atribot.common_utils import escape_cq_param
from atribot.LLMchat.emoji_system import EmojiCore
from atribot.LLMchat.message_sender import (
    DEFAULT_URL_TEMPLATE,
    CodecogsRenderer,
    MessageSender,
    find_formulas,
    replace_formulas,
)


def test_find_inline_dollar_formula():
    matches = find_formulas("答案就是 $x^2 + y$ 这样")

    assert len(matches) == 1
    assert matches[0].content == "x^2 + y"
    assert matches[0].display is False


def test_find_display_dollar_not_split_by_inline():
    matches = find_formulas("推导：$$a + b = c$$ 完毕")

    assert len(matches) == 1
    assert matches[0].content == "a + b = c"
    assert matches[0].display is True


def test_find_bracket_and_paren_delimiters():
    matches = find_formulas(r"块级 \[E=mc^2\] 行内 \(x_1\)")

    assert len(matches) == 2
    assert matches[0].content == "E=mc^2"
    assert matches[0].display is True
    assert matches[1].content == "x_1"
    assert matches[1].display is False


def test_currency_not_treated_as_formula():
    assert find_formulas("这个卖$5，那个要$10哦") == []
    assert find_formulas("价格是 5$ 和 10$ 之间") == []


def test_plain_text_without_delimiters():
    assert find_formulas("普通中文和english text 123") == []


def test_replace_produces_codecogs_cq_code():
    result = replace_formulas("结果 $a+b$ 没了", CodecogsRenderer().render)

    expected_url = DEFAULT_URL_TEMPLATE + quote("a+b", safe="")
    expected = f"结果 [CQ:image,file={escape_cq_param(expected_url)}] 没了"
    assert result == expected


def test_replace_escapes_ampersand_in_cq_param():
    result = replace_formulas("$a+b$", CodecogsRenderer().render)

    assert "&amp;space;" in result
    assert "[CQ:image,file=" in result


def test_replace_keeps_original_when_render_returns_none():
    text = "看 $$x + y$$ 和 $a_1$"

    assert replace_formulas(text, lambda match: None) == text


def test_render_rejects_overlong_formula():
    renderer = CodecogsRenderer(max_formula_length=5)

    assert renderer.render(type("M", (), {"content": "a" * 6, "display": True})()) is None


def test_render_rejects_blank_formula():
    renderer = CodecogsRenderer()

    assert renderer.render(type("M", (), {"content": "   ", "display": False})()) is None


def test_multiple_formulas_in_one_text():
    result = replace_formulas(
        r"首先 $a^2$，然后 \(b_2\)，最后 \[\frac{c}{d}\]",
        lambda match: f"<{match.content}>",
    )

    assert result == "首先 <a^2>，然后 <b_2>，最后 <\\frac{c}{d}>"


def _cq_image(formula_quoted: str) -> str:
    """构造期望的 codecogs 公式图片 CQ 码（formula_quoted 为已编码的公式）"""
    return f"[CQ:image,file={escape_cq_param(DEFAULT_URL_TEMPLATE)}{formula_quoted}]"


def _make_emoji_core(tmp_path) -> EmojiCore:
    """构造带一个 happy 分类表情的真实 EmojiCore，用于格式化组合测试"""
    happy_dir = tmp_path / "happy"
    happy_dir.mkdir()
    (happy_dir / "a.png").write_bytes(b"")
    return EmojiCore(folder_path=tmp_path)


def _make_sender(tmp_path) -> MessageSender:
    return MessageSender(_make_emoji_core(tmp_path))


def test_format_combines_formula_and_emoji(tmp_path):
    sender = _make_sender(tmp_path)

    result = sender.format_text("[happy] 看 $x^2$ 这个")

    assert result.startswith("[CQ:image,file=file://")
    assert result.endswith(f" 看 {_cq_image('x%5E2')} 这个")


def test_format_reply_prefix(tmp_path):
    sender = _make_sender(tmp_path)

    assert sender.format_text("你好", reply_id=123) == "[CQ:reply,id=123]你好"
    assert sender.format_text_list(["你好", "再见"], reply_id=123) == [
        "[CQ:reply,id=123]你好",
        "再见",
    ]


def test_fallback_text_keeps_formula():
    clean = MessageSender.fallback_text(r"[happy] 好的 \[a+b\] 和 $x^2$")

    assert clean == r"好的 \[a+b\] 和 $x^2$"


def test_fallback_text_with_reply_id():
    assert MessageSender.fallback_text("[happy] 好的", reply_id=7) == "[CQ:reply,id=7]好的"


class _StubSendClient:
    """记录发送内容的桩发送客户端，可控制返回失败触发降级"""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.group_messages: list[tuple[int, str]] = []
        self.private_messages: list[tuple[int, str]] = []

    async def send_group_msg(self, group_id: int, message: str) -> dict:
        self.group_messages.append((group_id, message))
        return {"status": "failed"} if self.fail else {"status": "ok"}

    async def send_private_msg(self, user_id: int, message: str, auto_escape: bool = False) -> dict:
        self.private_messages.append((user_id, message))
        return {"status": "failed"} if self.fail else {"status": "ok"}


async def test_send_group_text_formats_and_sends(tmp_path):
    sender = _make_sender(tmp_path)
    stub = _StubSendClient()

    result = await sender.send_group_text(stub, 10086, "答案 $x^2$", reply_id=55)

    assert result == {"status": "ok"}
    assert stub.group_messages == [
        (10086, f"[CQ:reply,id=55]答案 {_cq_image('x%5E2')}")
    ]


async def test_send_group_text_list_fallback_retry(tmp_path):
    sender = _make_sender(tmp_path)
    stub = _StubSendClient(fail=True)

    results = await sender.send_group_text_list(
        stub, 10086, ["[happy] 开心 $a_1$", "第二条"], reply_id=55, delay=0
    )

    # 每条先发 CQ 版本，失败后用降级纯文本重发（公式保留原文、标签剥掉、回复前缀只在第一条）
    first_cq, first_fallback, second_cq, second_fallback = [
        message for _, message in stub.group_messages
    ]
    assert first_cq.startswith("[CQ:reply,id=55][CQ:image,file=file://")
    assert first_cq.endswith(f"] 开心 {_cq_image('a_1')}")
    assert first_fallback == "[CQ:reply,id=55]开心 $a_1$"
    assert second_cq == "第二条"
    assert second_fallback == "第二条"
    assert results == [{"status": "failed"}, {"status": "failed"}]


async def test_send_private_text_list(tmp_path):
    sender = _make_sender(tmp_path)
    stub = _StubSendClient()

    await sender.send_private_text_list(stub, 10000, ["你好", "再见 $b_2$"], delay=0)

    assert stub.private_messages[0] == (10000, "你好")
    assert stub.private_messages[1][0] == 10000
    assert _cq_image("b_2") in stub.private_messages[1][1]
