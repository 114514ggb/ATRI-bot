from types import SimpleNamespace

from atribot.core.type.context_types import Context
from atribot.LLMchat.chat import ChatBasics


def test_system_message_order() -> None:
    ctx = Context(play_role="人设", static_prompt="静态规则")
    ctx.add_user_message("hi")
    messages = ctx.get_messages()
    assert messages[0] == {"role": "system", "content": "人设\n\n静态规则"}
    assert messages[1]["content"] == "hi"


def test_static_system_prompt_is_stable_and_has_no_dynamic_parts() -> None:
    chat = SimpleNamespace(
        emoji_core=SimpleNamespace(prompt="EMOJI"),
        skills=SimpleNamespace(prompt="SKILLS"),
        tool_calls=SimpleNamespace(get_deferred_tools_prompt=lambda *a, **k: "DEFERRED"),
        _tool_preset_name="group_chat",
        _tool_chat_type="group",
        _static_rules=lambda: "RULES",
    )
    first = ChatBasics._build_static_system_prompt(chat)
    second = ChatBasics._build_static_system_prompt(chat)
    assert first == second == "RULES\n\nEMOJI\n\nSKILLS\n\nDEFERRED"


def test_stored_message_carries_group_and_user_state() -> None:
    text = ChatBasics._format_stored_message(
        user_id=42, prompt="被@了", group_id=1001, body="用户消息:你好"
    )
    assert 'group_id="1001"' in text
    assert 'user_id="42"' in text
    assert "<prompt>被@了</prompt>" in text
    assert text.endswith("用户消息:你好")


def test_stored_message_omits_missing_state() -> None:
    text = ChatBasics._format_stored_message(user_id=None, prompt="定时")
    assert "group_id" not in text
    assert "user_id" not in text
    assert text.endswith("</context>")
