"""SKILL.md 文件的 YAML frontmatter 解析。"""

from pathlib import Path
from typing import Optional

import strictyaml

from .errors import ParseError, ValidationError
from .models import SkillProperties


def find_skill_md(skill_dir: Path) -> Optional[Path]:
    """在技能目录中查找 SKILL.md 文件。

    优先使用大写的 SKILL.md，但也接受小写的 skill.md。

    Args:
        skill_dir: 技能目录的路径

    Returns:
        SKILL.md 文件的路径，如果未找到则返回 None
    """
    for name in ("SKILL.md", "skill.md"):
        path = skill_dir / name
        if path.exists():
            return path
    return None


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """从 SKILL.md 内容中解析 YAML frontmatter。

    Args:
        content: SKILL.md 文件的原始内容

    Returns:
        (元数据字典, Markdown 正文) 的元组

    Raises:
        ParseError: 如果 frontmatter 缺失或无效
    """
    if not content.startswith("---"):
        raise ParseError("SKILL.md 必须以 YAML frontmatter (---) 开头")

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ParseError("SKILL.md frontmatter 未正确以 --- 闭合")

    frontmatter_str = parts[1]
    body = parts[2].strip()

    try:
        parsed = strictyaml.load(frontmatter_str)
        metadata = parsed.data
    except strictyaml.YAMLError as e:
        raise ParseError(f"frontmatter 中的 YAML 无效: {e}")

    if not isinstance(metadata, dict):
        raise ParseError("SKILL.md frontmatter 必须是 YAML 映射")

    if "metadata" in metadata and isinstance(metadata["metadata"], dict):
        metadata["metadata"] = {str(k): str(v) for k, v in metadata["metadata"].items()}

    return metadata, body


def read_properties(skill_dir: Path) -> SkillProperties:
    """从 SKILL.md frontmatter 中读取技能属性。

    此函数解析 frontmatter 并返回属性。
    它不执行完整的验证。请使用 validate() 进行验证。

    Args:
        skill_dir: 技能目录的路径

    Returns:
        包含已解析元数据的 SkillProperties

    Raises:
        ParseError: 如果 SKILL.md 缺失或包含无效的 YAML
        ValidationError: 如果缺少必填字段（name, description）
    """
    skill_dir = Path(skill_dir)
    skill_md = find_skill_md(skill_dir)

    if skill_md is None:
        raise ParseError(f"未在 {skill_dir} 中找到 SKILL.md")

    metadata, _ = parse_frontmatter(skill_md.read_text(encoding='utf-8'))

    if "name" not in metadata:
        raise ValidationError("frontmatter 中缺少必填字段: name")
    if "description" not in metadata:
        raise ValidationError("frontmatter 中缺少必填字段: description")

    name = metadata["name"]
    description = metadata["description"]

    if not isinstance(name, str) or not name.strip():
        raise ValidationError("字段 'name' 必须是非空字符串")
    if not isinstance(description, str) or not description.strip():
        raise ValidationError("字段 'description' 必须是非空字符串")

    return SkillProperties(
        name=name.strip(),
        description=description.strip(),
        path=skill_dir,
        license=metadata.get("license"),
        compatibility=metadata.get("compatibility"),
        allowed_tools=metadata.get("allowed-tools"),
        metadata=metadata.get("metadata"),
    )