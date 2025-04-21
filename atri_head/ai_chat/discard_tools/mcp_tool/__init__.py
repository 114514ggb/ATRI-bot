from modelcontextprotocol.sdk.client import McpClient
import asyncio

tool_json = {
    "name": "mcp_tool",
    "description": "MCP协议工具，可以通过MCP服务器执行各种功能",
    "properties": {
        "server_name": {
            "type": "string", 
            "description": "要连接的MCP服务器名称"
        },
        "tool_name": {
            "type": "string",
            "description": "要调用的工具名称"
        },
        "arguments": {
            "type": "object",
            "description": "传递给工具的参数"
        }
    }
}

async def main(server_name: str, tool_name: str, arguments: dict):
    """
    调用MCP工具的主函数
    """
    try:
        # 创建MCP客户端
        client = McpClient()
        
        # 调用MCP工具
        result = await client.call_tool(
            server_name=server_name,
            tool_name=tool_name,
            arguments=arguments
        )
        
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
