"""
atri_memory 查询结果格式化工具
"""
from datetime import datetime
from typing import List

from asyncpg import Record


def _ts(ts: int | float | None) -> str:
    """将时间戳格式化为可读字符串"""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "None"


def format_memory_records(records: List[Record]) -> str:
    """把 atri_memory 查询结果格式化成 AI 易读的文本。

    显示字段:user_id, group_id, event_time, event, category, importance, credibility

    每条格式：
        #1 用户:123456 群组:654321 [2025-06-01 10:00:00] [preference/重要:6/可信:8]
           喜欢吃拉面

    Args:
        records: 查询返回的asyncpg.Record 列表

    Returns:
        格式化后的多行字符串records 为空时返回 "(无数据)"
    """
    if not records:
        return "(无数据)"

    lines = []
    for i, r in enumerate(records, 1):
        user_id = r.get("user_id")
        group_id = r.get("group_id")
        
        src = f"{f'用户:{user_id} ' if user_id else ''}{f'群组:{group_id}' if group_id else ''}" or "知识库"

        lines.append(f"#{i} {src} [{_ts(r['event_time'])}][{r['category']}/重要:{r['importance']}/可信:{r['credibility']}]:{r['event']}")

    return "\n".join(lines)