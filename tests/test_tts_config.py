"""TTS 配置测试：面板保存校验与 TTSService 配置解析

运行：uv run python -m pytest tests/ -q
"""

import logging
from pathlib import Path
from types import SimpleNamespace

from atribot.commands.audio.TTS import TTSService
from atribot.web_panel.routes.config import _validate_tts


def _service() -> TTSService:
    """绕过容器依赖，只测纯解析逻辑"""
    service = object.__new__(TTSService)
    service.log = logging.getLogger("test.tts")
    return service


# ---------- 面板保存校验 ----------

def test_validate_tts_shape_and_happy_path():
    # 未配置 / None 都是合法的空配置
    assert _validate_tts({}) == []
    assert _validate_tts({"tts": None}) == []

    # 非对象立即报错
    errors = _validate_tts({"tts": []})
    assert errors and "tts 必须是对象" in errors[0]

    # 完整合法配置无错误
    data = {
        "tts": {
            "api_url": "http://127.0.0.1:9880",
            "emotions": {
                "平静": {
                    "refer_wav_path": "D:/tts/ref.mp3",
                    "prompt_text": "参考文本",
                    "prompt_language": "ja",
                }
            },
        }
    }
    assert _validate_tts(data) == []


def test_validate_tts_rejects_bad_fields():
    data = {
        "tts": {
            "api_url": "127.0.0.1:9880",
            "emotions": {
                "高兴": {"refer_wav_path": ""},
                "有 空格": {"refer_wav_path": "/tmp/a.mp3"},
                "坏类型": "not-an-object",
            },
        }
    }
    errors = _validate_tts(data)
    joined = "；".join(errors)
    assert "http:// 或 https://" in joined
    assert "refer_wav_path 不能为空" in joined
    assert "不能包含空白字符" in joined
    assert "必须是对象" in joined


# ---------- TTSService 解析 ----------

def test_load_custom_emotions():
    config = SimpleNamespace(
        tts={
            "api_url": "http://tts.local:9880",
            "emotions": {
                "平静": {
                    "refer_wav_path": "D:/tts/ref.mp3",
                    "prompt_text": "夏生さんが望むのでしたら",
                }
            },
        },
        file_path=SimpleNamespace(audio="D:/audio"),
    )
    api_url, emotions = _service()._load_tts_config(config)
    assert api_url == "http://tts.local:9880"
    assert set(emotions) == {"平静"}
    assert emotions["平静"]["prompt_language"] == "auto"


def test_load_falls_back_to_builtin_emotions():
    config = SimpleNamespace(file_path=SimpleNamespace(audio="D:/audio"))
    api_url, emotions = _service()._load_tts_config(config)
    assert api_url == "http://127.0.0.1:9880"
    assert set(emotions) == {"高兴", "机械", "平静"}
    expected_dir = Path("D:/audio") / "tts_reference"
    assert all(Path(item["refer_wav_path"]).parent == expected_dir for item in emotions.values())
