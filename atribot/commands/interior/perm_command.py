from typing import Optional

from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage

cmd_system: CommandSystem = container.get("CommandSystem")
send_message: QQAPIClient = container.get("SendMessage")
perm_manager: PermissionsManagement = container.get("PermissionsManagement")


@cmd_system.register_command(
    name="perm",
    description="权限管理",
    aliases=["permission", "权限"],
    authority_level=1,
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
    message_data: ChatMessage,
    subcommand: str,
    role: Optional[str] = None,
    user_id: Optional[int] = None
):
    """
    权限管理命令分发器
    """
    group_id = message_data.group_id
    operator_id = message_data.user_id

    async def reply_func(msg):
        await send_message.send_group_msg(group_id, msg)

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
