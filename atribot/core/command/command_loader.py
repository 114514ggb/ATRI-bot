from atribot.core.command.command_parsing import command_system
from atribot.core.service_container import container
from pathlib import Path
import importlib
import importlib.util
import logging
import sys



class command_loader:
    """命令加载器 - 用于动态加载指定目录下的命令模块"""
    
    def __init__(self):
        self.command_system:command_system = container.get("CommandSystem")
        self.logger:logging = container.get("log")
        self.loaded_modules = []
    
    def load_commands_from_directory(self, commands_dir: str, base_package: str = None) -> int:
        """
        从指定目录加载所有命令
        
        Args:
            commands_dir: 命令目录在项目的相对路径
            base_package: 基础包名，如果为None则自动推断
            
        Returns:
            成功加载的模块数量
        """
        commands_path = Path(commands_dir)
        
        if not commands_path.exists():
            self.logger.error(f"命令目录不存在: {commands_dir}")
            return 0
        
        if not commands_path.is_dir():
            self.logger.error(f"指定路径不是目录: {commands_dir}")
            return 0
        
        if base_package is None:
            base_package = self._path_to_package_name(commands_dir)
        
        
        loaded_count = 0
        
        for item in commands_path.iterdir():
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

    def _path_to_package_name(self, path_str: str) -> str:
        """
        将路径转换为包名
        
        Args:
            path_str: 路径字符串，如 "atribot/commands"
            
        Returns:
            包名，如 "atribot.commands"
        """
        normalized_path = path_str.replace('\\', '/').strip('/')
        return normalized_path.replace('/', '.')



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
    
    def reload_commands(self, commands_dir: str) -> int:
        """
        重新加载所有命令
        
        Args:
            commands_dir: 命令目录路径
            
        Returns:
            重新加载的模块数量
        """
        for module in self.loaded_modules:
            module_name = getattr(module, '__name__', None)
            if module_name and module_name in sys.modules:
                del sys.modules[module_name]
        
        self.loaded_modules.clear()
        
        if self.command_system and hasattr(self.command_system, 'command_registry'):
            self.command_system.command_registry.clear()
            self.command_system.alias_registry.clear()
        
        return self.load_commands_from_directory(commands_dir)