import time

from atribot.core.command.command_parsing import CommandSystem
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage
from atribot.LLMchat.memory.memory_system import memorySystem

cmd_system: CommandSystem = container.get("CommandSystem")
send_message: QQAPIClient = container.get("SendMessage")
memory_system: memorySystem = container.get("memorySystem")


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
    choices=["preference", "fact", "experience", "emotion", "group_topic", "knowledge", "domain", "guideline"],
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
            min_importance=min_importance if min_importance > 1 else 1,
            min_credibility=min_credibility if min_credibility > 1 else 1,
            time_decay_weight=decay_weight,
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
            min_importance=min_importance if min_importance > 1 else 1,
            min_credibility=min_credibility if min_credibility > 1 else 1,
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
