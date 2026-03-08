import functools
import inspect
import time


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
