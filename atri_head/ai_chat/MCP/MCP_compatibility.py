from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack
from typing import Optional

class mcp_tools:
    
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None
    
    async def connect_mcp_server(self, server_script_path:str):
        """
        连接到本地 MCP 服务器\n
        输入服务器文件地址\n
        支持js或py文件
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("mcp服务器脚本必须是 .py 或 .js 文件")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=server_script_path,
            env=None
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()
    
    
    async def get_all_tools_json(self)->list:
        """获取全部工具的json格式"""
        return [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
        } for tool in (await self.session.list_tools()).tools]
    
    
    async def run_tool(self, tool_name:str, tool_args:str)->str:
        """运行工具返回结果"""
        return await self.session.call_tool(tool_name, tool_args)
    
    
    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()