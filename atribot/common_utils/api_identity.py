"""LLM API 请求侧 user_id 的生成规则

user_id 用于供应商侧的账号级隔离（内容安全 / KVCache / 调度），
只使用字母、数字与下划线，满足常见供应商的字符集与 512 字节长度限制。
"""

from uuid import uuid4

PRIVATE_USER_PREFIX = "u_"
"""私聊的前缀"""

GROUP_USER_PREFIX = "group_"
"""群聊共享上下文时的前缀"""

SUB_AGENT_ID_BASE = "atri"
"""拿不到父对话 user_id 时子代理的回退基名"""

SUB_AGENT_ID_RANDOM_LENGTH = 8
"""子代理随机后缀长度"""


def private_api_user_id(user_id: int | str) -> str:
    """私聊维度的 user_id

    Args:
        user_id: 用户 QQ 号（或 WebUI 面板的虚拟用户号）

    Returns:
        str: 形如 ``u_123456789``
    """
    return f"{PRIVATE_USER_PREFIX}{user_id}"


def group_api_user_id(group_id: int | str) -> str:
    """群聊维度的 user_id

    Args:
        group_id: 群号

    Returns:
        str: 形如 ``group_123456789``
    """
    return f"{GROUP_USER_PREFIX}{group_id}"


def derive_chat_api_user_id(
    group_id: int | None,
    user_id: int | str | None,
    user_global_context: bool,
) -> str | None:
    """按会话场景与上下文模式推导聊天请求的 user_id

    与 `ChatManager` 取上下文的规则保持一致：私聊与 `user_global_context=True`
    的群聊使用各自的私聊上下文，此时按用户隔离；共享群聊上下文时按群隔离。

    Args:
        group_id: 群号，私聊为 None
        user_id: 触发消息的用户，未知时为 None
        user_global_context: 群聊是否使用每人独立上下文

    Returns:
        str | None: 推导出的 user_id；群聊共享上下文但缺少群号时返回 None
    """
    if user_id is None:
        return group_api_user_id(group_id) if group_id is not None else None
    if group_id is None or user_global_context:
        return private_api_user_id(user_id)
    return group_api_user_id(group_id)


def sub_agent_api_user_id(parent_user_id: str | None) -> str:
    """子代理请求的 user_id：父对话 id 加随机后缀，与父对话隔离

    Args:
        parent_user_id: 父对话的 user_id

    Returns:
        str: 形如 ``u_123456789_sub_ab12cd34``
    """
    base = parent_user_id or SUB_AGENT_ID_BASE
    suffix = uuid4().hex[:SUB_AGENT_ID_RANDOM_LENGTH]
    return f"{base}_sub_{suffix}"
