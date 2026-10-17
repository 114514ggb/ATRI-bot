import datetime

from atribot.common_utils.message_utils import construction_message_dict, parse_time_to_timestamp


def test_construction_message_dict():
    # 基本的多模态转换
    template = [
        {"image": "ATRI_smile.jpg"},
        {"text": "你好！"}
    ]

    res = construction_message_dict(template, url_prefix="file://")
    assert len(res) == 2
    assert res[0] == {"type": "image", "data": {"file": "file://ATRI_smile.jpg"}}
    assert res[1] == {"type": "text", "data": {"text": "你好！"}}

    # 无前缀转换
    res_no_prefix = construction_message_dict(template)
    assert res_no_prefix[0]["data"]["file"] == "ATRI_smile.jpg"

    # 空值忽略
    template_empty = [{"image": ""}, {"text": "text"}]
    res_empty = construction_message_dict(template_empty)
    assert len(res_empty) == 1
    assert res_empty[0]["type"] == "text"

def test_parse_time_to_timestamp():
    # 正常日期解析 (默认当天0点)
    ts = parse_time_to_timestamp("2024-01-01")
    dt = datetime.datetime.fromtimestamp(ts)
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 1
    assert dt.hour == 0
    assert dt.minute == 0
    assert dt.second == 0

    # 结束日期边界解析 (变更为23:59:59)
    ts_end = parse_time_to_timestamp("2024-01-01", is_end_time=True)
    dt_end = datetime.datetime.fromtimestamp(ts_end)
    assert dt_end.hour == 23
    assert dt_end.minute == 59
    assert dt_end.second == 59

    # 带具体时间的解析
    ts_time = parse_time_to_timestamp("2024-01-01 12:34:56")
    dt_time = datetime.datetime.fromtimestamp(ts_time)
    assert dt_time.hour == 12
    assert dt_time.minute == 34

    # 无效时间
    assert parse_time_to_timestamp("invalid-date") is None
