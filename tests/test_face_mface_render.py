import json
from pathlib import Path

import atribot.core.type.chat_message_types as cmt
from atribot.core.type.chat_message_types import (
    FaceSegment,
    MFaceSegment,
    parse_onebot_segments,
)

FACE_MAP_PATH = Path(cmt.__file__).parent / "qq_face_map.json"


def test_face_segment_known_id_rendered_with_name():
    assert str(FaceSegment("14")) == "[CQ:face,id=14,name=微笑]"
    assert str(FaceSegment("66")) == "[CQ:face,id=66,name=爱心]"


def test_face_segment_unknown_id_kept_raw():
    assert str(FaceSegment("99999")) == "[CQ:face,id=99999]"


def test_face_map_file_format():
    #数据源: koishijs/QFace
    data = json.loads(FACE_MAP_PATH.read_text(encoding="utf-8"))
    assert len(data) >= 280
    assert all(key.isdigit() for key in data)
    assert all(isinstance(value, str) and value for value in data.values())
    #锚点: 66=爱心
    assert data["66"] == "爱心"
    assert data["14"] == "微笑"
    #锚点: 现代QQ新表情
    assert data["265"] == "辣眼睛"
    assert data["266"] == "哦哟"
    assert data["267"] == "头秃"
    assert data["268"] == "问号脸"


def test_face_map_load_failure_degrades_to_raw(monkeypatch):
    monkeypatch.setattr(cmt, "_FACE_NAME_MAP", None)
    monkeypatch.setattr(cmt, "_FACE_NAME_MAP_PATH", Path("not/exist/qq_face_map.json"))

    assert cmt.get_face_name_map() == {}
    assert str(FaceSegment("14")) == "[CQ:face,id=14]"


def test_mface_parsed_to_dedicated_segment():
    segments = parse_onebot_segments([
        {"type": "mface", "data": {
            "summary": "[狗狗]",
            "emoji_id": "abc",
            "emoji_package_id": 1,
            "key": "secret-key",
            "url": "https://example.com/emoji.gif",
        }},
    ])

    assert len(segments) == 1
    segment = segments[0]
    assert isinstance(segment, MFaceSegment)
    assert segment.summary == "[狗狗]"
    assert segment.emoji_id == "abc"
    assert segment.data["key"] == "secret-key"

    text = str(segment)
    assert text == "[CQ:mface,summary=狗狗]"
    assert "secret-key" not in text
    assert "example.com" not in text


def test_mface_missing_summary_falls_back():
    segments = parse_onebot_segments([
        {"type": "mface", "data": {"emoji_id": "abc"}},
    ])

    assert str(segments[0]) == "[CQ:mface,summary=商城表情]"


def test_mface_blank_summary_falls_back():
    segments = parse_onebot_segments([
        {"type": "mface", "data": {"summary": "  "}},
    ])

    assert str(segments[0]) == "[CQ:mface,summary=商城表情]"


def test_mface_no_longer_hits_unknown_fallback():
    segments = parse_onebot_segments([
        {"type": "mface", "data": {"summary": "[doge]", "key": "k"}},
    ])

    assert not isinstance(segments[0], cmt.UnknownSegment)
    assert "data:{" not in str(segments[0])
