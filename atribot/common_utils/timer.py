import functools
import time


def timer(func):
    """计算函数运行时间的装饰器（高精度）。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()

        run_time = end_time - start_time

        if run_time < 1e-6:
            time_str = f"{run_time * 1e9:.3f} ns"
        elif run_time < 1e-3:
            time_str = f"{run_time * 1e6:.3f} μs"
        elif run_time < 1:
            time_str = f"{run_time * 1e3:.3f} ms"
        else:
            time_str = f"{run_time:.6f} s"

        print(f"函数 {func.__name__} 运行时间: {time_str}")
        return result

    return wrapper
