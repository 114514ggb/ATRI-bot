import asyncio
import atexit
import locale
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

from atribot.LLMchat.sandbox.sandbox_base import ExecutionResult, SandBoxBase
from atribot.LLMchat.sandbox.stream_exec import LocalCommandStream

_MAX_SESSION_LINES = 1000
"""会话输出缓冲的最大行数,超出后丢弃最早的输出"""


def _decode_output(data: bytes) -> str:
    """解码子进程输出

    优先 utf-8,失败时回退到系统本地编码(中文 Windows 的 cmd 通常是 gbk),
    最后再以替换模式兜底,保证任何字节序列都不会抛异常
    """
    for encoding in ("utf-8", locale.getpreferredencoding(False)):
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


class NoSandbox(SandBoxBase):
    """「没有沙盒」的沙盒:直接在宿主机本地环境中执行,不做任何隔离
    适用于不想安装 Docker / 不需要隔离的场景。所有代码和命令都会以
    当前用户权限直接运行在本机上,请确保仅在可信环境中使用。

    跨平台支持 Linux 与 Windows:
    - POSIX 系统使用 /bin/sh 执行命令(与 Docker 版行为一致)
    - Windows 优先寻找 bash(Git Bash/MSYS2,可兼容工具层的
      mkdir -p/base64/rm -rf 等 POSIX 命令),找不到时退回 cmd.exe
    - WSL 的 bash(System32 下)会被排除,避免文件系统映射混乱

    config 支持的键:
        - work_dir: 本地工作区根目录,默认为 项目根目录/sandbox_workspace;
          正常启动时 bot 会注入 document/work(见 sandbox.factory.resolve_sandbox_config)
        - shell: 显式指定 shell 程序路径(如 "/bin/bash"、
          r"C:\\Program Files\\Git\\bin\\bash.exe"、"powershell"),
          默认按上述规则自动探测
    """

    backend = "no-sandbox"
    backend_display = "本机直执行（无隔离）"

    shell_kind: str = "sh"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._shell_args = self._resolve_shell()
        self._sessions: dict[str, dict] = {}
        """session_name -> {"proc", "buffer", "tasks"}"""

        shell_prog = os.path.basename(self._shell_args[0]).lower()
        self._is_powershell = "powershell" in shell_prog or shell_prog == "pwsh"
        # 哨兵与 POSIX 拼接语法只适配 sh/bash/cmd；powershell 不支持面板终端
        self._posix_shell = not self._is_powershell and "cmd" not in shell_prog
        self.shell_kind = self._detect_shell_kind(shell_prog)

        default_root = Path(__file__).resolve().parents[3]
        work_dir = self.config.get("work_dir") or (default_root / "sandbox_workspace")
        # 统一使用 / 分隔符,方便工具层直接拼接路径
        self.work_dir: str = Path(work_dir).expanduser().resolve().as_posix()

        atexit.register(self._cleanup_sessions_sync)

    @staticmethod
    def _detect_shell_kind(shell_prog: str) -> str:
        """按 shell 程序名推导方言标识（供工具描述提示命令写法）

        Args:
            shell_prog: shell 程序名（小写，不含路径）

        Returns:
            ``"cmd"`` / ``"powershell"`` / ``"bash"`` / ``"sh"``
        """
        if "cmd" in shell_prog:
            return "cmd"
        if "powershell" in shell_prog or shell_prog == "pwsh":
            return "powershell"
        if "bash" in shell_prog:
            return "bash"
        return "sh"


    async def start(self):
        """启动本地执行模式(仅做标记与工作目录准备,无真实环境可启动)"""
        if self.is_running:
            return

        os.makedirs(self.work_dir, exist_ok=True)
        self.is_running = True
        shell_desc = " ".join(self._shell_args[:2])
        print(f"[NoSandbox] 本地执行模式已启用: shell={shell_desc}, work_dir={self.work_dir}")
        print("[NoSandbox] 警告: 命令与代码将以当前用户权限直接在本机执行,没有任何隔离!")

    async def stop(self):
        """停止本地执行模式,并终止所有活跃会话进程"""
        for name in list(self._sessions.keys()):
            await self.session_kill(name)
        self.is_running = False

    async def restart(self):
        """重启:终止所有会话进程后重新标记为运行状态"""
        await self.stop()
        await self.start()
        

    def _resolve_shell(self) -> list[str]:
        """解析出用于执行命令的 shell 启动参数(程序 + 执行选项)"""
        configured = self.config.get("shell")
        if configured:
            return self._shell_command_for(str(configured))

        if os.name == "nt":
            bash = self._find_windows_bash()
            if bash:
                return [bash, "-c"]
            # 没有 bash 时退回 cmd,此时 POSIX 风格命令(mkdir -p 等)不可用
            return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c"]
        return ["/bin/sh", "-c"]

    @staticmethod
    def _shell_command_for(shell: str) -> list[str]:
        """根据 shell 程序名附加对应的命令行选项"""
        name = os.path.basename(shell).lower()
        if "cmd" in name:
            return [shell, "/d", "/s", "/c"]
        if "powershell" in name or name == "pwsh":
            return [shell, "-NoProfile", "-Command"]
        return [shell, "-c"]

    @staticmethod
    def _find_windows_bash() -> str | None:
        """在 Windows 上寻找可用的 bash,排除 WSL 的存根"""
        bash = shutil.which("bash")
        if not bash:
            return None
        if "system32" in bash.lower():
            # System32 下的 bash.exe 是 WSL 入口,文件系统与宿主机隔离,会导致路径混乱
            return None
        return bash

    @staticmethod
    def _spawn_kwargs() -> dict:
        """平台相关的子进程创建参数

        POSIX 用 start_new_session 让子进程脱离进程组,便于整组杀死;
        Windows 用 CREATE_NEW_PROCESS_GROUP 便于 taskkill /T 清理进程树
        """
        if os.name == "nt":
            return {
                "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            }
        return {"start_new_session": True}

    @staticmethod
    def _kill_process_tree(proc: asyncio.subprocess.Process):
        """强制杀死进程及其所有子进程"""
        if proc.returncode is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=10,
                )
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    async def _execute(
        self,
        args: list[str],
        timeout: float | None = None,
        cwd: str | None = None,
        shell_command: str | None = None,
    ) -> ExecutionResult:
        """执行一个进程并收集输出,超时时杀死整个进程树

        Args:
            args: 完整的进程启动参数(shell_command 为空时使用)
            timeout: 超时秒数,None/0 表示不限时
            cwd: 工作目录,默认为 work_dir
            shell_command: 非空时经平台默认 shell 执行该命令字符串。cmd.exe 的
                引号解析与 MSVC(list2cmdline) 转义冲突(会把 " 变成 \"),
                因此 Windows cmd 必须走 shell 拼接路径,与面板终端一致

        Returns:
            ExecutionResult: 超时时 exit_code 为 124,与 Docker 版保持一致
        """
        cwd = cwd or self.work_dir
        if not os.path.isdir(cwd):
            try:
                os.makedirs(cwd, exist_ok=True)
            except OSError:
                cwd = None

        common = dict(
            cwd=cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **self._spawn_kwargs(),
        )
        try:
            if shell_command is not None:
                proc = await asyncio.create_subprocess_shell(shell_command, **common)
            else:
                proc = await asyncio.create_subprocess_exec(*args, **common)
        except Exception as e:
            return ExecutionResult(stdout="", stderr=str(e), exit_code=-1, text=str(e))

        stdout_parts: list[bytes] = []
        stderr_parts: list[bytes] = []

        async def _pump(stream: asyncio.StreamReader, sink: list[bytes]):
            try:
                while True:
                    chunk = await stream.read(65536)
                    if not chunk:
                        break
                    sink.append(chunk)
            except Exception:
                pass

        pump_out = asyncio.create_task(_pump(proc.stdout, stdout_parts))
        pump_err = asyncio.create_task(_pump(proc.stderr, stderr_parts))

        timed_out = False
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout or None)
        except asyncio.TimeoutError:
            timed_out = True
            self._kill_process_tree(proc)
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass

        # 杀死进程后管道会到达 EOF,读取任务自然结束
        await asyncio.gather(pump_out, pump_err, return_exceptions=True)

        stdout = _decode_output(b"".join(stdout_parts))
        stderr = _decode_output(b"".join(stderr_parts))

        if timed_out:
            return ExecutionResult(
                stdout=stdout,
                stderr=f"{stderr}\nExecution timed out (killed by sandbox)",
                exit_code=124,
                text="Execution timed out",
            )

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=proc.returncode if proc.returncode is not None else -1,
            text=f"{stdout}\n{stderr}".strip(),
        )

    async def run_command(self, command: str, timeout: int = 30) -> ExecutionResult:
        """在本地 shell 中执行命令

        Args:
            command: 要执行的 shell 命令
            timeout: 超时时间(秒),默认 30,超时会杀死整个进程树

        Returns:
            ExecutionResult
        """
        if not self.is_running:
            raise RuntimeError("Sandbox is not running")

        if self.shell_kind == "cmd":
            # cmd.exe 不吃 MSVC 转义(list2cmdline 会把 " 变成 \")，命令里的引号会被
            # 破坏，故改走 shell 拼接路径把命令字符串原样交给 cmd(与面板终端一致)
            return await self._execute([], timeout=timeout, shell_command=command)
        return await self._execute([*self._shell_args, command], timeout=timeout)

    async def run_code(self, code: str, language: str = "python", timeout: int = 30) -> ExecutionResult:
        """在本地临时目录中执行一次性代码,执行后清理

        与 Docker 版不同,这里直接用进程参数启动解释器而不经过 shell,
        避免解释器路径中的空格/特殊字符带来的引号问题

        Args:
            code: 代码字符串
            language: 支持 python / nodejs(javascript) / bash
            timeout: 超时时间(秒),默认 30

        Returns:
            ExecutionResult

        Raises:
            ValueError: 不支持的语言类型
        """
        if not self.is_running:
            raise RuntimeError("Sandbox is not running")

        lang = (language or "python").lower()
        run_dir = tempfile.mkdtemp(prefix="atri_sandbox_code_")

        if lang == "python":
            exe = sys.executable or shutil.which("python3") or shutil.which("python") or "python"
            args = [exe, "-u"]
            filename = "script.py"
        elif lang in ("nodejs", "javascript"):
            node = shutil.which("node")
            if not node:
                return ExecutionResult(
                    stdout="", stderr="node 不存在于 PATH 中", exit_code=1, text="node 不可用"
                )
            args = [node]
            filename = "script.js"
        elif lang == "bash":
            bash = self._find_windows_bash() if os.name == "nt" else (shutil.which("bash") or "/bin/sh")
            if not bash:
                return ExecutionResult(
                    stdout="",
                    stderr="Windows 下执行 bash 需要 Git Bash/MSYS2 环境",
                    exit_code=1,
                    text="bash 不可用",
                )
            args = [bash]
            filename = "script.sh"
        else:
            raise ValueError(f"不支持的编程语言类型: {language}")

        script_path = os.path.join(run_dir, filename)
        with open(script_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)

        try:
            return await self._execute([*args, script_path], timeout=timeout, cwd=run_dir)
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)


    async def upload_file(self, local_path: str, remote_path: str):
        """将本地文件复制到沙盒工作区(即本机文件系统内的复制)"""
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file {local_path} not found")

        remote_dir = os.path.dirname(remote_path)
        if remote_dir:
            os.makedirs(remote_dir, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, local_path, remote_path)

    async def download_file(self, remote_path: str, local_path: str):
        """将沙盒内文件复制到指定本地路径"""
        if not os.path.exists(remote_path):
            raise FileNotFoundError(f"Remote file {remote_path} not found")

        try:
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            await asyncio.to_thread(shutil.copy2, remote_path, local_path)
        except Exception as e:
            raise RuntimeError(f"Download failed: {e}")

    async def read_file(self, remote_path: str, max_size: int = 1024 * 1024) -> str:
        """读取沙盒内文件的文本内容

        Args:
            remote_path: 文件路径
            max_size: 最大读取字节数,默认 1MB

        Returns:
            str: 文件内容字符串,出错时返回错误信息(与 Docker 版一致)
        """
        if not self.is_running:
            raise RuntimeError("Sandbox is not running")

        try:
            if not os.path.isfile(remote_path):
                return f"Error reading file: [Errno 2] No such file or directory: '{remote_path}'"

            size = os.path.getsize(remote_path)
            if size > max_size:
                return f"Error: File too large ({size} bytes). Limit is {max_size} bytes."

            with open(remote_path, "rb") as f:
                return _decode_output(f.read(max_size))
        except Exception as e:
            return f"Error reading file: {e}"

    async def file_exists(self, remote_path: str) -> bool:
        """检查沙盒内文件或目录是否存在"""
        if not self.is_running:
            return False
        return os.path.exists(remote_path)
    

    @staticmethod
    async def _pump_lines(
        stream: asyncio.StreamReader, buffer: deque, partials: dict, key: str
    ):
        """逐行读取子进程输出并写入缓冲

        没有换行结尾的残余(如 REPL 的 ">>>" 提示符)保存在 partials[key] 中,
        由 session_read 一并返回;流结束时写入缓冲
        """
        try:
            remainder = ""
            while True:
                chunk = await stream.read(1024)
                if not chunk:
                    break
                remainder += _decode_output(chunk)
                if "\n" in remainder:
                    *lines, remainder = remainder.split("\n")
                    for line in lines:
                        buffer.append(line.rstrip("\r"))
                partials[key] = remainder
            if remainder:
                buffer.append(remainder)
        except Exception:
            pass
        finally:
            partials[key] = ""

    async def session_start(self, session_name: str, command: str, timeout: int = 10) -> ExecutionResult:
        """新建一个本地会话并在其中运行命令

        本地没有 tmux,通过常驻子进程 + 后台输出缓冲来模拟:
        进程的 stdout/stderr 被逐行收集到缓冲区,session_read 读取缓冲,
        session_send 向 stdin 写入一行

        Args:
            session_name: 会话名称,后续 send/read/kill 通过此名称引用
            command: 要在会话中运行的命令(如 'python'、'node' 等)
            timeout: 等待初始输出的秒数,默认 10;期间一旦有输出立即返回

        Returns:
            ExecutionResult(text 为启动后的初始缓冲内容)
        """
        if not self.is_running:
            raise RuntimeError("Sandbox is not running")

        # 同名会话幂等清理
        await self.session_kill(session_name)

        try:
            proc = await asyncio.create_subprocess_exec(
                *self._shell_args,
                command,
                cwd=self.work_dir,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **self._spawn_kwargs(),
            )
        except Exception as e:
            return ExecutionResult(stdout="", stderr=str(e), exit_code=1, text=str(e))

        buffer: deque[str] = deque(maxlen=_MAX_SESSION_LINES)
        partials = {"out": "", "err": ""}

        async def _watch():
            await proc.wait()
            buffer.append(f"[会话进程已退出, exit_code={proc.returncode}]")

        tasks = [
            asyncio.create_task(self._pump_lines(proc.stdout, buffer, partials, "out")),
            asyncio.create_task(self._pump_lines(proc.stderr, buffer, partials, "err")),
            asyncio.create_task(_watch()),
        ]
        self._sessions[session_name] = {
            "proc": proc,
            "buffer": buffer,
            "tasks": tasks,
            "partials": partials,
        }

        # 等待程序启动并产生初始输出(交互式程序启动可能较慢),有输出即提前返回
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(timeout, 0.5)
        while not buffer and not any(partials.values()) and loop.time() < deadline:
            await asyncio.sleep(0.1)
        return await self.session_read(session_name)

    async def session_send(self, session_name: str, input_text: str, wait: float = 0.5) -> ExecutionResult:
        """向会话进程发送一行输入(自动追加换行),并返回发送后的输出缓冲"""
        session = self._sessions.get(session_name)
        if not session:
            msg = f"Session '{session_name}' not found"
            return ExecutionResult(stdout="", stderr=msg, exit_code=1, text=msg)

        proc: asyncio.subprocess.Process = session["proc"]
        if proc.returncode is not None:
            msg = f"Session '{session_name}' process has exited (exit_code={proc.returncode})"
            return ExecutionResult(stdout="", stderr=msg, exit_code=1, text=msg)

        try:
            proc.stdin.write(f"{input_text}\n".encode("utf-8"))
            await proc.stdin.drain()
        except Exception as e:
            return ExecutionResult(stdout="", stderr=str(e), exit_code=1, text=str(e))

        await asyncio.sleep(wait)
        return await self.session_read(session_name)

    async def session_read(self, session_name: str) -> ExecutionResult:
        """返回会话当前的输出缓冲内容(含尚未换行的残余输出)"""
        session = self._sessions.get(session_name)
        if not session:
            msg = f"Session '{session_name}' not found"
            return ExecutionResult(stdout="", stderr=msg, exit_code=1, text=msg)

        pending = [p for p in session["partials"].values() if p]
        text = "\n".join([*session["buffer"], *pending])
        return ExecutionResult(stdout=text, stderr="", exit_code=0, text=text)

    async def session_kill(self, session_name: str) -> ExecutionResult:
        """终止并删除一个会话(杀死进程树并清理缓冲)"""
        session = self._sessions.pop(session_name, None)
        if not session:
            return ExecutionResult(stdout="", stderr="", exit_code=0, text="")

        proc: asyncio.subprocess.Process = session["proc"]
        self._kill_process_tree(proc)
        for task in session["tasks"]:
            task.cancel()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass

        return ExecutionResult(stdout="", stderr="", exit_code=0, text="")

    def _cleanup_sessions_sync(self):
        """进程退出钩子:同步杀死所有会话进程,防止残留"""
        for session in self._sessions.values():
            self._kill_process_tree(session["proc"])
        self._sessions.clear()


    def panel_capabilities(self) -> dict:
        # powershell 的哨兵语法未适配,不开放面板终端
        return {"start_stop": True, "terminal": not self._is_powershell, "metrics": False}

    async def panel_status(self) -> dict:
        return {
            "backend": self.backend,
            "display": self.backend_display,
            "running": self.is_running,
            "rows": [
                ("工作目录", self.work_dir),
                ("Shell", " ".join(self._shell_args[:2])),
                ("活跃会话", str(len(self._sessions))),
                ("隔离级别", "无（命令以当前用户权限直接在本机执行）"),
            ],
        }

    async def panel_exec_stream(self, command: str, send, cwd: str | None = None):
        if not self.is_running:
            raise RuntimeError("Sandbox is not running")
        return LocalCommandStream(
            cwd=cwd or self.work_dir,
            posix=self._posix_shell,
            spawn_args=self._shell_args if not self._is_cmd_shell() else None,
            spawn_kwargs=self._spawn_kwargs(),
            cwd_mapper=self._normalize_cwd,
        ).start(command, send)

    def _normalize_cwd(self, path: str) -> str:
        """Git Bash 的 $(pwd) 返回 MSYS 风格路径（/c/...），转回 Windows 形式"""
        if os.name == "nt" and self._posix_shell:
            m = re.match(r"^/([A-Za-z])/(.*)$", path)
            if m:
                return f"{m.group(1).upper()}:/{m.group(2)}"
        return path

    def _is_cmd_shell(self) -> bool:
        return "cmd" in os.path.basename(self._shell_args[0]).lower()

    def panel_terminal_info(self) -> dict:
        import getpass
        import socket

        try:
            user = getpass.getuser()
        except Exception:
            user = "?"
        return {
            "cwd": self.work_dir,
            "home": os.path.expanduser("~"),
            "user": user,
            "host": socket.gethostname(),
            "isWindows": os.name == "nt",
            "platform": sys.platform,
            "sep": os.sep,
        }
