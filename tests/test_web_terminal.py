"""WebUI 终端与沙盒流式执行的单元测试

覆盖：哨兵标记的输出流提取（含跨块截断）、多字节字符智能解码（UTF-8/GBK 与分块截断）、
Shell 命令行的哨兵拼接、NoSandbox 的面板扩展点（状态/能力/流式执行）、沙盒工厂。
"""

import asyncio
import sys
from pathlib import Path

import pytest

from atribot.LLMchat.sandbox import factory
from atribot.LLMchat.sandbox.no_sandbox import NoSandbox
from atribot.LLMchat.sandbox.stream_exec import (
    EC_RX,
    LocalCommandStream,
    MarkerStreamFilter,
    StreamDecoder,
    partial_marker_len,
    sentinel_line,
)

EC_TAG = "__ATRI_EC_"

# ---------- 哨兵标记提取 ----------

def test_partial_marker_detects_truncated_tags():
    assert partial_marker_len("abc") == 0
    assert partial_marker_len("输出__ATRI_PWD_") == len("__ATRI_PWD_")
    assert partial_marker_len("x__ATRI_EC_1") > 0
    assert partial_marker_len("__ATRI_EC_9009_") == len("__ATRI_EC_9009_")
    # 完整标记先经正则提取（pump 顺序），剩余部分不再扣留
    assert partial_marker_len(EC_RX.sub("", f"x{EC_TAG}0__")) == 0


def test_marker_filter_extracts_across_chunks():
    text = "普通输出\r\n__ATRI_EC_9009__\r\n__ATRI_PWD_C:\\Users\\test__\r\n"
    # 逐字符喂入，模拟最恶劣的分块
    marker = MarkerStreamFilter()
    emitted = ""
    cwd = code = None
    for ch in text:
        out, c1, c2 = marker.feed(ch)
        emitted += out
        cwd = c1 or cwd
        code = c2 if c2 is not None else code
    emitted += marker.flush()
    assert code == 9009
    assert cwd == "C:\\Users\\test"
    assert "__ATRI" not in emitted  # 标记不会泄漏到可见输出


# ---------- 智能解码 ----------

def test_decoder_utf8_and_gbk():
    d = StreamDecoder()
    assert d.feed("你好".encode("utf-8")) == "你好"
    assert d.feed("中文输出".encode("gbk")) == "中文输出"
    assert d.flush() == ""


def test_decoder_split_multibyte_across_feeds():
    raw = "多字节截断".encode("gbk")
    d = StreamDecoder()
    out = d.feed(raw[:2]) + d.feed(raw[2:4]) + d.feed(raw[4:])
    assert out == "多字节截断"

    raw_u8 = "截断测试".encode("utf-8")
    d = StreamDecoder()
    out = d.feed(raw_u8[:5]) + d.feed(raw_u8[5:])
    assert out == "截断测试"


def test_decoder_invalid_bytes_replaced():
    d = StreamDecoder()
    out = d.feed(b"ok\xffbad")
    assert out.startswith("ok")
    assert d.flush() == ""


# ---------- Shell 命令行拼接 ----------

def test_sentinel_line_contains_tags():
    posix_line = sentinel_line("echo hi", posix=True)
    assert "echo hi" in posix_line and "$(pwd)" in posix_line and "$?" in posix_line

    win_line = sentinel_line("echo hi", posix=False)
    assert "echo hi" in win_line and "^%ERRORLEVEL^%" in win_line
    # EC 标记必须在 PWD 之前（PWD 的 call echo 会清零 ERRORLEVEL）
    assert win_line.index("__ATRI_EC_") < win_line.index("__ATRI_PWD_")


# ---------- 本地命令流（真实子进程） ----------

def test_local_command_stream_exec_and_cwd(tmp_path: Path):
    async def scenario():
        sub = tmp_path / "sub"
        sub.mkdir()
        outputs: list[str] = []

        async def send(text: str) -> None:
            outputs.append(text)

        stream = LocalCommandStream(cwd=str(tmp_path), posix=sys.platform != "win32", timeout=30)
        stream.start(f'echo stream_ok && cd "{sub}"' if sys.platform != "win32" else "echo stream_ok", send)
        code = await stream.wait()

        assert code == 0
        assert "stream_ok" in "".join(outputs)
        if sys.platform != "win32":
            assert stream.new_cwd == str(sub).replace("\\", "/")

    asyncio.run(scenario())


def test_local_command_stream_failure_exit_code():
    async def scenario():
        outputs: list[str] = []

        async def send(text: str) -> None:
            outputs.append(text)

        bad_cmd = "cmdgonnafail_xyz" if sys.platform == "win32" else "exit 3"
        stream = LocalCommandStream(cwd=str(Path.cwd()), posix=sys.platform != "win32", timeout=30)
        stream.start(bad_cmd, send)
        code = await stream.wait()
        assert code != 0

    asyncio.run(scenario())


# ---------- NoSandbox 面板扩展点 ----------

@pytest.fixture()
def no_sandbox(tmp_path: Path) -> NoSandbox:
    sb = NoSandbox(config={"work_dir": tmp_path / "workspace"})
    return sb


def test_no_sandbox_panel_capabilities_and_status(no_sandbox: NoSandbox):
    caps = no_sandbox.panel_capabilities()
    assert caps["start_stop"] is True
    assert caps["terminal"] is True  # 自动探测的 shell 非 powershell

    status = asyncio.run(no_sandbox.panel_status())
    assert status["backend"] == "no-sandbox"
    assert status["running"] is False
    assert any(row[0] == "工作目录" for row in status["rows"])


def test_no_sandbox_panel_exec_stream(tmp_path: Path):
    async def scenario():
        sb = NoSandbox(config={"work_dir": tmp_path / "workspace"})
        await sb.start()
        outputs: list[str] = []

        async def send(text: str) -> None:
            outputs.append(text)

        handle = await sb.panel_exec_stream("echo panel_ok", send)
        code = await handle.wait()
        assert code == 0
        assert "panel_ok" in "".join(outputs)
        assert handle.new_cwd == sb.work_dir

        # 失败命令：哨兵必须回传非零退出码（bash 的 cd 失败 + Windows MSYS 路径归一）
        outputs.clear()
        handle = await sb.panel_exec_stream("cd sub_dir_missing_xyz", send)
        code = await handle.wait()
        assert code != 0
        assert handle.new_cwd == sb.work_dir  # cd 失败，目录不变
        await sb.stop()

    asyncio.run(scenario())


def test_no_sandbox_terminal_info(no_sandbox: NoSandbox):
    info = no_sandbox.panel_terminal_info()
    assert info["cwd"] == no_sandbox.work_dir
    assert info["isWindows"] == (sys.platform == "win32")


# ---------- 沙盒工厂 ----------

def test_factory_creates_no_sandbox():
    sb = factory.create_sandbox({"type": "none"})
    assert isinstance(sb, NoSandbox)
    sb2 = factory.create_sandbox({"type": "local"})
    assert isinstance(sb2, NoSandbox)


def test_factory_docker_branch():
    try:
        sb = factory.create_sandbox({"type": "docker"})
    except Exception as e:  # 无 Docker 守护进程的环境跳过
        pytest.skip(f"Docker 不可用：{e}")
    from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox

    assert isinstance(sb, DockerSandbox)
    assert sb.panel_capabilities()["terminal"] is True


# ---------- WS 鉴权 close code 送达（accept-then-close） ----------

def test_ws_wrong_token_close_code_reaches_client(monkeypatch):
    """错误令牌必须收到 4401 而非 HTTP 403/1006：
    pre-accept close 会被 uvicorn 转成 403，前端永远拿不到真实原因"""
    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from atribot.web_panel.routes import terminal as term_route

    monkeypatch.setenv("ATRI_PANEL_TOKEN", "tok-correct-123")
    app = FastAPI()
    # panel_router 挂载时带 /admin 前缀，这里保持一致
    app.include_router(term_route.router, prefix="/admin")
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/admin/api/ws/terminal?token=wrong-token") as ws:
            ws.receive_text()  # 服务端 accept 后立即带 4401 关闭
    assert exc_info.value.code == 4401


def test_ws_correct_token_receives_hello(monkeypatch):
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from atribot.web_panel.routes import terminal as term_route

    monkeypatch.setenv("ATRI_PANEL_TOKEN", "tok-correct-123")
    app = FastAPI()
    app.include_router(term_route.router, prefix="/admin")
    client = TestClient(app)

    with client.websocket_connect("/admin/api/ws/terminal?token=tok-correct-123") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["platform"] == sys.platform
        assert isinstance(hello["commands"], list)
