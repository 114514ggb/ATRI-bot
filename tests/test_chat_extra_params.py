from atribot.web_panel.routes import chat_engine as engine


def test_extra_params_lowest_priority():
    kwargs = engine._chat_parameter_kwargs(
        {"temperature": 1.2},
        {"temperature": 0.1, "top_k": 40, "tool_choice": "none"},
    )
    assert kwargs["temperature"] == 1.2  # 已有配置项覆盖额外 JSON
    assert kwargs["tool_choice"] == "auto"
    assert kwargs["top_k"] == 40


def test_extra_params_blocks_protected_keys():
    kwargs = engine._chat_parameter_kwargs(None, {"model": "x", "messages": [], "tools": [], "stream": False, "seed": 7})
    assert "model" not in kwargs and "messages" not in kwargs and "tools" not in kwargs
    assert kwargs["stream"] is True
    assert kwargs["seed"] == 7


def test_extra_params_rejects_invalid_shape_and_oversize():
    assert engine._sanitize_extra_params([1, 2]) == {}
    assert engine._sanitize_extra_params("x") == {}
    assert engine._sanitize_extra_params({"a": "x" * (engine._EXTRA_PARAM_MAX_BYTES + 1)}) == {}
