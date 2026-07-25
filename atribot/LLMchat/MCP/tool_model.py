from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable

import mcp
from mcp.types import CallToolResult

from atribot.core.type.bot_types import atriMessageEvent

if TYPE_CHECKING:
    from atribot.LLMchat.MCP.mcp_tool_manager import MCPClient


class FunctionTool:
    """工具基类 —— 定义所有工具的公共属性

    Attributes:
        name: 工具名称,全局唯一标识
        description: 工具功能描述,供 LLM 理解工具用途
        parameters: 工具参数 JSON Schema,默认为空的 object 类型
        concurrent: 是否允许并发执行
        background: 是否为后台任务,执行后返回已执行标志，等待执行完成后回调返回结果
        active: 是否启用
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict | None = None,
        concurrent: bool = False,
        background: bool = False,
        active: bool = True,
    ) -> None:
        """初始化工具基类

        Args:
            name: 工具名称,全局唯一标识
            description: 工具功能描述,供 LLM 理解工具用途
            parameters: 工具参数 JSON Schema,若为 None 则默认为
                ``{"type": "object", "properties": {}}``
            concurrent: 是否允许并发执行,默认为 ``False``
            background: 是否为后台任务,默认为 ``False``,会返回一个结果标识,等待完成后触发回调函数给出结果
            active: 是否启用,默认为 ``True``
        """
        self.name: str = name
        """工具名称,全局唯一标识"""
        self.description: str = description
        """工具功能描述,供 LLM 理解工具用途"""
        self.parameters: dict = parameters or {"type": "object", "properties": {}}
        """工具参数 JSON Schema"""
        self.concurrent: bool = concurrent
        """是否允许并发执行,为 ``False`` 时调用方应串行化调用"""
        self.background: bool = background
        """是否为后台任务,为 ``True`` 时调用方不需要等待结果"""
        self.active: bool = active
        """是否启用"""

    async def execute(
        self, message_data: atriMessageEvent, **kwargs: Any
    ) -> str | CallToolResult:
        """执行工具 —— 子类必须覆盖此方法

        Args:
            message_data: 聊天消息事件上下文
            **kwargs: 工具参数
        """
        ...

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name={self.name!r}, "
            f"active={self.active!r}"
            f")"
        )


class LocalTool(FunctionTool):
    """本地工具 —— 由本地异步函数驱动的工具

    Attributes:
        handler: 异步处理函数
        handler_module_path: handler 所在模块路径（用于 functools.partial 包装后
            恢复 ``__module__`` 信息）
    """

    def __init__(
        self,
        name: str,
        description: str,
        handler: Awaitable,
        parameters: dict | None = None,
        concurrent: bool = False,
        background: bool = False,
        active: bool = True,
        handler_module_path: str | None = None,
    ) -> None:
        """初始化本地工具

        Args:
            name: 工具名称,全局唯一标识
            description: 工具功能描述
            handler: 异步处理函数
            parameters: 工具参数 JSON Schema
            concurrent: 是否允许并发执行
            background: 是否为后台任务
            active: 是否启用
        """
        super().__init__(
            name=name,
            description=description,
            parameters=parameters,
            concurrent=concurrent,
            background=background,
            active=active,
        )
        self.handler: Awaitable = handler
        """异步处理函数"""

    async def execute(
        self, message_data: atriMessageEvent, **kwargs: Any
    ) -> str | CallToolResult:
        """执行本地工具

        检查 handler 是否存在,自动注入 ``message_data`` 到 handler 签名中,
        然后调用 ``await self.handler(**kwargs)``

        Args:
            message_data: 聊天消息事件上下文
            **kwargs: 工具参数

        Returns:
            工具执行结果

        Raises:
            Exception: handler 不存在时抛出
        """
        if not self.handler:
            raise Exception(f"本地工具 {self.name} 没有绑定处理函数")
        if "message_data" in inspect.signature(
            self.handler
        ).parameters:
            kwargs["message_data"] = message_data
        return await self.handler(**kwargs)


class MCPTool(FunctionTool):
    """MCP 工具

    Attributes:
        mcp_tool: MCP SDK 中的原始工具对象
        mcp_client: 与 MCP 服务器通信的客户端实例
        mcp_server_name: MCP 服务名称
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict | None,
        mcp_tool: mcp.Tool,
        mcp_client: MCPClient,
        mcp_server_name: str,
        concurrent: bool = False,
        background: bool = False,
        active: bool = True,
    ) -> None:
        """初始化 MCP 工具

        Args:
            name: 工具名称
            description: 工具功能描述
            parameters: 工具参数 JSON Schema
            mcp_tool: MCP SDK 原始工具对象
            mcp_client: MCP 客户端实例
            mcp_server_name: MCP 服务名称
            concurrent: 是否允许并发执行
            background: 是否为后台任务
            active: 是否启用
        """
        super().__init__(
            name=name,
            description=description,
            parameters=parameters,
            concurrent=concurrent,
            background=background,
            active=active,
        )
        self.mcp_tool: mcp.Tool = mcp_tool
        """MCP SDK 中的原始工具对象"""
        self.mcp_client: MCPClient = mcp_client
        """与 MCP 服务器通信的客户端实例"""
        self.mcp_server_name: str = mcp_server_name
        """MCP 服务名称"""

    async def execute(
        self, message_data: atriMessageEvent, **kwargs: Any
    ) -> str | CallToolResult:
        """执行 MCP 工具

        通过 MCP 客户端会话调用远程工具,MCP 工具不需要聊天消息上下文

        Args:
            message_data: 未使用（MCP 工具忽略此参数）
            **kwargs: 工具参数

        Returns:
            工具执行结果

        Raises:
            Exception: 当 MCP 客户端或会话不可用时抛出
        """
        if not self.mcp_client or not self.mcp_client.session:
            raise Exception(
                f"MCP 客户端 {self.mcp_server_name} 不可用,"
                f"无法执行工具 {self.name}"
            )
        return await self.mcp_client.session.call_tool(
            self.mcp_tool.name, kwargs
        )


@dataclass(slots=True)
class ToolSet:
    """工具集合,用于管理一组 :class:`FunctionTool` 实例

    提供工具的增删查操作,以及将工具转换为不同 LLM API(OpenAI、Anthropic、
    Google GenAI)所要求的函数调用格式

    Attributes:
        tools: 工具列表
    """

    tools: list[FunctionTool] = field(default_factory=list)
    """工具列表"""

    def empty(self) -> bool:
        """检查工具集合是否为空

        Returns:
            若集合为空返回 ``True``,否则返回 ``False``
        """
        return len(self.tools) == 0

    def add_tool(self, tool: FunctionTool) -> None:
        """向集合中添加工具

        若已存在同名工具,则按以下规则处理：

        - 优先保留 ``active=True`` 的工具
        - 若两者 ``active`` 状态相同,则用新工具覆盖旧工具

        Args:
            tool: 要添加的工具实例
        """
        for i, existing_tool in enumerate(self.tools):
            if existing_tool.name == tool.name:
                existing_active = bool(getattr(existing_tool, "active", True))
                new_active = bool(getattr(tool, "active", True))
                if new_active or not existing_active:
                    self.tools[i] = tool
                return
        self.tools.append(tool)

    def remove_tool(self, name: str) -> None:
        """按名称移除工具

        Args:
            name: 要移除的工具名称
        """
        self.tools = [tool for tool in self.tools if tool.name != name]

    def get_tool(self, name: str) -> FunctionTool | None:
        """按名称获取工具

        Args:
            name: 工具名称

        Returns:
            匹配的工具实例,若未找到则返回 ``None``
        """
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def names(self) -> list[str]:
        """获取所有工具的名称列表

        Returns:
            工具名称字符串列表
        """
        return [tool.name for tool in self.tools]

    def openai_schema(
        self, omit_empty_parameter_field: bool = False
    ) -> list[dict]:
        """将工具转换为 OpenAI API 函数调用格式

        Args:
            omit_empty_parameter_field: 为 ``True`` 时,若工具无参数
                (``properties`` 为空),则省略 ``parameters`` 字段
                默认为 ``False``

        Returns:
            OpenAI API 风格的工具描述字典列表
        """
        result: list[dict] = []
        for tool in self.tools:
            func_def: dict[str, Any] = {
                "type": "function",
                "function": {"name": tool.name},
            }
            if tool.description:
                func_def["function"]["description"] = tool.description

            if tool.parameters is not None:
                if (
                    tool.parameters.get("properties")
                ) or not omit_empty_parameter_field:
                    func_def["function"]["parameters"] = tool.parameters

            result.append(func_def)
        return result

    def anthropic_schema(self) -> list[dict]:
        """将工具转换为 Anthropic API 格式

        Returns:
            Anthropic API 风格的工具描述字典列表
        """
        result: list[dict] = []
        for tool in self.tools:
            input_schema: dict[str, Any] = {"type": "object"}
            if tool.parameters:
                input_schema["properties"] = tool.parameters.get(
                    "properties", {}
                )
                input_schema["required"] = tool.parameters.get("required", [])
            tool_def: dict[str, Any] = {
                "name": tool.name,
                "input_schema": input_schema,
            }
            if tool.description:
                tool_def["description"] = tool.description
            result.append(tool_def)
        return result

    def google_schema(self) -> dict:
        """将工具转换为 Google GenAI API 格式

        内部递归转换 JSON Schema 各字段以适配 Gemini API 的类型系统和
        格式约束处理 ``anyOf`` 组合类型、类型列表回退、数组
        ``items`` 必填等兼容性问题

        Returns:
            Google GenAI API 风格的工具声明字典,包含
            ``function_declarations`` 键
        """

        def convert_schema(schema: dict) -> dict:
            """将 JSON Schema 节点转换为 Gemini API 兼容格式

            处理以下兼容性问题：

            - Gemini 要求 ``type`` 为字符串,不支持列表形式
              （如 ``["string", "null"]``),此时取第一个非 ``"null"`` 类型
            - 过滤 Gemini 不支持的字段（如 ``default``、
              ``additionalProperties``)
            - 数组类型必须包含 ``items`` 定义,缺失时回退为
              ``{"type": "string"}``

            Args:
                schema: 原始 JSON Schema 节点

            Returns:
                Gemini API 兼容的 Schema 节点
            """
            supported_types = {
                "string",
                "number",
                "integer",
                "boolean",
                "array",
                "object",
                "null",
            }
            supported_formats: dict[str, set[str]] = {
                "string": {"enum", "date-time"},
                "integer": {"int32", "int64"},
                "number": {"float", "double"},
            }

            if "anyOf" in schema:
                return {
                    "anyOf": [convert_schema(s) for s in schema["anyOf"]]
                }

            result: dict[str, Any] = {}

            # 确定目标类型,处理列表形式 type 的兼容性
            origin_type = schema.get("type")
            target_type = origin_type

            if isinstance(origin_type, list):
                target_type = next(
                    (t for t in origin_type if t != "null"), "string"
                )

            if target_type in supported_types:
                result["type"] = target_type
                if "format" in schema and schema["format"] in supported_formats.get(
                    result["type"], set()
                ):
                    result["format"] = schema["format"]
            else:
                result["type"] = "null"

            support_fields = {
                "title",
                "description",
                "enum",
                "minimum",
                "maximum",
                "maxItems",
                "minItems",
                "nullable",
                "required",
            }
            result.update(
                {k: schema[k] for k in support_fields if k in schema}
            )

            if "properties" in schema:
                properties: dict[str, Any] = {}
                for key, value in schema["properties"].items():
                    prop_value = convert_schema(value)
                    # Gemini 不支持 default 和 additionalProperties
                    if "default" in prop_value:
                        del prop_value["default"]
                    if "additionalProperties" in prop_value:
                        del prop_value["additionalProperties"]
                    properties[key] = prop_value

                if properties:
                    result["properties"] = properties

            if target_type == "array":
                items_schema = schema.get("items")
                if isinstance(items_schema, dict):
                    result["items"] = convert_schema(items_schema)
                else:
                    # Gemini 要求 array 必须包含 items,缺失时回退
                    result["items"] = {"type": "string"}

            return result

        tools: list[dict[str, Any]] = []
        for tool in self.tools:
            d: dict[str, Any] = {"name": tool.name}
            if tool.description:
                d["description"] = tool.description
            if tool.parameters:
                d["parameters"] = convert_schema(tool.parameters)
            tools.append(d)

        declarations: dict[str, Any] = {}
        if tools:
            declarations["function_declarations"] = tools
        return declarations


    def merge(self, other: ToolSet) -> None:
        """将另一个 ToolSet 合并到当前集合中

        合并规则遵循 :meth:`add_tool` 的覆盖逻辑

        Args:
            other: 要合并的另一个工具集合
        """
        for tool in other.tools:
            self.add_tool(tool)

    def filter_by_names(self, names: list[str]) -> ToolSet:
        """按名称列表筛选工具子集

        Args:
            names: 要保留的工具名称列表

        Returns:
            仅包含匹配名称工具的新 ToolSet 实例
        """
        result = ToolSet()
        names_set = set(names)
        for tool in self.tools:
            if tool.name in names_set:
                result.add_tool(tool)
        return result

    def __len__(self) -> int:
        """返回工具数量"""
        return len(self.tools)

    def __bool__(self) -> bool:
        """若集合非空返回 ``True``"""
        return len(self.tools) > 0

    def __iter__(self):
        """迭代工具列表"""
        return iter(self.tools)

    def __repr__(self) -> str:
        """返回工具集合的字符串表示"""
        return f"ToolSet(tools={self.tools!r})"

    def __str__(self) -> str:
        """返回工具集合的字符串表示"""
        return f"ToolSet(tools={self.tools!r})"