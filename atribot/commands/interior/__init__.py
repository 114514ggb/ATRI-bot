from atribot.core.command.async_permissions_management import permissions_management
from atribot.commands.interior.mysql_query_statistics import UserActivityAnalyzer
from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.commands.interior.ai_context import AIContextCommands
from atribot.commands.interior.system_monitor import SystemMonitor
from atribot.core.command.command_parsing import command_system
from atribot.core.service_container import container
from typing import Optional


cmd_system:command_system = container.get("CommandSystem")
send_message:qq_send_message = container.get("SendMessage")
perm_manager:permissions_management = container.get("PermissionsManagement")
AIContextCommands()


@cmd_system.register_command(
    name="qmysql",
    description="查询数据库并生成用户活跃度报告",
    aliases=["查询", "mysql"],
    examples=[
        "/mysql 2631018780",
        "/qmysql",
    ]
)
@cmd_system.argument(
    name="user_id",
    description="要查询的用户ID,qq号",
    required=False,
    type=int
)
async def query_mysql_command(message_data: dict, user_id: int = 0):
    """
    查询MySQL数据库并生成用户活跃度报告
    
    参数:
        message_data: 所有命令固定传入参数
        user_id: 要查询的用户ID，如果没有就会查询命令的执行者
    """
    analyzer = UserActivityAnalyzer()
    await analyzer.query_mysql(message_data=message_data, user_id=user_id)

    
@cmd_system.register_command(
    name="help",
    description="显示帮助信息",
    aliases=["帮助"],
    examples=[
        "/help",
        "/help -l",
        "/help --list"
    ],
    authority_level = 0
)
@cmd_system.flag(
    name="list",
    short="l",
    long="--list",
    description="显示支持的所有命令"
)
async def help_command(message_data: dict, list: bool = False):
    """
    显示帮助信息
    
    参数:
        message_data: 固定参数
        full: 是否显示完整帮助(FLAG参数)
    """
    group_id = message_data["group_id"]
    if list:
        help_text = cmd_system.get_help_text()
        await send_message.send_group_merge_forward(
            group_id = group_id,
            message = help_text,
            source = "命令list"
        )
    else:
        basic_help = (
            "ATRIbot,版本 2.0.0.1"
            "所有命令以开头要@bot再以\"/\"开头才能使用\n"
            "输入 /help --list 查看完整命令列表\n"
            "输入 /help <命令名> 查看特定命令帮助\n\n"
            "任意命令加入 --help 参数可以查看该命令的帮助信息"
            "基本功能:\n"
            "1.@bot后接文字就可以聊天\n"
            "2.@bot后以/开头接[命令]即可触发命令.\n"
            "3.会对群出现的一些词进行反应。\n"
            "4.会对交互数据进行存储，可能会对其用于分析，服务质量优化和功能迭代。\n"
        )
        await send_message.send_group_message(group_id,basic_help)





@cmd_system.register_command(
    name="perm",
    description="权限管理",
    aliases=["permission", "权限"],
    authority_level= 1,
    usage="/perm <add|remove|list|my> [参数...]",
    examples=[
        "/perm add admin 12345678",
        "/perm remove blacklist 87654321",
        "/perm list",
        "/perm my"
    ]
)
@cmd_system.argument(
    name="subcommand",
    description="执行的操作 (add, remove, list, my)",
    required=True,
    choices=["add", "remove", "list", "my"]
)
@cmd_system.argument(
    name="role",
    description="目标权限角色 (admin, blacklist)",
    required=False,
    choices=["admin", "blacklist"]
)
@cmd_system.argument(
    name="user_id",
    description="目标用户的QQ号",
    required=False,
    type=int
)
async def permission_command_handler(
    message_data: dict, 
    subcommand: str, 
    role: Optional[str] = None, 
    user_id: Optional[int] = None
):
    """
    权限管理命令分发器
    """
    group_id = message_data["group_id"]
    operator_id = message_data["user_id"]
    async def reply_func(msg):
        await send_message.send_group_message(group_id, msg)
        
    if subcommand == "add":
        if not role or not user_id:
            await reply_func("用法错误：/perm add <role> <user_id>")
            return
        
        if role == "admin":
            await perm_manager.add_administrator(user_id, operator_id)
            await reply_func(f"操作成功：已将用户 {user_id} 添加为管理员。")
        elif role == "blacklist":
            await perm_manager.add_to_blacklist(user_id, operator_id)
            await reply_func(f"操作成功：已将用户 {user_id} 添加到黑名单。")

    elif subcommand == "remove":
        if not role or not user_id:
            await reply_func("用法错误：/perm remove <role> <user_id>")
            return

        if role == "admin":
            await perm_manager.delete_administrator(user_id, operator_id)
            await reply_func(f"操作成功：已移除用户 {user_id} 的管理员权限。")
        elif role == "blacklist":
            await perm_manager.remove_from_blacklist(user_id, operator_id)
            await reply_func(f"操作成功：已将用户 {user_id} 从黑名单中移除。")

    elif subcommand == "list":
        root, admin = perm_manager.view_permissions()
        blacklist = perm_manager.blacklist
        
        response = "权限列表：\n"
        response += f" - Root ({len(root)}): {', '.join(map(str, root))}\n"
        response += f" - 管理员 ({len(admin)}): {', '.join(map(str, admin)) or '无'}\n"
        response += f" - 黑名单 ({len(blacklist)}): {', '.join(map(str, blacklist)) or '无'}"
        await reply_func(response)

    elif subcommand == "my":
        my_role = perm_manager.get_my_permission(operator_id)
        await reply_func(f"您好，{operator_id}。\n您当前的权限角色是：{my_role}")
        
        
        
        
        

@cmd_system.register_command(
    name='show',
    description='查看服务器的详细系统状态信息',
    aliases=['查看', 'list'],
    examples=[
        '/show all',
        '/show cpu mem'
    ]
)
@cmd_system.argument(
    'components',
    description='要查看的系统组件',
    required=True,
    multiple=True,
    choices=['all', 'sys', 'cpu', 'mem', 'disk', 'mcp']
)
async def handle_status_command(message_data: dict, components: list):
    """
    处理状态查询命令，并将结果以合并转发的形式发送。
    """
    group_id = message_data['group_id']

    info_str = await SystemMonitor().view_list(components)

    if not info_str.strip():
        await send_message.send_group_message(group_id, "ℹ️ 未生成任何信息，请检查您的输入参数。")
        return

    await send_message.send_group_merge_forward(
        group_id, 
        info_str,
        source = "查看信息"
    )

