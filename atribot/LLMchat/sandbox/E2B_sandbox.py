from atribot.LLMchat.sandbox.sandbox_base import (
    SandBoxBase,
    ExecutionResult,
    GeneratedFile
)
import base64
import uuid
import os
import sys
from typing import Optional

try:
    from e2b_code_interpreter import AsyncSandbox
    from e2b_code_interpreter.models import ExecutionError
except ImportError:
    print("错误：e2b_code_interpreter 模块未安装")
    print("请使用以下命令安装：")
    print("pip install e2b-code-interpreter")
    sys.exit(1)


class E2BSandbox(SandBoxBase):
    """
    基于 E2B (e2b_code_interpreter) 的沙盒实现。
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._sandbox: Optional[AsyncSandbox] = None
        self._api_key = self.config.get("api_key", os.environ.get("E2B_API_KEY"))
        self._template = self.config.get("template", "code-interpreter-v1")

    async def start(self):
        """启动 E2B 沙盒实例"""
        if not self._sandbox:
            self._sandbox = await AsyncSandbox.create(
                api_key=self._api_key,
                template=self._template
            )
        self.is_running = True

    async def stop(self):
        """关闭沙盒连接"""
        if self._sandbox:
            await self._sandbox.close()
            self._sandbox = None
        self.is_running = False

    async def restart(self):
        """重启沙盒 (E2B 通常是销毁后重建)"""
        await self.stop()
        await self.start()

    async def run_code(self, code: str, language: str = 'python', timeout: int = 30) -> ExecutionResult:
        """
        执行代码。
        注意：E2B 主要针对 Python 进行了富媒体优化 (run_code)。
        如果是 Bash，底层会转发给 run_command。
        """
        if not self._sandbox:
            await self.start()

        # 1. 处理 Bash
        if language.lower() in ['bash', 'sh', 'shell']:
            return await self.run_command(code, timeout=timeout)

        # 2. 处理 Python (使用 Code Interpreter 特性)
        if language.lower() == 'python':
            try:
                # E2B 的 run_code 类似于 Jupyter cell 执行
                execution = await self._sandbox.run_code(code, timeout=timeout)
            except Exception as e:
                # 处理超时或其他系统级错误
                return ExecutionResult(
                    stdout="",
                    stderr=str(e),
                    exit_code=1,
                    text=str(e)
                )

            # 提取标准输出和错误
            stdout_str = "\n".join(execution.logs.stdout)
            stderr_str = "\n".join(execution.logs.stderr)
            
            # 处理运行时错误 (Python Exception)
            exit_code = 0
            if execution.error:
                exit_code = 1
                # 将 Python 异常堆栈追加到 stderr
                tb = execution.error.traceback
                stderr_str += f"\n{execution.error.name}: {execution.error.value}\n{tb}"

            # 处理生成的文件 (主要是图表/图像)
            generated_files = []
            
            # E2B 将 plt.show() 等结果放在 execution.results 中
            for idx, result in enumerate(execution.results):
                # 检查常见的图像格式
                formats = [
                    ('png', 'image/png'),
                    ('jpeg', 'image/jpeg'),
                    ('svg', 'image/svg+xml'),
                    ('pdf', 'application/pdf')
                ]
                
                for attr, mime_type in formats:
                    if hasattr(result, attr) and getattr(result, attr):
                        data_b64 = getattr(result, attr)
                        # E2B 返回的是 base64 字符串，需要解码为 bytes
                        file_content = base64.b64decode(data_b64)
                        
                        # 生成一个文件名 (因为 plt.show() 没有文件名)
                        filename = f"chart_{uuid.uuid4().hex[:8]}_{idx}.{attr}"
                        
                        generated_files.append(GeneratedFile(
                            path=filename,
                            content=file_content,
                            type=mime_type
                        ))
                        break # 一个 result 通常只是一种格式

            return ExecutionResult(
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=exit_code,
                text=f"{stdout_str}\n{stderr_str}",
                files=generated_files
            )

        else:
            return ExecutionResult(
                stdout="",
                stderr=f"Language {language} not supported in run_code mode.",
                exit_code=1,
                text="Unsupported language"
            )

    async def run_command(self, command: str, timeout: int = 30) -> ExecutionResult:
        """在终端执行 Shell 命令"""
        if not self._sandbox:
            await self.start()

        try:
            # E2B commands.run 返回 stdout, stderr, exit_code
            cmd_result = await self._sandbox.commands.run(command, timeout=timeout)
            
            return ExecutionResult(
                stdout=cmd_result.stdout,
                stderr=cmd_result.stderr,
                exit_code=cmd_result.exit_code,
                text=f"{cmd_result.stdout}\n{cmd_result.stderr}"
            )
        except Exception as e:
            return ExecutionResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                text=str(e)
            )

    async def upload_file(self, local_path: str, remote_path: str):
        """上传文件"""
        if not self._sandbox:
            await self.start()
            
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")

        with open(local_path, 'rb') as f:
            data = f.read()
        
        await self._sandbox.files.write(remote_path, data)

    async def download_file(self, remote_path: str, local_path: str):
        """下载文件"""
        if not self._sandbox:
            await self.start()

        try:
            # 读取沙盒文件 (指定 format='bytes' 以获取二进制数据)
            # 注意：E2B SDK 的 read 方法根据版本可能行为略有不同，
            # 但通常支持读取为 bytes 或 str。这里假设 read 返回 bytes 或有 format 参数
            # 在最新版中，通常直接 read() 返回 str，read_bytes() 或类似机制存在
            # 这里的实现基于通用逻辑，具体视 SDK 版本微调
            content = await self._sandbox.files.read(remote_path, format='bytes')
            
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            
            with open(local_path, 'wb') as f:
                f.write(content)
        except Exception as e:
            raise IOError(f"Failed to download file {remote_path}: {str(e)}")

    async def read_file(self, remote_path: str) -> str:
        """读取文本文件内容"""
        if not self._sandbox:
            await self.start()
        
        # 默认 format='text' (utf-8)
        content = await self._sandbox.files.read(remote_path, format='text')
        return content

    async def file_exists(self, remote_path: str) -> bool:
        """检查文件是否存在"""
        if not self._sandbox:
            await self.start()
            
        return await self._sandbox.files.exists(remote_path)