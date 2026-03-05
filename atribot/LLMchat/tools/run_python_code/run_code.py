from atribot.core.service_container import container
from atribot.core.type.chat_message_type import File
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox
from atribot.LLMchat.sandbox.sandbox_base import ExecutionResult

sand_box:DockerSandbox = container.get("SandBox")



async def run_python_code(
    code: str, 
    files: list[File] = None,
    timeout: int = 30, 
    max_file_size: int = 20 * 1024 * 1024,
    max_total_size: int = 150 * 1024 * 1024
)->ExecutionResult:
    """在沙盒中执行一次性python代码

    Args:
        code (str): 要执行的代码字符串
        files (list[File]): 要输入到环境的文件列表
        timeout (int, optional): 执行超时时间（秒）. Defaults to 30.
        max_file_size (int, optional): 单个文件最大字节数限制（仅在单文件模式下生效）. Defaults to 20*1024*1024.
        max_total_size (int, optional): 产生的所有文件总大小限制（压缩前）. Defaults to 150*1024*1024.

    Returns:
        ExecutionResult: 包含执行结果的对象
    """
    