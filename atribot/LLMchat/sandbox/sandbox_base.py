from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import List
import base64
import os




@dataclass(slots=True)
class GeneratedFile:
    path: str               # 文件名或相对路径
    content: bytes          # 文件的二进制内容
    type: str = "unknown"   #文件类型

    def save(self, local_dir: str):
        """将文件保存到本地磁盘"""
        full_path = os.path.join(local_dir, self.path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(self.content)
    
    def to_base64(self, encoding: str = 'utf-8') -> str:
        """
        将文件内容转换为 Base64 编码字符串
        
        Args:
            encoding: 返回字符串的编码方式，默认为 'utf-8'
            
        Returns:
            Base64 编码的字符串
        """
        return base64.b64encode(self.content).decode(encoding)
    
    @property
    def size(self) -> int:
        return len(self.content)


@dataclass(slots=True)
class ExecutionResult:
    stdout: str             # 标准输出
    stderr: str             # 错误输出
    exit_code: int          # 退出码 (0代表成功, 非0代表失败)
    text: str               # 组合了 stdout 和 stderr 的完整文本
    files: List[GeneratedFile] = field(default_factory=list)      # 额外产生的文件


class SandBoxBase(ABC):
    """
    沙盒环境的抽象基类。
    所有具体的沙盒实现都必须继承此类。
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.is_running = False
    
    @abstractmethod
    async def start(self):
        """
        启动沙盒环境
        """
        pass

    @abstractmethod
    async def stop(self):
        """
        停止并销毁沙盒环境
        """
        pass

    @abstractmethod
    async def restart(self):
        """重启环境"""
        pass

    @abstractmethod
    async def run_code(self, code: str, language: str = 'python', timeout: int = 30) -> ExecutionResult:
        """
        在沙盒中执行一次性代码，会执行后清理
        
        Args:
            code: 代码字符串
            language: 语言类型 (python, bash, nodejs)
            timeout: 超时时间（秒）
            
        Returns:
            ExecutionResult 对象
        """
        pass
    

    @abstractmethod
    async def run_command(self, command: str, timeout: int = 30) -> ExecutionResult:
        """
        在沙盒终端执行 Shell 命令
        """
        pass


    @abstractmethod
    async def upload_file(self, local_path: str, remote_path: str):
        """
        将本地文件上传到沙盒中
        """
        pass

    @abstractmethod
    async def download_file(self, remote_path: str, local_path: str):
        """
        从沙盒中下载文件到本地
        """
        pass
    
    @abstractmethod
    async def read_file(self, remote_path: str) -> str:
        """
        直接读取沙盒内文件的内容（文本模式）
        """
        pass

    @abstractmethod
    async def file_exists(self, remote_path: str) -> bool:
        """检查沙盒内文件是否存在"""
        pass

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()