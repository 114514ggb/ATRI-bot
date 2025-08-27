from mcp.server.fastmcp import FastMCP
from .local_mcp_tools.get_weather import weather_main


mcp = FastMCP("mcpServer")


@mcp.tool()
async def query_weather(city: str) -> str:
    """
    输入指定城市的英文名称，返回今日天气查询结果。
    :param city: 城市名称（需使用英文）
    :return: 格式化后的天气信息
    """
    return await weather_main(city)



if __name__ == "__main__":
    mcp.run(transport='stdio')