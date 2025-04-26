from mcp.server.fastmcp import FastMCP
import time


mcp = FastMCP("WeatherServer")


@mcp.tool()
async def get_time() -> str:
    """
    获取当前时间\n
    :param: 什么也不需要\n
    :return: time
    """
    return time.strftime('%Y-%m-%d %H:%M:%S')



if __name__ == "__main__":
    mcp.run(transport='stdio')