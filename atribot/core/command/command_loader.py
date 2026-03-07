import importlib
import importlib.util
import logging
import sys
from pathlib import Path

from atribot.core.atri_config import atriConfig
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.service_container import container


class command_loader:
    """命令加载器 - 用于动态加载指定目录下的命令模块"""
    
    def __init__(self, commands_dir: Path | None = None):
        """初始化命令加载器，并立即加载命令目录。

        Args:
            commands_dir: 命令目录的绝对路径；如果不传，则默认使用
                `config.file_path.commands`。
        """
        self.command_system:CommandSystem = container.get("CommandSystem")
        self.logger:logging = container.get("log")
        self.config:atriConfig = container.get("config")
        self.loaded_modules = []
        self.commands_dir: Path = Path(commands_dir) if commands_dir else self.config.file_path.commands

        self.load_commands_from_directory(self.commands_dir)

    def _infer_base_package(self, commands_dir: Path) -> str:
        """根据项目根目录推断命令目录对应的基础包名。

        Args:
            commands_dir: 命令目录的绝对路径

        Returns:
            str: 可用于后续拼接子模块名的基础包名，例如 `atribot.commands`。
        """
        commands_dir = commands_dir.resolve()
        project_root = self.config.file_path.project_root.resolve()

        try:
            relative_path = commands_dir.relative_to(project_root)
        except ValueError:
            self.logger.warning(
                f"命令目录 {commands_dir} 不在项目根目录 {project_root} 下，将退回目录名推断包名。"
            )
            return commands_dir.name

        return ".".join(relative_path.parts) if relative_path.parts else commands_dir.name
    
    def load_commands_from_directory(self, commands_dir: Path, base_package: str = None) -> int:
        """从指定目录加载所有命令包。

        Args:
            commands_dir: 命令目录在项目中的绝对路径。
            base_package: 基础包名；如果不传，则根据项目根目录自动推断。

        Returns:
            int: 成功加载的命令包数量。
        """
        commands_dir = Path(commands_dir)
        self.commands_dir = commands_dir
        
        if not commands_dir.exists():
            self.logger.error(f"命令目录不存在: {commands_dir}")
            return 0
        
        if not commands_dir.is_dir():
            self.logger.error(f"指定路径不是目录: {commands_dir}")
            return 0
        
        if base_package is None:
            base_package = self._infer_base_package(commands_dir)
        
        loaded_count = 0
        
        for item in commands_dir.iterdir():
            if item.is_dir():
                init_file = item / "__init__.py"
                if init_file.exists():
                    try:
                        package_name = f"{base_package}.{item.name}" if base_package else item.name
                        self._load_package(item, package_name)
                        loaded_count += 1
                        self.logger.info(f"成功加载命令模块: {item.name}")
                    except Exception as e:
                        self.logger.error(f"加载命令模块 {item.name} 失败: {e}")
        
        self.logger.info(f"命令加载完成，共加载 {loaded_count} 个模块")
        return loaded_count

    def _load_package(self, package_path: Path, package_name: str):
        """
        加载整个包，确保正确的包层次结构
        
        Args:
            package_path: 包目录路径
            package_name: 完整包名
        """
        parent_parts = package_name.split('.')
        for i in range(1, len(parent_parts)):
            parent_name = '.'.join(parent_parts[:i])
            if parent_name not in sys.modules:
                parent_module = importlib.util.module_from_spec(
                    importlib.util.spec_from_loader(parent_name, loader=None)
                )
                sys.modules[parent_name] = parent_module
        
        for py_file in package_path.glob("*.py"):
            if py_file.name == "__init__.py":
                module_name = package_name
                file_path = py_file
            else:
                module_name = f"{package_name}.{py_file.stem}"
                file_path = py_file
            
            if module_name not in sys.modules:
                self._load_module_from_path(file_path, module_name)


    def _load_module_from_path(self, file_path: Path, module_name: str):
        """
        从指定路径加载模块
        
        Args:
            file_path: 模块文件路径
            module_name: 模块名称
        """
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法创建模块规格: {file_path}")
        
        if module_name in sys.modules:
            self.logger.debug(f"模块 {module_name} 已存在，跳过加载")
            return sys.modules[module_name]
        
        module = importlib.util.module_from_spec(spec)
        
        if file_path.name == "__init__.py":
            module.__path__ = [str(file_path.parent)]
        
        sys.modules[module_name] = module
        
        try:
            spec.loader.exec_module(module)
            self.loaded_modules.append(module)
            return module
        except Exception as e:
            if module_name in sys.modules:
                del sys.modules[module_name]
            raise e
    
    def reload_commands(self, commands_dir: str | Path | None = None) -> int:
        """重新加载所有命令。

        Args:
            commands_dir: 新的命令目录路径；如果不传，则重载当前目录。

        Returns:
            int: 重新加载的模块数量。
        """
        for module in self.loaded_modules:
            module_name = getattr(module, '__name__', None)
            if module_name and module_name in sys.modules:
                del sys.modules[module_name]
        
        self.loaded_modules.clear()
        
        if self.command_system and hasattr(self.command_system, 'command_registry'):
            self.command_system.command_registry.clear()
            self.command_system.alias_registry.clear()
        
        target_dir = Path(commands_dir) if commands_dir else self.commands_dir
        return self.load_commands_from_directory(target_dir)