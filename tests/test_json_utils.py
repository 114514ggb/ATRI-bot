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
