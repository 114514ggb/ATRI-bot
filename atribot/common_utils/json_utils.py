import json
import re
from typing import Any

import json_repair


def extract_json_from_text(text: str) -> dict[str, Any] | str:
    """
    尝试解析文本中的JSON字符串为字典。
    
    逻辑流程：
    1. 尝试将整个文本直接当做JSON解析。
    2. 如果失败，尝试使用正则从文本中提取JSON片段（支持Markdown代码块或直接的大括号包裹内容）。
    3. 提取成功后再次尝试解析。
    4. 如果所有尝试都失败，返回原始文本。
    
    Args:
        text (str): 包含可能JSON内容的原始文本
        
    Returns:
        Dict[str, Any]: 解析成功的字典，或在失败时返回 {}
    """
    # try:
    #     return json.loads(text)
    # except json.JSONDecodeError:
    #     pass  
    
    extracted_str = None

    if match := re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        extracted_str = match.group(1)
    elif match := re.search(r"\{.*\}", text, re.DOTALL):
        extracted_str = match.group(0)

    if not extracted_str:
        return text

    try:
        return json.loads(extracted_str)
    except json.JSONDecodeError:
        return json_repair.loads(extracted_str)
