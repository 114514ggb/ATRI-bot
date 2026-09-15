import asyncio
import contextlib
import json
import socket
import urllib.request

import pytest
import uvicorn
from fastapi import FastAPI

from atribot.common_utils.net_utils import bind_port_with_fallback, is_port_in_use, try_bind_port


def _find_free_port() -> int:
    """用 port 0 让系统分配一个空闲端口后立即释放（用于后续探测）"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _occupy_port() -> tuple[socket.socket, int]:
    """占用一个空闲端口（保持监听状态）并返回 (socket, port)"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    return sock, sock.getsockname()[1]


def test_try_bind_port_on_free_port():
    port = _find_free_port()

    sock = try_bind_port("127.0.0.1", port)

    assert sock is not None
    assert sock.getsockname()[1] == port
    sock.close()


def test_try_bind_port_on_occupied_port():
    blocker, port = _occupy_port()
    try:
        assert try_bind_port("127.0.0.1", port) is None
    finally:
        blocker.close()


def test_is_port_in_use():
    blocker, port = _occupy_port()
    try:
        assert is_port_in_use("127.0.0.1", port) is True
    finally:
        blocker.close()
    # 探测用的 socket 已关闭，不会占住端口，释放后应判定为空闲
    assert is_port_in_use("127.0.0.1", port) is False


def test_bind_port_with_fallback_on_free_port():
    port = _find_free_port()

    result = bind_port_with_fallback("127.0.0.1", port)

    assert result is not None
    sock, actual = result
    assert actual == port
    sock.close()


def test_bind_port_with_fallback_on_occupied_port_increments():
    blocker, port = _occupy_port()
    try:
        result = bind_port_with_fallback("127.0.0.1", port)
        assert result is not None
        sock, actual = result
        assert actual > port
        sock.close()
    finally:
        blocker.close()


def test_bind_port_with_fallback_exhausted_returns_none():
    """max_attempts 内全部被占用时返回 None"""
    blocker, port = _occupy_port()
    try:
        assert bind_port_with_fallback("127.0.0.1", port, max_attempts=1) is None
    finally:
        blocker.close()


def test_out_of_range_port_returns_none_instead_of_raising():
    """端口越界时 socket 抛 OverflowError，应按绑定失败处理而不是崩出去"""
    assert try_bind_port("127.0.0.1", 65536) is None
    assert bind_port_with_fallback("127.0.0.1", 65540, max_attempts=3) is None


@pytest.mark.asyncio
async def test_uvicorn_serve_with_prebound_socket():
    """验证预绑定 socket 传给 uvicorn 的启动/请求/关闭链路（与管理面板同一机制）"""
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    sock = try_bind_port("127.0.0.1", _find_free_port())
    assert sock is not None
    port = sock.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    server.capture_signals = lambda: contextlib.nullcontext()

    serve_task = asyncio.create_task(server.serve(sockets=[sock]))
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.05)
    assert server.started, "uvicorn 未能在超时内完成启动"

    # urllib 是阻塞客户端，必须放线程里跑，否则会卡死事件循环导致 uvicorn 无法写回响应
    def _fetch():
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=5) as resp:
            return json.loads(resp.read())

    assert await asyncio.to_thread(_fetch) == {"ok": True}

    server.should_exit = True
    await asyncio.wait_for(serve_task, timeout=5)
