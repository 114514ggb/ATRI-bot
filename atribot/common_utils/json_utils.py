import json
from typing import Any

import json_repair

# 截断恢复时最多回退尝试的安全点数量
_MAX_SAFE_POINTS = 8


def _extract_json_object(text: str, start: int) -> str | None:
    """从 start 处的 `{` 起线性扫描，提取配对的 JSON 对象（忽略字符串内的括号）。

    Args:
        text (str): 原始文本
        start (int): 起始 `{` 的下标

    Returns:
        str | None: 提取出的 JSON 子串，找不到配对 `}` 时返回 None
    """
    depth = 0
    in_string = False
    escape = False
    n = len(text)
    for i in range(start, n):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_fenced_json_object(text: str) -> str | None:
    """从 ```json / ``` 代码块中提取 `{...}` 对象。

    Args:
        text (str): 原始文本

    Returns:
        str | None: 提取出的 JSON 子串，无合法代码块时返回 None
    """
    n = len(text)
    pos = 0
    while True:
        fence = text.find("```", pos)
        if fence < 0:
            return None
        after = fence + 3
        if text.startswith("json", after):
            after += 4
        while after < n and text[after] in " \t\r\n":
            after += 1
        if after < n and text[after] == "{":
            extracted = _extract_json_object(text, after)
            if extracted is not None:
                close = after + len(extracted)
                while close < n and text[close] in " \t\r\n":
                    close += 1
                if text.startswith("```", close):
                    return extracted
        pos = fence + 3


def _recover_truncated_json(text: str, start: int) -> dict[str, Any] | None:
    """从 start 处被截断的 `{` 起回收最大完整前缀。

    LLM 输出常因 max_tokens 截断：顶层 `{` 找不到配对 `}`。恢复策略是记录扫描中
    每个对象/数组闭合的安全点，截断时从最新安全点向旧回退，截到该处并按括号栈
    补全闭合符，直到 json.loads 成功——这样数组里已完整的元素全部保留，被截断
    的残片确定性丢弃。只认 `}`/`]` 闭合为安全点：字符串值的闭引号不代表一个
    action 结束，若也作为安全点会把 `"decision": "xxx",` 这类残片补成合法对象。

    Args:
        text (str): 原始文本，start 处为顶层对象的 `{`
        start (int): 起始 `{` 的下标

    Returns:
        dict[str, Any] | None: 恢复出的字典，无法恢复时返回 None
    """
    stack: list[str] = []
    in_string = False
    escape = False
    safe_points: list[tuple[int, str]] = []
    n = len(text)
    for i in range(start, n):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c in "{[":
            stack.append(c)
        elif c in "}]":
            # 栈顶与闭括号不配对说明结构错乱，栈弹空说明顶层已闭合，都不属于截断
            if (c == "}") != (stack[-1] == "{"):
                return None
            stack.pop()
            if not stack:
                return None
            safe_points.append((i + 1, "".join("}" if b == "{" else "]" for b in reversed(stack))))
    for end, closers in reversed(safe_points[-_MAX_SAFE_POINTS:]):
        candidate = text[start:end] + closers
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return parsed if isinstance(parsed, dict) else None
    return None


def extract_json_from_text(text: str) -> dict[str, Any] | str:
    """
    尝试解析文本中的JSON字符串为字典。

    逻辑流程（按优先级）：
    1. 尝试将整个文本直接当做JSON解析。
    2. 从 ```json 代码块或首个 `{` 起做配对扫描提取（忽略字符串内的括号）。
    3. 配对失败视为输出被截断，从最后一个完整值处截断并补全闭合符，
       保留已完整的元素、丢弃残片（如 actions 数组里被截断的尾部 action）。
    4. 提取串不合法时用 json_repair 修复；json_repair 对个别残缺输入会抛
       EOFError，此时返回原始文本。

    Args:
        text (str): 包含可能JSON内容的原始文本

    Returns:
        dict[str, Any]: 解析成功的字典（截断恢复时可能只含完整前缀），
        失败时返回原始文本
    """
    try:
        parsed = json.loads(text.strip())
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    extracted_str = _extract_fenced_json_object(text)
    if extracted_str is None:
        brace = text.find("{")
        if brace < 0:
            return text
        extracted_str = _extract_json_object(text, brace)
        if extracted_str is None:
            recovered = _recover_truncated_json(text, brace)
            return recovered if recovered is not None else text

    try:
        return json.loads(extracted_str)
    except json.JSONDecodeError:
        try:
            return json_repair.loads(extracted_str)
        except EOFError:
            return text
