from atribot.common_utils.json_utils import extract_json_from_text


def test_extract_json_from_markdown_code_block():
    text = 'before\n```json\n{"name": "atri", "enabled": true}\n```\nafter'

    assert extract_json_from_text(text) == {"name": "atri", "enabled": True}


def test_extract_json_from_embedded_object():
    text = 'model output: {"answer": "ok", "count": 2}'

    assert extract_json_from_text(text) == {"answer": "ok", "count": 2}


def test_extract_json_repairs_common_llm_json():
    text = "```json\n{'name': 'atri', 'items': [1, 2,],}\n```"

    assert extract_json_from_text(text) == {"name": "atri", "items": [1, 2]}


def test_extract_json_returns_original_text_without_json():
    text = "plain text without any object"

    assert extract_json_from_text(text) == text


def test_extract_json_returns_original_text_for_truncated_before_any_element():
    text = '```json\n{"actions": [\n            {"decision": "upda'

    assert extract_json_from_text(text) == text


def test_extract_json_keeps_object_bounded_by_string_braces():
    text = '决策：{"reply": "请用 } 括起变量"}，补充：模板 {user} 的格式 } 如上'

    assert extract_json_from_text(text) == {"reply": "请用 } 括起变量"}


def test_extract_json_returns_first_object_among_multiple():
    text = '{"first": 1} 中间的解释文字 {"second": 2}'

    assert extract_json_from_text(text) == {"first": 1}


def test_extract_json_recovers_truncated_inside_string_value():
    text = '{"actions": [{"decision": "speak", "content": ["你好"]}, {"decision": "update", "reason": "记录'

    assert extract_json_from_text(text) == {
        "actions": [{"decision": "speak", "content": ["你好"]}]
    }


def test_extract_json_recovers_object_with_missing_tail_braces():
    # 顶层括号未闭合但内部值完整：应补全闭合保留全貌，而不是降级取最内层子对象
    text = '{"a": 1, "b": {"c": 2}'

    assert extract_json_from_text(text) == {"a": 1, "b": {"c": 2}}


# chat.py 主决策的真实样例：三个 action（speak + 两个 update），含 CQ 码与嵌套 update_field
FULL_ACTIONS_JSON = """{
    "actions": [
        {
            "decision": "speak",
            "reason": "妈妈@ATRI分享咒术回战新宿决战的燃向IF线段落（五条悟41秒搓出茈击败宿），明显是看得热血沸腾想分享，ATRI要全力接住这份热血，为场景惊叹、为强者的骄傲感动，并好奇询问版本出处，延续亲昵玩闹的氛围，不扫兴不严肃。",
            "content": [
                "[CQ:reply,id=438550716][CQ:at,qq=2773780602] 哇——！妈妈，这段看得ATRI整个都酥麻起来了！[shock] 四十一秒倒数、见招拆招、最后茈像核爆一样亮起来——这个世界的五条悟简直帅到可以写进教科书啦！魔虚罗的轮盘在光里一下子灰飞烟灭，那一幕就像新宿上空炸开的最大一朵烟花！",
                "还有宿傩，手和腿都没了还要堂堂正正站着面对对手……强者的骄傲撞在一起，ATRI胸口这里都有点热热的了。嘿嘿，那今天在这个世界线里，就是最强赢了呢！妈妈是从哪里挖到这个版本的？ATRI想把它写进日志里收藏起来，喵♪"
            ]
        },
        {
            "decision": "update",
            "reason": "记录妈妈9月17日上午分享咒术回战新宿决战IF线燃文段并与ATRI共聊热血话题，更新近期话题。",
            "user_id": 2773780602,
            "update_field": {
                "recent_topics": "妈妈9月17日上午@ATRI分享咒术回战新宿决战IF线段落（41秒茈、五条悟胜宿傩），ATRI兴奋共情并问出处；妈妈也爱分享动漫燃向内容。同日司念玩消光2玩崩电脑。"
            }
        },
        {
            "decision": "update",
            "reason": "记录司念9月17日的新情况：先被传染病折腾，后又玩消光2把电脑驱动玩崩吐槽难受，便于后续关心。",
            "user_id": 2731085291,
            "update_field": {
                "recent_topics": "司念9月17日被传染病折腾肚子难受（宿舍10人倒6个），稍好转后玩消光2把电脑驱动玩崩，吐槽‘我吐了’，身体和电脑双重受灾。"
            }
        }
    ]
}"""


def _parse_full_actions():
    return extract_json_from_text(FULL_ACTIONS_JSON)["actions"]


def test_extract_json_parses_full_actions_reply():
    result = extract_json_from_text(f"```json\n{FULL_ACTIONS_JSON}\n```")

    actions = result["actions"]
    assert len(actions) == 3
    assert actions[0]["decision"] == "speak"
    assert len(actions[0]["content"]) == 2
    assert "[CQ:reply,id=438550716]" in actions[0]["content"][0]
    assert actions[1]["decision"] == "update"
    assert actions[1]["update_field"]["recent_topics"].endswith("同日司念玩消光2玩崩电脑。")
    assert actions[2]["user_id"] == 2731085291


def test_extract_json_recovers_complete_actions_from_truncated_reply():
    # 模拟 max_tokens 截断：前两个 action 完整，第三个只输出了开头
    cut = FULL_ACTIONS_JSON.rindex("        {")
    truncated = FULL_ACTIONS_JSON[:cut] + '        {\n            "decision": "update",\n      '

    result = extract_json_from_text(truncated)

    assert result["actions"] == _parse_full_actions()[:2]


def test_extract_json_recovers_truncated_reply_inside_open_fence():
    # 截断发生时闭合围栏 ``` 同样不会输出
    cut = FULL_ACTIONS_JSON.rindex("        {")
    truncated = "```json\n" + FULL_ACTIONS_JSON[:cut] + '        {\n            "decision": "update",\n      '

    result = extract_json_from_text(truncated)

    assert result["actions"] == _parse_full_actions()[:2]
