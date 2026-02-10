"""Skill validation logic."""

import unicodedata
from pathlib import Path
from typing import Optional

from .errors import ParseError
from .parser import find_skill_md, parse_frontmatter

MAX_SKILL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500

# 根据 Agent Skills 规范允许的前置元数据字段
ALLOWED_FIELDS = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "compatibility",
}



def _validate_name(name: str, skill_dir: Path) -> list[str]:
    """验证技能名称格式和目录匹配。

    技能名称支持国际化字符（Unicode 字母）加连字符。
    名称必须为小写，且不能以连字符开头或结尾。
    """
    errors = []

    if not name or not isinstance(name, str) or not name.strip():
        errors.append("字段 'name' 必须是非空字符串")
        return errors

    name = unicodedata.normalize("NFKC", name.strip())

    if len(name) > MAX_SKILL_NAME_LENGTH:
        errors.append(
            f"技能名称 '{name}' 超出 {MAX_SKILL_NAME_LENGTH} 个字符的限制 "
            f"（当前 {len(name)} 个字符）"
        )

    if name != name.lower():
        errors.append(f"技能名称 '{name}' 必须为小写")

    if name.startswith("-") or name.endswith("-"):
        errors.append("技能名称不能以连字符开头或结尾")

    if "--" in name:
        errors.append("技能名称不能包含连续的连字符")

    if not all(c.isalnum() or c == "-" for c in name):
        errors.append(
            f"技能名称 '{name}' 包含无效字符。"
            "仅允许字母、数字和连字符。"
        )

    if skill_dir:
        dir_name = unicodedata.normalize("NFKC", skill_dir.name)
        if dir_name != name:
            errors.append(
                f"目录名称 '{skill_dir.name}' 必须与技能名称 '{name}' 一致"
            )

    return errors


def _validate_description(description: str) -> list[str]:
    """验证描述格式。"""
    errors = []

    if not description or not isinstance(description, str) or not description.strip():
        errors.append("字段 'description' 必须是非空字符串")
        return errors

    if len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append(
            f"描述超出 {MAX_DESCRIPTION_LENGTH} 个字符的限制 "
            f"（当前 {len(description)} 个字符）"
        )

    return errors


def _validate_compatibility(compatibility: str) -> list[str]:
    """验证兼容性格式。"""
    errors = []

    if not isinstance(compatibility, str):
        errors.append("字段 'compatibility' 必须是字符串")
        return errors

    if len(compatibility) > MAX_COMPATIBILITY_LENGTH:
        errors.append(
            f"兼容性说明超出 {MAX_COMPATIBILITY_LENGTH} 个字符的限制 "
            f"（当前 {len(compatibility)} 个字符）"
        )

    return errors


def _validate_metadata_fields(metadata: dict) -> list[str]:
    """验证仅存在允许的字段。"""
    errors = []

    extra_fields = set(metadata.keys()) - ALLOWED_FIELDS
    if extra_fields:
        errors.append(
            f"前置元数据中存在意外字段：{', '.join(sorted(extra_fields))}。"
            f"仅允许 {sorted(ALLOWED_FIELDS)}。"
        )

    return errors

def validate_metadata(metadata: dict, skill_dir: Optional[Path] = None) -> list[str]:
    """验证已解析的技能元数据。

    这是核心验证函数，作用于已解析的元数据，
    避免从解析器调用时产生重复的文件 I/O 操作。

    Args:
        metadata: 解析后的 YAML 前置元数据字典
        skill_dir: 技能目录的可选路径（用于检查名称与目录是否匹配）

    Returns:
        验证错误消息列表。空列表表示验证通过。
    """
    errors = []
    errors.extend(_validate_metadata_fields(metadata))

    if "name" not in metadata:
        errors.append("前置元数据中缺少必填字段：name")
    else:
        errors.extend(_validate_name(metadata["name"], skill_dir))

    if "description" not in metadata:
        errors.append("前置元数据中缺少必填字段：description")
    else:
        errors.extend(_validate_description(metadata["description"]))

    if "compatibility" in metadata:
        errors.extend(_validate_compatibility(metadata["compatibility"]))

    return errors


def validate(skill_dir: Path) -> list[str]:
    """验证技能目录。

    Args:
        skill_dir: 技能目录的路径

    Rteurns:
        验证错误消息列表。空列表表示验证通过。
    """
    skill_dir = Path(skill_dir)

    if not skill_dir.exists():
        return [f"路径不存在：{skill_dir}"]

    if not skill_dir.is_dir():
        return [f"不是目录：{skill_dir}"]

    skill_md = find_skill_md(skill_dir)
    if skill_md is None:
        return ["缺少必需文件：SKILL.md"]

    try:
        metadata, _ = parse_frontmatter(skill_md.read_text(encoding='utf-8'))
    except ParseError as e:
        return [str(e)]

    return validate_metadata(metadata, skill_dir)