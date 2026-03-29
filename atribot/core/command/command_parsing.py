import inspect
import logging
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from atribot.common_utils import jaro_winkler_similarity
from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage


class ParamType(Enum):
    """参数类型枚举"""
    POSITIONAL = "positional"
    """位置参数
    
    基础参数类型
    必须按照预设的顺序提供这些参数，它们通过其在命令行中的“位置”来被识别
    """
    OPTION = "option"
    """选项参数
    
    前面有个标志符，后面通常跟一个值。
    """
    FLAG = "flag"
    """标志参数
    
    用于表示一个布尔状态。它只需要名字，
    不需要跟任何值。它的出现本身就代表“真”，不出现则代表“假”。
    """


@dataclass
class CommandParam:
    """命令参数元数据"""
    name: str
    """参数名称"""
    type: Type = str
    """参数类型"""
    default: Any = None
    """默认值"""
    required: bool = False
    """是否必填"""
    param_type: ParamType = ParamType.POSITIONAL
    """参数类型"""
    short_option: Optional[str] = None
    """短选项格式"""
    long_option: Optional[str] = None
    """长选项格式"""
    description: str = ""
    """参数描述"""
    choices: Optional[List[str]] = None
    """可选值列表"""
    metavar: Optional[str] = None
    """帮助文档中显示的参数名"""
    multiple: bool = False
    """是否接受多个值"""
    
    def __post_init__(self):
        if self.param_type == ParamType.FLAG:
            self.type = bool
            self.default = False
        if self.long_option is None and self.param_type in (ParamType.OPTION, ParamType.FLAG):
            self.long_option = f"--{self.name.replace('_', '-')}"


@dataclass
class Command:
    """指令元数据容器"""
    name: str
    """名称"""
    handler: Callable
    """处理函数"""
    aliases: List[str] = field(default_factory=list)
    """别名"""
    description: str = "无可用描述"
    """一个对命令的描述"""
    params: Dict[str, CommandParam] = field(default_factory=dict)
    """参数字典"""
    authority_level: int = 1
    """执行需要的权限等级"""
    cooldown: int = 0
    """冷却时间（单位秒）"""
    usage: Optional[str] = None
    """自定义用法说明"""
    examples: List[str] = field(default_factory=list)
    """使用示例"""
    _decorators_processed: bool = False
    """标记是否已处理装饰器"""
    
    def __post_init__(self):
        """自动提取处理函数的参数信息"""
        sig = inspect.signature(self.handler)
        for name, param in sig.parameters.items():
            if name in ["self","message_data"]:
                continue
                
            if name not in self.params:
                cmd_param = CommandParam(
                    name=name,
                    type=param.annotation if param.annotation != inspect.Parameter.empty else str,
                    default=param.default if param.default != inspect.Parameter.empty else None,
                    required=param.default == inspect.Parameter.empty
                )
                self.params[name] = cmd_param

    def add_param(self, name: str, **kwargs):
        """添加/覆盖参数元数据"""
        if name in self.params:
            for k, v in kwargs.items():
                setattr(self.params[name], k, v)
        else:
            self.params[name] = CommandParam(name=name, **kwargs)
    
    def get_usage_string(self) -> str:
        """生成用法字符串"""
        if self.usage:
            return self.usage
            
        usage_parts = [f"/{self.name}"]
        
        # 添加选项和标志
        options = [p for p in self.params.values() if p.param_type in (ParamType.OPTION, ParamType.FLAG)]
        if options:
            optional_opts = []
            required_opts = []
            
            for param in options:
                if param.param_type == ParamType.FLAG:
                    short_part = f"-{param.short_option}" if param.short_option else ""
                    long_part = param.long_option or ""
                    if short_part and long_part:
                        opt_str = f"[{short_part}|{long_part}]"
                    else:
                        opt_str = f"[{short_part or long_part}]"
                else:
                    metavar = param.metavar or param.name.upper()
                    long_part = param.long_option or ""
                    opt_str = f"{long_part} {metavar}"
                    if not param.required:
                        opt_str = f"[{opt_str}]"
                
                if param.required:
                    required_opts.append(opt_str)
                else:
                    optional_opts.append(opt_str)
            
            usage_parts.extend(required_opts + optional_opts)
        
        # 添加位置参数
        positionals = [p for p in self.params.values() if p.param_type == ParamType.POSITIONAL]
        for param in positionals:
            metavar = param.metavar or param.name.upper()
            if param.multiple:
                metavar = f"{metavar}..."
            if not param.required:
                metavar = f"[{metavar}]"
            usage_parts.append(metavar)
        
        return " ".join(usage_parts)




class CommandSystem:
    """命令系统主类"""
    
    def __init__(self):
        self.log:logging = container.get("log")
        self.permissions_management:PermissionsManagement = container.get("PermissionsManagement")
        self.send_message:QQAPIClient = container.get("SendMessage")
        self.command_registry: Dict[str, Command] = {}
        self.alias_registry: Dict[str, str] = {}  # 别名映射
        self.log.info("CommandSystem已初始化!")
    
    def register_command(
        self, 
        name: str, 
        description: str = "无可用描述",
        aliases: Optional[List[str]] = None,
        usage: Optional[str] = None,
        examples: Optional[List[str]] = None,
        authority_level: int = 1
    ) -> Callable:
        """装饰器：注册指令处理器
        
        Args:
            name (str): 命令名称
            description (str): 命令描述，默认为"无可用描述"
            aliases (Optional[List[str]]): 命令别名列表，默认为None
            usage (Optional[str]): 自定义用法说明，默认为None
            examples (Optional[List[str]]): 使用示例列表，默认为None
            authority_level (int): 执行需要的最低权限等级
        """
        def decorator(func: Callable) -> Callable:
            command = Command(
                name=name, 
                handler=func, 
                description=description,
                aliases=aliases or [],
                usage=usage,
                examples=examples or [],
                authority_level= authority_level
            )
            
            if name in self.command_registry:
                self.log.warning(f"警告：指令 '{name}' 已被覆盖。")
                pass
            
            self.command_registry[name] = command
            
            for alias in command.aliases:
                if alias in self.alias_registry:
                    self.log.warning(f"警告：别名 '{alias}' 已被覆盖。")
                    pass
                self.alias_registry[alias] = name
            
            return func
        return decorator
    
    def option(
        self,
        name: str, 
        short: Optional[str] = None,
        long: Optional[str] = None, 
        description: str = "", 
        required: bool = False, 
        default: Any = None,
        choices: Optional[List[str]] = None,
        metavar: Optional[str] = None,
        multiple: bool = False,
        type: Type = str
    ):
        """装饰器：为命令添加选项参数
        
        Args:
            name (str): 参数名称
            short (Optional[str]): 短选项前缀，如"-v"，默认为None
            long (Optional[str]): 长选项前缀，如"--verbose"，默认为None
            description (str): 参数描述，默认为空字符串
            required (bool): 是否为必需参数，默认为False
            default (Any): 默认值，默认为None
            choices (Optional[List[str]]): 可选值列表，默认为None
            metavar (Optional[str]): 帮助文档中显示的参数名，默认为None
            multiple (bool): 是否接受多个值，默认为False
            type (Type): 参数类型，默认为str
        """
        def decorator(func: Callable) -> Callable:
            if not hasattr(func, "_command_params"):
                func._command_params = []
                
            func._command_params.append({
                "name": name,
                "param_type": ParamType.OPTION,
                "short_option": short,
                "long_option": long or f"--{name.replace('_', '-')}",
                "description": description,
                "required": required,
                "default": default,
                "choices": choices,
                "metavar": metavar,
                "multiple": multiple,
                "type": type
            })
            return func
        return decorator
    
    def flag(
        self,
        name: str,
        short: Optional[str] = None,
        long: Optional[str] = None,
        description: str = ""
    ):
        """装饰器：为命令添加标志参数
        
        Args:
            name (str): 标志名称
            short (Optional[str]): 短选项前缀，如"v"，默认为None
            long (Optional[str]): 长选项前缀，如"--verbose"，默认为None
            description (str): 标志描述，默认为空字符串
        """
        def decorator(func: Callable) -> Callable:
            if not hasattr(func, "_command_params"):
                func._command_params = []
                
            func._command_params.append({
                "name": name,
                "param_type": ParamType.FLAG,
                "short_option": short,
                "long_option": long or f"--{name.replace('_', '-')}",
                "description": description,
                "default": False,
                "type": bool
            })
            return func
        return decorator
    
    def argument(
        self,
        name: str,
        description: str = "",
        required: bool = True,
        choices: Optional[List[str]] = None,
        metavar: Optional[str] = None,
        multiple: bool = False,
        type: Type = str
    ):
        """装饰器：为命令添加位置参数
        
        Args:
            name (str): 参数名称
            description (str): 参数描述，默认为空字符串
            required (bool): 是否为必需参数，默认为True
            choices (Optional[List[str]]): 可选值列表，默认为None
            metavar (Optional[str]): 帮助文档中显示的参数名，默认为None
            multiple (bool): 是否接受多个值，默认为False
            type (Type): 参数类型，默认为str
        """
        def decorator(func: Callable) -> Callable:
            if not hasattr(func, "_command_params"):
                func._command_params = []
                
            func._command_params.append({
                "name": name,
                "param_type": ParamType.POSITIONAL,
                "description": description,
                "required": required,
                "choices": choices,
                "metavar": metavar,
                "multiple": multiple,
                "type": type
            })
            return func
        return decorator
    
    def _process_command_decorators(self, command: Command):
        """处理函数上的装饰器元数据"""
        if command._decorators_processed:
            return
            
        func = command.handler
        
        # 处理装饰器定义的参数
        if hasattr(func, "_command_params"):
            for param_def in func._command_params:
                command.add_param(param_def["name"], **{k: v for k, v in param_def.items() if k != "name"})
        
        command._decorators_processed = True
    
    def _convert_value(self, value: str, param_type: Type) -> Any:
        """类型转换"""
        if param_type is bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif param_type is int:
            return int(value)
        elif param_type is float:
            return float(value)
        else:
            return str(value)
    
    def _parse_command(self, tokens: List[str]) -> tuple[str, Dict[str, Any]]:
        """解析命令tokens，返回命令名和参数字典"""
        if not tokens:
            raise ValueError("空命令")
        
        command_name = tokens[0]
        args = tokens[1:]
        
        # 处理别名
        if command_name in self.alias_registry:
            command_name = self.alias_registry[command_name]
        
        if command_name not in self.command_registry:
            suggestions = self._get_similar_commands(command_name)
            error_msg = f"未知命令: {command_name}"
            if suggestions:
                error_msg += f"\n你是否想输入: \n{', '.join(suggestions)}"
            raise ValueError(error_msg)
        
        command = self.command_registry[command_name]
        self._process_command_decorators(command)
        
        if "--help" in args or "-h" in args:
            return command_name, {"_help": True}
        
        parsed_args = {}
        for name, param in command.params.items():
            if param.param_type == ParamType.FLAG:
                parsed_args[name] = False
            elif param.multiple:
                parsed_args[name] = []
            else:
                parsed_args[name] = param.default
        
        positionals = []
        i = 0
        
        while i < len(args):
            token = args[i]
            
            # 处理长选项
            if token.startswith("--"):
                if "=" in token:
                    option_part, value = token.split("=", 1)
                else:
                    option_part = token
                    value = None
                
                # 查找对应的参数
                param = None
                for p in command.params.values():
                    if p.long_option == option_part:
                        param = p
                        break
                
                if not param:
                    raise ValueError(f"未知选项: {option_part}")
                
                if param.param_type == ParamType.FLAG:
                    parsed_args[param.name] = True
                else:
                    if value is None:
                        if i + 1 >= len(args):
                            raise ValueError(f"选项 {option_part} 需要参数值")
                        value = args[i + 1]
                        i += 1
                    
                    # 验证choices
                    if param.choices and value not in param.choices:
                        raise ValueError(f"选项 {option_part} 的值必须是 {param.choices} 之一")
                    
                    converted_value = self._convert_value(value, param.type)
                    if param.multiple:
                        parsed_args[param.name].append(converted_value)
                    else:
                        parsed_args[param.name] = converted_value
            
            # 处理短选项
            elif token.startswith("-") and len(token) > 1:
                flags = token[1:]
                
                for j, flag in enumerate(flags):
                    # 查找对应的参数
                    param = None
                    for p in command.params.values():
                        if p.short_option == flag:
                            param = p
                            break
                    
                    if not param:
                        raise ValueError(f"未知选项: -{flag}")
                    
                    if param.param_type == ParamType.FLAG:
                        parsed_args[param.name] = True
                    else:
                        # 短选项的值处理
                        if j == len(flags) - 1:  # 最后一个字符
                            if i + 1 >= len(args):
                                raise ValueError(f"选项 -{flag} 需要参数值")
                            value = args[i + 1]
                            i += 1
                        else:
                            raise ValueError(f"选项 -{flag} 需要参数值，不能与其他短选项组合")
                        
                        if param.choices and value not in param.choices:
                            raise ValueError(f"选项 -{flag} 的值必须是 {param.choices} 之一")
                        
                        converted_value = self._convert_value(value, param.type)
                        if param.multiple:
                            parsed_args[param.name].append(converted_value)
                        else:
                            parsed_args[param.name] = converted_value
            
            # 位置参数
            else:
                positionals.append(token)
            
            i += 1
        
        # 分配位置参数
        positional_params = [
            p for p in command.params.values() 
            if p.param_type == ParamType.POSITIONAL
        ]
        
        # 按定义顺序排序位置参数
        positional_params.sort(key=lambda p: list(command.params.keys()).index(p.name))
        
        pos_index = 0
        for param in positional_params:
            if param.multiple:
                # 多值位置参数获取剩余所有位置参数
                remaining_positionals = positionals[pos_index:]
                if param.required and not remaining_positionals:
                    raise ValueError(f"缺少必需参数: {param.name}")
                parsed_args[param.name] = [self._convert_value(val, param.type) for val in remaining_positionals]
                break
            else:
                if pos_index < len(positionals):
                    value = positionals[pos_index]
                    if param.choices and value not in param.choices:
                        raise ValueError(f"参数 {param.name} 的值必须是 {param.choices} 之一")
                    parsed_args[param.name] = self._convert_value(value, param.type)
                    pos_index += 1
                elif param.required:
                    raise ValueError(f"缺少必需参数: {param.name}")
        
        # 验证必需参数
        for name, param in command.params.items():
            if param.required and (parsed_args[name] is None or 
                (param.multiple and not parsed_args[name])):
                if param.param_type == ParamType.POSITIONAL:
                    raise ValueError(f"缺少必需参数: {param.name}")
                else:
                    option_str = param.long_option or f"-{param.short_option}"
                    raise ValueError(f"缺少必需选项: {option_str}")
        
        return command_name, parsed_args
    
    def _get_similar_commands(self, command_name: str, max_suggestions: int = 3) -> List[str]:
        """获取相似的命令建议"""
        
        all_commands = list(self.command_registry.keys()) + list(self.alias_registry.keys())
        
        matches = []
        for cmd in all_commands:
            similarity = jaro_winkler_similarity(command_name.lower(), cmd.lower())
            
            if similarity >= 0.8:
                matches.append((cmd, similarity))
                
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return [cmd for cmd, _ in matches[:max_suggestions]]
    
    async def dispatch_command(self, chat_message:ChatMessage) -> bool:
        """解析并分发指令，会直接抛出命令执行的错误"""
        
        tokens = shlex.split(chat_message.pure_text[1:])
        if not tokens:
            raise TypeError("空命令,请输入有效命令哦！")
        
        command_name, parsed = self._parse_command(tokens)
        
        command = self.command_registry[command_name]
        
        if parsed.get("_help"):
            await self.send_message.send_group_merge_text(
                group_id = chat_message.group_id,
                message = self._get_command_help(command),
                source = "命令的帮助信息"
            )
            return 
        
        if self.permissions_management.has_permission(chat_message.user_id,command.authority_level):#判断权限
            
            filtered_args = {k: v for k, v in parsed.items() if not k.startswith("_")}
            
            await command.handler(**filtered_args,message_data = chat_message)

            
    def _get_command_help(self, command: Command) -> str:
        """获取单个命令的帮助信息"""
        help_lines = []
        
        level = ["blacklist","tourist","administrator","root"]
        
        help_lines.append("✨" * 10)
        help_lines.append(f"🔹 命令: {command.name} 🔹")
        if command.aliases:
            help_lines.append(f"📛 别名: {', '.join(command.aliases)}")
        help_lines.append(f"🔐 执行权限: 最低{level[command.authority_level]}")    
        help_lines.append(f"📝 描述: {command.description}")
        help_lines.append("✨" * 10)
        help_lines.append("")
        
        help_lines.append("🚀 用法:")
        help_lines.append(f"  💻 {command.get_usage_string()}")
        help_lines.append("")
        
        if command.params:
            positionals = [p for p in command.params.values() if p.param_type == ParamType.POSITIONAL]
            if positionals:
                help_lines.append("📍 位置参数:")
                for param in positionals:
                    desc = param.description
                    if param.choices:
                        desc += f" (选项: {', '.join(param.choices)})"
                    help_lines.append(f"  🎯 {param.name:<15} {desc}")
                help_lines.append("")
            
            options = [p for p in command.params.values() if p.param_type == ParamType.OPTION]
            if options:
                help_lines.append("⚙️ 选项:")
                for param in options:
                    opts = []
                    if param.short_option:
                        opts.append(f"{param.short_option}")
                    if param.long_option:
                        opts.append(f"{param.long_option}")
                    
                    opt_str = ", ".join(opts)
                    if param.metavar:
                        opt_str += f" {param.metavar}"
                    
                    desc = param.description
                    if param.default is not None:
                        desc += f" (默认: {param.default})"
                    if param.choices:
                        desc += f" (选项: {', '.join(param.choices)})"
                    
                    help_lines.append(f"  🔘 {opt_str:<25} {desc}")
                help_lines.append("")
            
            flags = [p for p in command.params.values() if p.param_type == ParamType.FLAG]
            if flags:
                help_lines.append("🏁 标志:")
                for param in flags:
                    opts = []
                    if param.short_option:
                        opts.append(f"{param.short_option}")
                    if param.long_option:
                        opts.append(f"{param.long_option}")
                    
                    opt_str = ", ".join(opts)
                    help_lines.append(f"  🎚️ {opt_str:<25} {param.description}")
                help_lines.append("")
        
        if command.examples:
            help_lines.append("🌠 示例:")
            for i, example in enumerate(command.examples, 1):
                help_lines.append(f"  {i}. 💡 {example}")
        
        help_lines.append("")
        help_lines.append("🌈" * 10)
        
        return "\n".join(help_lines)
    
    def get_help_text(self, command_name: Optional[str] = None) -> str:
        """获取帮助文本"""
        if command_name:
            if command_name in self.alias_registry:
                command_name = self.alias_registry[command_name]
            
            if command_name in self.command_registry:
                return self._get_command_help(self.command_registry[command_name])
            else:
                return f"⚠️ 未找到命令: {command_name}"
        
        help_lines = [
            "✨" * 10,
            "📚 可用命令",
            "✨" * 10,
            ""
        ]
        
        for name, command in sorted(self.command_registry.items()):
            name_part = f"🔹 {name}"
            if command.aliases:
                name_part += f" (别名: {', '.join(command.aliases)})"
            
            desc_part = f"- {command.description}"
            
            help_lines.append(f"{name_part:<30} {desc_part}")
        
        help_lines.extend([
            "",
            "💡 使用提示:",
            "  • 输入 '/help <命令名>' 查看具体命令的详细帮助",
            "  • 输入 '/<命令名> --help' 也可以查看命令帮助",
            "",
            "🌈" * 10
        ])
        
        return "\n".join(help_lines)