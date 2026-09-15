import asyncio

import pytest

from atribot.core.type.chat_types import MessageAggregationWindow, WindowCloseReason

#测试用短窗口:留足事件循环计时抖动余量,Windows 定时器粒度较粗


@pytest.mark.asyncio
async def test_timeout_flushes_whole_batch_in_order():
    flushed: list = []

    async def on_flush(key, items, reason):
        flushed.append((key, list(items), reason))

    window = MessageAggregationWindow(on_flush=on_flush, window_seconds=0.06)
    window.add("u1", "a")
    window.add("u1", "b")
    assert window.pending("u1") == 2

    await asyncio.sleep(0.2)

    assert flushed == [("u1", ["a", "b"], WindowCloseReason.TIMEOUT)]
    assert window.pending("u1") == 0


@pytest.mark.asyncio
async def test_new_message_resets_timer_and_merges_batches():
    flushed: list = []

    async def on_flush(key, items, reason):
        flushed.append((key, list(items), reason))

    window = MessageAggregationWindow(on_flush=on_flush, window_seconds=0.15)

    window.add("u1", "a")
    await asyncio.sleep(0.06)
    window.add("u1", "b")  #重置计时,旧计时器不应再触发

    await asyncio.sleep(0.06)  #距最后一条 0.06s < 0.15s,尚未到窗口
    assert flushed == []
    assert window.pending("u1") == 2

    await asyncio.sleep(0.15)
    assert flushed == [("u1", ["a", "b"], WindowCloseReason.TIMEOUT)]


@pytest.mark.asyncio
async def test_capacity_flushes_immediately_and_restarts():
    flushed: list = []

    async def on_flush(key, items, reason):
        flushed.append((key, list(items), reason))

    window = MessageAggregationWindow(
        on_flush=on_flush, window_seconds=5.0, max_buffer_size=2
    )

    window.add("u1", "a")
    window.add("u1", "b")  #达到上限立即触发

    await asyncio.sleep(0.01)  #让回调任务执行完
    assert flushed == [("u1", ["a", "b"], WindowCloseReason.CAPACITY)]
    assert window.pending("u1") == 0

    #触发后新消息重新开窗,不再受旧缓冲影响
    window.add("u1", "c")
    assert window.pending("u1") == 1

    window.close()


@pytest.mark.asyncio
async def test_manual_flush_and_cancel():
    flushed: list = []

    async def on_flush(key, items, reason):
        flushed.append((key, list(items), reason))

    window = MessageAggregationWindow(on_flush=on_flush, window_seconds=5.0)

    window.add("u1", "a")
    window.add("u1", "b")
    assert window.flush("u1") == ["a", "b"]
    assert window.flush("missing") is None

    await asyncio.sleep(0.01)
    assert flushed == [("u1", ["a", "b"], WindowCloseReason.MANUAL)]

    #cancel 丢弃缓冲且不触发回调
    window.add("u2", "x")
    assert window.cancel("u2") == ["x"]
    assert window.pending("u2") == 0
    await asyncio.sleep(0.01)
    assert len(flushed) == 1

    window.close()


@pytest.mark.asyncio
async def test_independent_keys_fire_on_their_own_timers():
    flushed: list = []

    async def on_flush(key, items, reason):
        flushed.append((key, list(items), reason))

    window = MessageAggregationWindow(on_flush=on_flush, window_seconds=0.06)

    window.add("u1", "a")
    await asyncio.sleep(0.03)
    window.add("u2", "b")

    await asyncio.sleep(0.2)
    assert [(key, items) for key, items, _ in flushed] == [("u1", ["a"]), ("u2", ["b"])]


@pytest.mark.asyncio
async def test_messages_during_callback_merge_into_next_round():
    """回调执行期间的新消息并入缓冲,回调完成后立即触发下一轮(不并发、不等窗口)"""
    flushed: list = []
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def on_flush(key, items, reason):
        flushed.append(list(items))
        if len(flushed) == 1:
            first_started.set()
            await release_first.wait()

    window = MessageAggregationWindow(on_flush=on_flush, window_seconds=0.05)

    window.add("u1", "a")
    await asyncio.sleep(0.12)  #第一批(a)超时触发,回调卡在 wait
    await first_started.wait()
    assert flushed == [["a"]]

    #回调执行期间的新消息:并入缓冲,不开新窗口也不触发新回调
    window.add("u1", "b")
    window.add("u1", "c")
    await asyncio.sleep(0.12)  #远超窗口时间,但消费者在跑,不会触发
    assert flushed == [["a"]]

    release_first.set()  #放行第一批回调
    await asyncio.sleep(0.05)  #下一轮立即处理 bc,无需再等窗口时间
    assert flushed == [["a"], ["b", "c"]]
