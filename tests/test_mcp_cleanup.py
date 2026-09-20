"""ToolManager.cleanup 的单元测试

覆盖：cleanup 会真正等待并终止各客户端；单个客户端终止卡死时，
总耗时被 _CLEANUP_TIMEOUT 兜住，不阻塞关机流程。
"""

import asyncio
import time

from atribot.LLMchat.MCP.mcp_tool_manager import ToolManager


class _FakeClient:
    def __init__(self, hang: bool):
        self._hang = hang
        self.cleaned = False

    async def cleanup(self):
        if self._hang:
            await asyncio.sleep(60)  # 模拟 stdio 子进程不肯退出
        self.cleaned = True


async def test_cleanup_terminates_clients_normally():
    tm = ToolManager(mcp_path="")
    tm._CLEANUP_TIMEOUT = 2.0
    tm.mcp_client_dict["正常服务"] = _FakeClient(hang=False)

    await tm.cleanup()

    assert "正常服务" not in tm.mcp_client_dict  # 客户端被移除
    assert tm._mcp_service_task is None


async def test_cleanup_bounded_when_client_hangs():
    tm = ToolManager(mcp_path="")
    tm._CLEANUP_TIMEOUT = 0.3
    tm.mcp_client_dict["卡死服务"] = _FakeClient(hang=True)

    start = time.monotonic()
    await asyncio.wait_for(tm.cleanup(), timeout=5.0)  # cleanup 自身绝不能卡死
    elapsed = time.monotonic() - start

    assert elapsed < 3.0  # 远小于假客户端的 60s
    assert "卡死服务" in tm.mcp_client_dict  # 未完成的客户端留在后台自行退出


async def test_cleanup_signals_wrapper_to_close_in_same_task():
    """正常路径：cleanup 唤醒持有连接的 wrapper 任务自行终止（same-task 关闭），
    而不是从别的任务直接 aclose（那会触发 anyio cancel scope 跨任务错误）"""
    tm = ToolManager(mcp_path="")
    tm._CLEANUP_TIMEOUT = 2.0
    client = _FakeClient(hang=False)
    tm.mcp_client_dict["正常服务"] = client
    event = asyncio.Event()
    tm.mcp_client_event["正常服务"] = event

    async def fake_wrapper():
        await event.wait()  # 与真实 wrapper 相同的终止约定
        await client.cleanup()
        del tm.mcp_client_dict["正常服务"]

    task = asyncio.create_task(fake_wrapper())
    tm._wrapper_tasks.add(task)
    task.add_done_callback(tm._wrapper_tasks.discard)

    await tm.cleanup()

    assert client.cleaned  # wrapper 在自己的任务里完成了关闭
    assert "正常服务" not in tm.mcp_client_dict
    assert tm._mcp_service_task is None
