from atribot.LLMchat.sandbox.sandbox_base import (
    SandBoxBase,
    ExecutionResult,
    GeneratedFile
)
from docker.errors import ImageNotFound, NotFound
from tarfile import TarInfo
from typing import List
import mimetypes
import tarfile
import asyncio
import zipfile
import base64
import docker
import shlex
import uuid
import time
import io
import os




class DockerSandbox(SandBoxBase):
    """基于 Docker 容器的沙盒实现"""
    def __init__(self, config: dict = None):
        """初始化 Docker 沙盒实例

        Args:
            config: 配置字典，包含以下可选键：
                - image: Docker 镜像名称，默认为 'python:3.12-slim'
                - container_name: 容器名称，默认为随机生成的名称
                - mem_limit: 内存限制，默认为 '1024m'
                - cpu_period: CPU 周期，默认为 100000
                - cpu_quota: CPU 配额，默认为 100000
                - pids_limit: 进程数限制，默认为 64
                - network_mode: 网络模式，默认为 'bridge'
        """
        super().__init__(config)
        self.client = docker.from_env()
        self.image = self.config.get('image', 'python:3.12-slim')
        self.container_name = self.config.get('container_name', f"sandbox_{uuid.uuid4().hex[:8]}")
        self.container = None
        self.work_dir = "/workspace"
        
        # 资源限制配置
        self.mem_limit = self.config.get('mem_limit', '1024m')
        self.cpu_period = self.config.get('cpu_period', 100000)
        self.cpu_quota = self.config.get('cpu_quota', 100000)
        self.pids_limit = self.config.get('pids_limit', 64)
        self.network_mode = self.config.get('network_mode', 'bridge') #网络

    async def start(self):
        """启动 Docker 容器。

        如果容器不存在，会先拉取镜像再创建并启动容器。

        Raises:
            RuntimeError: 容器启动失败时抛出。
        """
        if self.is_running and self.container:
            return

        try:
            # 检查镜像是否存在，不存在则拉取
            try:
                await asyncio.to_thread(self.client.images.get, self.image)
            except ImageNotFound:
                print(f"Pulling image {self.image}...")
                await asyncio.to_thread(self.client.images.pull, self.image)

            # 启动容器
            self.container = await asyncio.to_thread(
                self.client.containers.run,
                self.image,
                name=self.container_name,
                detach=True,
                tty=True,
                command="tail -f /dev/null",
                working_dir=self.work_dir,
                mem_limit=self.mem_limit,
                cpu_period=self.cpu_period,
                cpu_quota=self.cpu_quota,
                pids_limit=self.pids_limit,
                network_mode=self.network_mode,
                # cap_drop=['ALL'] # 进阶安全：丢弃所有 Linux 能力
            )

            self.is_running = True
            
        except Exception as e:
            self.is_running = False
            await self.stop()
            raise RuntimeError(f"Failed to start Docker sandbox: {e}")

    async def stop(self):
        """停止并删除容器。

        如果容器不存在或已经停止，会静默处理。
        """
        if self.container:
            try:
                await asyncio.to_thread(self.container.stop, timeout=1)
                await asyncio.to_thread(self.container.remove, force=True)
            except NotFound:
                pass
            except Exception as e:
                print(f"Error stopping container: {e}")
            finally:
                self.container = None
                self.is_running = False

    async def restart(self):
        """重启沙盒环境。

        先停止并删除现有容器，然后重新启动新容器。
        """
        await self.stop()
        await self.start()

    async def run_command(self, command: str, timeout: int = 30) -> ExecutionResult:
        """在容器内执行 Shell 命令。

        使用 Linux 的 timeout 命令在容器内部强制终止超时进程。

        Args:
            command: 要执行的 Shell 命令。
            timeout: 命令执行超时时间（秒），默认 30 秒。

        Returns:
            ExecutionResult: 包含执行结果的对象。

        Raises:
            RuntimeError: 沙盒未运行时抛出。
        """
        if not self.is_running or not self.container:
            raise RuntimeError("Sandbox is not running")

        # 使用 Linux timeout 命令在容器内部强制终止超时进程
        # 这样即使 Python 侧超时，容器内的进程也会被 kill
        safe_command = f"timeout -k 5s {timeout}s /bin/sh -c {shlex.quote(command)}" if timeout else command

        try:
            # 依赖容器内的 timeout 命令。
            # 但为了防止 docker daemon 卡死，保留一个稍大的 Python 侧超时
            exec_future = asyncio.to_thread(
                self.container.exec_run,
                cmd=["/bin/sh", "-c", safe_command],
                workdir=self.work_dir,
                demux=True
            )
            
            exit_code, output = await asyncio.wait_for(exec_future, timeout=timeout + 2)
            # print(output)
            stdout_bytes, stderr_bytes = output if output else (b'', b'')
            stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ""
            stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ""
            
            # 检查 exit_code，124 是 Linux timeout 命令的默认退出码
            if exit_code == 124:
                return ExecutionResult(
                    stdout=stdout,
                    stderr=f"{stderr}\nExecution timed out (killed by sandbox)",
                    exit_code=124,
                    text="Execution timed out"
                )

            return ExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                text=f"{stdout}\n{stderr}".strip()
            )

        except asyncio.TimeoutError:
            return ExecutionResult(
                stdout="",
                stderr="Docker API timed out",
                exit_code=124,
                text="Execution timed out"
            )
        except Exception as e:
            return ExecutionResult(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                text=str(e)
            )

    async def run_code(self, code: str, language: str = 'python', timeout: int = 30) -> ExecutionResult:
        """在沙盒中执行一次性代码，会执行清理

        根据语言类型生成对应的文件并执行（但是目前环境只有py）

        Args:
            code: 要执行的代码字符串。
            language: 编程语言，支持 'python', 'nodejs'/'javascript', 'bash'，默认为 'python'
            timeout: 执行超时时间（秒），默认 30 秒。

        Returns:
            ExecutionResult: 包含执行结果的对象。
        """
        run_id = uuid.uuid4().hex[:8]
        temp_dir = f"/tmp/code_{run_id}"
        
        filename = f"script_{run_id}"
        interpreter = ""
        
        if language == 'python':
            filename += ".py"
            interpreter = "python3 -u"
        elif language in ['nodejs', 'javascript']:
            filename += ".js"
            interpreter = "node"
        elif language == 'bash':
            filename += ".sh"
            interpreter = "bash"
        else:

            raise ValueError(f"不支持的编程语言类型: {language}")

        file_path = f"{temp_dir}/{filename}"

        try:
            await self.run_command(f"mkdir -p {temp_dir}")
            
            await self.run_command(f"echo {base64.b64encode(code.encode('utf-8')).decode('utf-8')} | base64 -d > {file_path}")

            run_cmd = f"cd {temp_dir} && {interpreter} ./{filename}"
            
            return await self.run_command(run_cmd, timeout=timeout)

        finally:
            if temp_dir and temp_dir.startswith("/tmp/code_"):
                await self.run_command(f"rm -rf {temp_dir}", timeout=5)

    async def run_python_code(
        self, 
        code: str, 
        timeout: int = 30, 
        max_file_size: int = 20 * 1024 * 1024,
        max_total_size: int = 150 * 1024 * 1024
    ) -> ExecutionResult:
        """在沙盒中执行一次性python代码。
        
        逻辑变更：
        1. 如果产生单个文件，直接返回该文件。
        2. 如果产生多个文件，打包成 output.zip 返回。
        3. 增加总大小限制检查。

        Args:
            code: 要执行的代码字符串
            timeout: 执行超时时间（秒）。
            max_file_size: 单个文件最大字节数限制（仅在单文件模式下生效）
            max_total_size: 产生的所有文件总大小限制（压缩前）

        Returns:
            ExecutionResult: 包含执行结果的对象
        """
        
        run_id = uuid.uuid4().hex
        run_dir = f"{self.work_dir}/run_{run_id}"
        script_name = "main.py"
        script_path = f"{run_dir}/{script_name}"
        
        generated_files: List[GeneratedFile] = []
        exec_result = None
        warning_msg = ""

        try:
            #准备环境和代码
            await self.run_command(f"mkdir -p {run_dir}")
            b64_code = base64.b64encode(code.encode('utf-8')).decode('utf-8')
            await self.run_command(f"echo {b64_code} | base64 -d > {script_path}")

            #执行代码
            run_cmd = f"cd {run_dir} && python3 -u {script_name}"
            exec_result = await self.run_command(run_cmd, timeout=timeout)

            try:
                bits, stat = await asyncio.to_thread(self.container.get_archive, run_dir)
                
                file_obj = io.BytesIO()
                for chunk in bits:
                    file_obj.write(chunk)
                file_obj.seek(0)
                valid_members:List[TarInfo] = []
                total_size = 0
                
                with tarfile.open(fileobj=file_obj, mode='r') as tar:
                    for member in tar.getmembers():
                        if not member.isfile():
                            continue
                        
                        filename = os.path.basename(member.name)
                        if filename == script_name: # 忽略脚本本身
                            continue
                        
                        valid_members.append(member)
                        total_size += member.size
                
                #总大小超过限制
                if total_size > max_total_size:
                    warning_msg = f"\n[System Warning] Generated files ignored. Total size ({total_size} bytes) exceeds limit ({max_total_size} bytes)."
                
                #没有产生文件
                elif len(valid_members) == 0:
                    pass 

                #直接存储
                elif len(valid_members) == 1:
                    member = valid_members[0]
                    filename = os.path.basename(member.name)
                    
                    if member.size > max_file_size:
                        warning_msg = f"\n[System Warning] File '{filename}' ignored. Size ({member.size} bytes) exceeds limit ({max_file_size} bytes)."
                    else:
                        file_obj.seek(0) 
                        with tarfile.open(fileobj=file_obj, mode='r') as tar:
                            f_extracted = tar.extractfile(member)
                            if f_extracted:
                                content = f_extracted.read()
                                mime_type, _ = mimetypes.guess_type(filename)
                                generated_files.append(GeneratedFile(
                                    path=filename,
                                    content=content,
                                    type=mime_type or "application/octet-stream"
                                ))

                #打包成 ZIP
                else:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                        file_obj.seek(0) # 重置 tar 流指针
                        with tarfile.open(fileobj=file_obj, mode='r') as tar:
                            for member in valid_members:
                                f_extracted = tar.extractfile(member)
                                if f_extracted:
                                    filename = os.path.basename(member.name)
                                    zf.writestr(filename, f_extracted.read())
                    
                    generated_files.append(GeneratedFile(
                        path="output.zip",
                        content=zip_buffer.getvalue(),
                        type="application/zip"
                    ))

            except Exception as e:
                if exec_result:
                    err_msg = f"\n[System Error] Failed to process generated files: {str(e)}"
                    exec_result.stderr += err_msg
                    exec_result.text += err_msg

        finally:
            # 清理环境
            if run_dir.startswith(self.work_dir) and "run_" in run_dir:
                await self.run_command(f"rm -rf {run_dir}", timeout=5)

        if exec_result:
            if warning_msg:
                exec_result.stderr += warning_msg
                exec_result.text += warning_msg
            
            exec_result.files = generated_files
            return exec_result
        else:
            return ExecutionResult(
                stdout="",
                stderr="Execution failed internally.",
                exit_code=-1,
                text="Execution failed internally.",
                files=[]
            )

    async def upload_file(self, local_path: str, remote_path: str):
        """上传本地文件到容器。

        Args:
            local_path: 本地文件路径。
            remote_path: 容器内目标路径。

        Raises:
            FileNotFoundError: 本地文件不存在时抛出。
            RuntimeError: 沙盒未运行或上传失败时抛出。
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file {local_path} not found")

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tar.add(local_path, arcname=os.path.basename(remote_path))
        tar_stream.seek(0)

        remote_dir = os.path.dirname(remote_path)
        if not remote_dir:
            remote_dir = self.work_dir
            
        await self.run_command(f"mkdir -p {remote_dir}")

        await asyncio.to_thread(
            self.container.put_archive,
            path=remote_dir,
            data=tar_stream
        )

    async def download_file(self, remote_path: str, local_path: str):
        """从容器下载文件到本地（流式处理）。

        使用临时 tar 文件进行流式处理，避免全部加载到内存。

        Args:
            remote_path: 容器内文件路径。
            local_path: 本地保存路径。

        Raises:
            RuntimeError: 沙盒未运行或下载失败时抛出。
            FileNotFoundError: 容器内文件不存在时抛出。
        """
        if not self.is_running:
            raise RuntimeError("Sandbox is not running")

        try:
            # 获取数据流
            bits, stat = await asyncio.to_thread(self.container.get_archive, remote_path)
            
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 使用临时文件流式解压是比较复杂的，因为 get_archive 返回的是 tar 流。
            # 简单优化：先写入临时 tar 文件，再解压，避免全部加载到 RAM
            temp_tar = local_path + ".tar.tmp"
            with open(temp_tar, 'wb') as f:
                for chunk in bits:
                    f.write(chunk)
            
            try:
                with tarfile.open(temp_tar, 'r') as tar:
                    # 更加安全的解压方式
                    member = tar.next() # 获取第一个文件
                    if member.isfile():
                        f_src = tar.extractfile(member)
                        with open(local_path, 'wb') as f_dst:
                            while True:
                                chunk = f_src.read(8192) # 分块读取
                                if not chunk: 
                                    break
                                f_dst.write(chunk)
            finally:
                if os.path.exists(temp_tar):
                    os.remove(temp_tar)

        except NotFound:
            raise FileNotFoundError(f"Remote file {remote_path} not found")
        except Exception as e:
            raise RuntimeError(f"Download failed: {e}")

    async def read_file(self, remote_path: str, max_size: int = 1024 * 1024) -> str:
        """读取容器内文件内容。

        Args:
            remote_path: 容器内文件路径。
            max_size: 最大读取字节数，默认 1MB

        Returns:
            str: UTF-8 编码的文件内容字符串。如果文件超过最大限制，返回错误信息。

        Raises:
            RuntimeError: 沙盒未运行时抛出。
        """
        if not self.is_running:
            raise RuntimeError("Sandbox is not running")
        
        try:
            bits, stat = await asyncio.to_thread(self.container.get_archive, remote_path)
            
            if stat['size'] > max_size:
                return f"Error: File too large ({stat['size']} bytes). Limit is {max_size} bytes."

            file_obj = io.BytesIO()
            for chunk in bits:
                file_obj.write(chunk)
            file_obj.seek(0)
            
            with tarfile.open(fileobj=file_obj, mode='r') as tar:
                content = tar.extractfile(tar.next()).read(max_size) 
                return content.decode('utf-8', errors='replace')
        except Exception as e:
            return f"Error reading file: {str(e)}"


    async def file_exists(self, remote_path: str) -> bool:
        """检查沙盒内文件是否存在。

        Args:
            remote_path: 容器内文件路径。

        Returns:
            bool: 文件存在返回 True，否则返回 False。
        """
        if not self.is_running:
            return False

        cmd = f"test -e {shlex.quote(remote_path)}"
        
        result = await self.run_command(cmd, timeout=5)
        
        # exit_code 为 0 表示命令执行成功
        # exit_code 为 1 表示文件不存在
        return result.exit_code == 0


    async def _write_content_to_container(self, filename: str, content: str):
        """将字符串内容写入容器内的指定文件。

        该方法会在内存中构建一个包含目标文件的 tar 归档流（不涉及本地磁盘 I/O）
        并通过 `put_archive` 接口将其上传到容器的 `work_dir` 目录中。
        由于 `put_archive` 通常是阻塞操作，因此使用 `asyncio.to_thread` 在独立线程中运行

        Args:
            filename (str): 要在容器中创建的文件名（例如 "main.py"）。
            content (str): 要写入文件的文本内容。

        Returns:
            None

        Raises:
            Exception: 如果容器操作失败（具体异常取决于底层容器库，例如 docker.errors.APIError）。
        """
        tar_stream = io.BytesIO()
        info = tarfile.TarInfo(name=filename)
        encoded_content: bytes = content.encode('utf-8')
        info.size = len(encoded_content)
        info.mtime = time.time()
        
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tar.addfile(info, io.BytesIO(encoded_content))
        tar_stream.seek(0)

        await asyncio.to_thread(
            self.container.put_archive,
            path=self.work_dir,
            data=tar_stream
        )


