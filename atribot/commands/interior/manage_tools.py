from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope
from atribot.LLMchat.MCP.tool_calls import ToolCalls

cmd_system:CommandSystem = container.get("CommandSystem")

@cmd_system.register_command(
    name="tools",
    description="本地工具预设管理",
    authority_level=2,
    aliases=["工具管理"],
    examples=[
        "/tools list - 查看所有工具预设",
        "/tools add_tool <name> <tools> - 向预设中添加工具(逗号分隔)",
        "/tools del_tool <name> <tools> - 从预设中移除工具(逗号分隔)",
        "/tools reload - 重载所有工具预设配置"
    ]
)
@cmd_system.argument(
    name="action", 
    description="操作类型",
    choices = ["list","add_tool","del_tool","reload"],
    required=True, 
    type=str
)
@cmd_system.argument(name="target", description="预设名称", required=False,)
@cmd_system.argument(name="extra_arg", description="工具列表", required=False)
async def manage_tools(message_data: MessageEventEnvelope, action: str, target: str | None = None, extra_arg: str | None = None) -> None:
    send_message = message_data.send_client
    tool_calls_instance: ToolCalls = container.get("ToolCalls")

    if action == "list":
        presets = tool_calls_instance.presets
        if not presets:
            await send_message.send_group_msg(message_data.group_id, "当前没有任何工具预设")
            return
            
        msg = "当前工具预设:\n"
        for name, toolset in presets.items():
            msg += f"- {name}: \n{', '.join(toolset.names())}\n"
            deferred_tools = tool_calls_instance.get_deferred_tools(name)
            if deferred_tools:
                msg += f"  待发现: {', '.join(t.name for t in deferred_tools)}\n"
            msg += "\n"
        await send_message.send_group_merge_text(message_data.group_id, msg.strip(), source="工具预设列表")
        
    elif action == "add_tool":
        if not target or not extra_arg:
            raise ValueError("请指定预设名和要添加的工具列表。\n如: /tools add_tool my_preset tool1,tool2")
            
        tool_list = [t.strip() for t in extra_arg.split(",") if t.strip()]
        await tool_calls_instance.modify_preset_tools(target, "add", tool_list)
        await send_message.send_group_msg(message_data.group_id, f"✅ 预设 '{target}' 增添工具成功")
            
    elif action == "del_tool":
        if not target or not extra_arg:
            raise ValueError("请指定预设名和要移除的工具。\n如: /tools del_tool my_preset tool1,tool2")
            
        tool_list = [t.strip() for t in extra_arg.split(",") if t.strip()]
        await tool_calls_instance.modify_preset_tools(target, "remove", tool_list)
        await send_message.send_group_msg(message_data.group_id, f"✅ 预设 '{target}' 移除工具成功")
            
    elif action == "reload":
        # 全量重载本地工具（含预设重解析与沙盒工具描述/启用状态）
        changed = tool_calls_instance.reload_local_tools()

        await send_message.send_group_msg(
            message_data.group_id,
            "✅ 本地工具已全部重载！"
            + (f"\n已重载 {len(changed)} 个本地工具" if changed else ""),
        )
    else:
        raise ValueError("无效的操作类型。支持的类型有: list, add_tool, del_tool, reload")