import textwrap


async def async_run_exec(text: str) -> None:
    """在当前携程中异步执行一段字符串形式的异步代码"""
    src = f"""
async def function():
{textwrap.indent(text, "  ")}
"""
    locs = {}
    exec(src, globals(), locs)
    coro = locs["function"]()
    await coro
