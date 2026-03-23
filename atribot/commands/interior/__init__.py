import time
from typing import Optional

from atribot.commands.interior.ai_context import AIContextCommands
from atribot.commands.interior.query_statistics import UserActivityAnalyzer
from atribot.commands.interior.system_monitor import SystemMonitor
from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_type import ChatMessage
from atribot.LLMchat.memory.memory_system import memorySystem

cmd_system:CommandSystem = container.get("CommandSystem")
send_message:QQAPIClient = container.get("SendMessage")
perm_manager:PermissionsManagement = container.get("PermissionsManagement")
memory_system:memorySystem = container.get("memorySystem") 
AIContextCommands()


@cmd_system.register_command(
    name="psql",
    description="查询数据库并生成用户活跃度报告",
    aliases=["查询", "postgresql"],
    examples=[
        "/postgresql 2631018780",
        "/psql",
    ]
)
@cmd_system.argument(
    name="user_id",
    description="要查询的用户ID,qq号,如果没有就会查询命令的执行者",
    required=False,
    type=int
)
async def query_database_command(message_data: ChatMessage, user_id: int = 0):
    """
    查询数据库并生成用户活跃度报告
    
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
async def help_command(message_data: ChatMessage, list: bool = False):
    """
    显示帮助信息
    
    参数:
        message_data: 固定参数
        full: 是否显示完整帮助(FLAG参数)
    """
    if list:
        help_text = cmd_system.get_help_text()
        await send_message.send_group_merge_text(
            group_id = message_data.group_id,
            message = help_text,
            source = "命令list"
        )
    else:
        basic_help = (
            "ATRIbot,版本 2.0.0.1 2025.08.28\n"
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
        await send_message.send_group_message(message_data.group_id,basic_help)





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
    choices=['all', 'sys', 'cpu', 'mem', 'disk', 'mcp', 'model']
)
async def handle_status_command(message_data: ChatMessage, components: list):
    """
    处理状态查询命令，并将结果以合并转发的形式发送。
    """
    group_id = message_data.group_id

    info_str = await SystemMonitor().view_list(components)

    if not info_str.strip():
        await send_message.send_group_message(group_id, "ℹ️ 未生成任何信息，请检查您的输入参数。")
        return

    await send_message.send_group_merge_text(
        group_id, 
        info_str,
        source = "查看信息"
    )



@cmd_system.register_command(
    name="query",
    description="查询记忆库中的相关信息，支持向量+全文混合检索与时间衰减评分，不提供文本会按照时间降序排序",
    aliases=["search", "记忆"],
    authority_level=1,
    examples=[
        "/query 学校的事情",
        "/query 上次讨论的话题 --limit 10",
        "/query 编程相关内容 --group 123456",
        "/query 某人说过什么 --user 789012 --days 7",
        "/query 知识库内容 --kb-only",
        "/query 喜欢的事情 --exclude-kb --category preference",
        "/query 重要的事 --min-importance 5 --no-decay"
    ]
)
@cmd_system.argument(
    name="query_text",
    description="要查询的文本内容",
    required=False,
    multiple=True,
    metavar="TEXT"
)
@cmd_system.option(
    name="limit",
    short="l",
    long="--limit",
    description="返回结果数量",
    type=int,
    default=5,
    metavar="NUM"
)
@cmd_system.option(
    name="group",
    short="g",
    long="--group",
    description="筛选指定群组ID",
    type=int,
    metavar="GROUP_ID"
)
@cmd_system.option(
    name="user",
    short="u",
    long="--user",
    description="筛选指定用户ID",
    type=int,
    metavar="USER_ID"
)
@cmd_system.option(
    name="days",
    short="d",
    long="--days",
    description="查询最近N天的记忆",
    type=int,
    metavar="DAYS"
)
@cmd_system.option(
    name="start_time",
    long="--start",
    description="开始时间戳",
    type=int,
    metavar="TIMESTAMP"
)
@cmd_system.option(
    name="end_time",
    long="--end",
    description="结束时间戳",
    type=int,
    metavar="TIMESTAMP"
)
@cmd_system.flag(
    name="exclude_kb",
    long="--exclude-kb",
    description="排除知识库记忆"
)
@cmd_system.flag(
    name="kb_only",
    long="--kb-only",
    description="只查询知识库记忆"
)
@cmd_system.flag(
    name="no_decay",
    long="--no-decay",
    description="禁用时间衰减，所有类别记忆平等对待"
)
@cmd_system.option(
    name="category",
    short="c",
    long="--category",
    description="筛选记忆类型",
    choices = ["preference","fact","experience","emotion","group_topic","knowledge","domain","guideline"],
    metavar="CATEGORY"
)
@cmd_system.option(
    name="min_importance",
    long="--min-importance",
    description="重要度下界(1-10)",
    type=int,
    default=1,
    metavar="NUM"
)
@cmd_system.option(
    name="min_credibility",
    long="--min_credibility",
    description="可信度度下界(1-10)",
    type=int,
    default=1,
    metavar="NUM"
)
async def cmd_query_memories(
    limit: int,
    group: int,
    user: int,
    days: int,
    start_time: int,
    end_time: int,
    exclude_kb: bool,
    kb_only: bool,
    no_decay: bool,
    category: str,
    min_importance: int,
    min_credibility: int,
    message_data: ChatMessage,
    query_text: list[str] = None,
):
    """查询记忆命令处理函数"""
    from datetime import datetime as dt

    if query_text:
        query_string = " ".join(query_text)
    else:
        query_string = None

    if days is not None:
        end_time = int(time.time())
        start_time = end_time - (days * 24 * 60 * 60)

    group_id = group or None
    decay_weight = 0.0 if no_decay else 0.3

    if query_string:
        results = await memory_system.hybrid_recall(
            query_text=query_string,
            limit=limit,
            group_id=group_id if not kb_only else None,
            user_id=user,
            start_time=start_time,
            end_time=end_time,
            exclude_knowledge_base=exclude_kb,
            only_knowledge_base=kb_only,
            category=category,
            min_importance = min_importance if min_importance > 1 else 1,
            min_credibility = min_credibility if min_credibility > 1 else 1,
            time_decay_weight = decay_weight,
        )
    else:
        results = await memory_system.vector_store.query_memories(
            query_vector=None,
            limit=limit,
            group_id=group_id if not kb_only else None,
            user_id=user,
            start_time=start_time,
            end_time=end_time,
            exclude_knowledge_base=exclude_kb,
            only_knowledge_base=kb_only,
            category=category,
            min_importance = min_importance if min_importance > 1 else 1,
            min_credibility = min_credibility if min_credibility > 1 else 1,
        )

    if not results:
        await send_message.send_group_merge_text(
            message_data.group_id,
            message=f"🔍 未找到与「{query_string or '最近记忆'}」相关的记忆",
            source="记忆查询结果"
        )
        return

    decay_tip = "⏸️ 已禁用时间衰减" if no_decay else "⏱️ 已启用时间衰减评分"
    result_lines = [
        f"🔍 查询字段: 「{query_string or '(没输入查询文本按时间倒序)'}」",
        f"📊 找到 {len(results)} 条相关记忆  {decay_tip}",
        "=" * 10
    ]

    CATEGORY_MAP = {
        "preference": "偏好",
        "fact": "事实", 
        "experience": "经历",
        "emotion": "情感",
        "group_topic": "群话题",
        "knowledge": "知识",
        "domain": "领域知识",
        "guideline": "行为准则"
    }

    for result in results:
        time_str = dt.fromtimestamp(result.get("event_time")).strftime('%Y-%m-%d %H:%M:%S')

        cat = result['category']

        if result.get('hybrid_score'):
            score_str = f"综合评分:{result['hybrid_score']:.4f}"
        elif result.get('distance'):
            score_str = f"向量距离:{result['distance']:.4f}"
        else:
            score_str = ""

        result_lines.append(
            f"\n[记忆ID:{result.get('memory_id')}]"
            f"[{CATEGORY_MAP.get(cat, cat)}]"
            f"重要度:{result['importance']}"
            f"可信度:{result['credibility']}\n{score_str}\n"
            f"⏰ 时间: {time_str}"
        )

        if result.get("user_id"):
            result_lines.append(f"👤 用户: {result['user_id']}")
        if result.get("group_id"):
            result_lines.append(f"👥 群组: {result['group_id']}")

        content = result.get('event', '无内容')
        if len(content) > 300:
            content = content[:300] + "..."
        result_lines.append(f"💭 内容:\n {content}")

    result_lines.append("=" * 10)

    await send_message.send_group_merge_text(
        group_id=message_data.group_id,
        message="\n".join(result_lines),
        source="记忆查询结果"
    )
    

@cmd_system.register_command(
    name='qq',
    description='查看qq账号的一些信息',
    aliases=['账号信息', 'qqProfile'],
    examples=[
        '/qq',
        '/qqProfile 168238719'
    ]
)
@cmd_system.argument(
    name="qq_id",
    description="QQ账号",
    required=False,
    metavar="qq_id",
    type=int
)
async def get_qq_profile(message_data: ChatMessage, qq_id: int = None):

    target_id = qq_id or message_data.user_id

    resp: dict = await send_message.get_stranger_info(target_id)
    
    if not resp or not isinstance(resp, dict) or not resp.get('data'):
        await send_message.send_group_merge_text(
            group_id=message_data["group_id"],
            message=f"⚠️ 哎呀？找不到 QQ:{target_id} 的资料呢，是不是被外星人抓走了？",
            source="系统提示"
        )
        return

    data = resp['data']

    def format_timestamp(timestamp):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)) if timestamp else "未知时间"

    nickname = data.get("nickname", "未知用户")
    display_id = data.get("qid") or target_id 
    age = data.get("age", "秘密")
    sex = data.get("sex", "未知")
    level = data.get("qqLevel", 0)

    is_vip = "👑尊贵会员" if data.get("is_vip") else "✨普通用户"
    if data.get("is_years_vip"): 
        is_vip = "💎年费大佬"
        
    reg_time = format_timestamp(data.get("reg_time", 0))

    country = data.get('country', '')
    province = data.get('province', '')
    city = data.get('city', '')
    location_parts = [p for p in [country, province, city] if p]
    location = "-".join(location_parts) if location_parts else "未知坐标"
    
    sign = data.get("long_nick") or "这个人很懒，什么都没写~"


    card = (
        f"║📂 用户档案 | 🆔 {str(display_id):<14}\n"
        f"╠══════════════════════════════\n"
        f"║ 👤 昵称: {nickname}\n"
        f"║ ⚧  性别: {sex}  | 🎂 年龄: {age}\n"
        f"║ 🌟 等级: Lv.{str(level):<3} | 🏷️ 身份: {is_vip}\n"
        f"║ 🌍 地区: {location}\n"
        f"║ 📅 注册: {reg_time}\n"
        f"╠══════════════════════════════\n"
        f"║ 📝 个性签名:\n"
        f"║ {sign}\n"
    )

    await send_message.send_group_merge_text(
        group_id=message_data.group_id,
        message=card,
        source="QQ账号信息"
    )


@cmd_system.register_command(
    name="reload",
    description="热重载所有命令模块，无需重启 bot",
    aliases=["重载", "reload_commands"],
    authority_level=3,
    examples=[
        "/reload",
    ]
)
async def reload_commands_handler(message_data: ChatMessage) -> None:
    from atribot.core.command.command_loader import command_loader as LoaderType

    loader: LoaderType = container.get("CommandLoader")
    log = container.get("log")
    group_id = message_data.group_id

    await send_message.send_group_message(group_id, "⏳ 正在重载全部命令模块...")

    try:
        loaded_count = loader.reload_commands()
        await send_message.send_group_message(
            group_id,
            f"✅ 命令热重载完成，已加载 {loaded_count} 个命令包。"
        )
        log.info(f"命令热重载完成，操作者: {message_data.user_id}，加载包数: {loaded_count}")
    except Exception as e:
        log.exception(f"命令热重载失败: {e}")
        await send_message.send_group_message(
            group_id,
            f"❌ 命令热重载失败：{e}"
        )
