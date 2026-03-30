import asyncio
import functools
import inspect
import time
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


def _format_run_time(run_time: float) -> str:
    if run_time < 1e-6:
        return f"{run_time * 1e9:.3f} ns"
    if run_time < 1e-3:
        return f"{run_time * 1e6:.3f} μs"
    if run_time < 1:
        return f"{run_time * 1e3:.3f} ms"
    return f"{run_time:.6f} s"


def timer(func):
    """计算函数运行时间的装饰器（高精度）"""
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                end_time = time.perf_counter()
                time_str = _format_run_time(end_time - start_time)
                print(f"函数 {func.__name__} 运行时间: {time_str}")

        return async_wrapper

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            end_time = time.perf_counter()
            time_str = _format_run_time(end_time - start_time)
            print(f"函数 {func.__name__} 运行时间: {time_str}")

    return wrapper


async def poll_until_done(
    request_fn: Callable[[], Awaitable[T] | T],
    check_fn: Callable[[T], Awaitable[bool] | bool],
    interval: float = 1.0,
    timeout: float | None = None,
    max_retries: int | None = None,
) -> bool:
    """发起一个任务并轮询直到完成

    先调用 ``request_fn`` 一次获取任务句柄，然后每隔 ``interval`` 秒调用
    ``check_fn(handle)`` 检查是否完成。``timeout`` 与 ``max_retries`` 同时存在时，
    任意一个条件先触发均视为超时返回 ``False``

    Args:
        request_fn: 发起任务的函数，只调用一次，返回值会作为句柄传给 ``check_fn``
            支持普通函数和协程函数。
        check_fn: 接收任务句柄，返回 ``True`` 表示任务完成。
            支持普通函数和协程函数。
        interval: 每次轮询的间隔秒数，默认 ``1.0``
        timeout: 最大等待时间（秒）。``None`` 表示不受时间限制。
        max_retries: 最大轮询次数。``None`` 表示不受次数限制。

    Returns:
        任务在限制条件内完成返回 ``True``，否则返回 ``False``
    """
    if inspect.iscoroutinefunction(request_fn):
        handle: Any = await request_fn()
    else:
        handle = request_fn()

    deadline = time.perf_counter() + timeout if timeout is not None else None
    attempts = 0

    while True:
        if deadline is not None and time.perf_counter() >= deadline:
            return False
        if max_retries is not None and attempts >= max_retries:
            return False

        if inspect.iscoroutinefunction(check_fn):
            done: bool = await check_fn(handle)
        else:
            done = check_fn(handle)

        if done:
            return True

        attempts += 1
        await asyncio.sleep(interval)


def retry(
    max_retries: int = 3,
    interval: float = 1.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
):
    """函数/协程重试装饰器。

    只要抛出指定异常就自动重试，支持同步和异步函数。

    Args:
        max_retries: 最大重试次数（含首次），默认 3。
        interval: 每次重试的间隔秒数，默认 1.0。
        exceptions: 需要捕获并重试的异常类型元组，默认 (Exception,)

    Returns:
        装饰后的函数。
    """
    def decorator(func: Callable):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        last_exc = e
                        if attempt < max_retries - 1:
                            await asyncio.sleep(interval)
                raise last_exc
            return async_wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exc = e
                        if attempt < max_retries - 1:
                            time.sleep(interval)
                raise last_exc
            return wrapper
    return decorator
