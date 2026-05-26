from unittest.mock import MagicMock, patch

import pytest

from atribot.core.command.command_parsing import CommandSystem


@pytest.fixture
def cmd_system():
    """提供一个挂载Mock容器的 CommandSystem 实例"""
    with patch('atribot.core.command.command_parsing.container') as mock_container:
        mock_container.get.return_value = MagicMock()
        return CommandSystem()

def test_register_command(cmd_system):
    @cmd_system.register_command(name="ping", description="A simple ping command", aliases=["p"])
    def cmd_ping(message_data):
        return "pong"
        
    assert "ping" in cmd_system.command_registry
    assert cmd_system.command_registry["ping"].description == "A simple ping command"
    
    # 测试别名是否生效
    assert "p" in cmd_system.alias_registry
    assert cmd_system.alias_registry["p"] == "ping"

def test_parse_command_options_and_flags(cmd_system):
    @cmd_system.register_command("make")
    @cmd_system.option("file", short="f", long="--file")
    @cmd_system.flag("verbose", short="v", long="--verbose")
    def handler(message_data, file: str, verbose: bool):
        pass
        
    # 使用长选项和Flag
    cmd_name, args = cmd_system._parse_command(["make", "--file", "main.c", "--verbose"])
    assert cmd_name == "make"
    assert args["file"] == "main.c"
    assert args["verbose"] is True
    
    # 使用短选项
    cmd_name2, args2 = cmd_system._parse_command(["make", "-f", "test.c", "-v"])
    assert args2["file"] == "test.c"
    assert args2["verbose"] is True

def test_parse_command_errors(cmd_system):
    @cmd_system.register_command("demo")
    @cmd_system.option("opt", choices=["A", "B"])
    def handler(message_data, opt: str):
        pass
        
    # 测试空命令引发错误
    with pytest.raises(ValueError, match="空命令"):
        cmd_system._parse_command([])
        
    # 测试未知命令
    with pytest.raises(ValueError, match="未知命令.*"):
        cmd_system._parse_command(["unknown_command"])
        
    # 测试提供非法选项值 (choices限制)
    with pytest.raises(ValueError):
        cmd_system._parse_command(["demo", "--opt", "C"])
