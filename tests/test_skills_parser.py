import pytest

from atribot.LLMchat.skills.errors import ParseError
from atribot.LLMchat.skills.parser import parse_frontmatter


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
