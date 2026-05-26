from pathlib import Path

import pytest

from atribot.LLMchat.skills.errors import ParseError, ValidationError
from atribot.LLMchat.skills.parser import parse_frontmatter, read_properties


def test_parse_frontmatter():
    valid_content = "---\nname: my_skill\ndescription: Test skill description\nauthor: user\n---\n这里是正文部分\n包含多行"
    
    metadata, body = parse_frontmatter(valid_content)
    
    assert metadata["name"] == "my_skill"
    assert metadata["description"] == "Test skill description"
    assert metadata["author"] == "user"
    assert "这里是正文部分" in body
    
    # 缺少 YAML 头部
    with pytest.raises(ParseError):
        parse_frontmatter("只有正文没有头部")
        
    # 未闭合头部
    with pytest.raises(ParseError):
        parse_frontmatter("---\nname: test")

def test_read_properties(tmp_path: Path):
    # 目录中无 SKILL.md
    with pytest.raises(ParseError):
        read_properties(tmp_path)
        
    # 创建带元数据的正常测试文件
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\nname: my_skill\ndescription: My Description\n---\nBody", encoding="utf-8")
    
    props = read_properties(tmp_path)
    assert props.name == "my_skill"
    assert props.description == "My Description"
    assert props.path == tmp_path
    
    # 缺少必须字段 (name)
    skill_md.write_text("---\ndescription: Desc only\n---\nBody", encoding="utf-8")
    with pytest.raises(ValidationError):
        read_properties(tmp_path)
        
    # name 为空字符串
    skill_md.write_text("---\nname:  \ndescription: Desc\n---\nBody", encoding="utf-8")
    with pytest.raises(ValidationError):
        read_properties(tmp_path)
