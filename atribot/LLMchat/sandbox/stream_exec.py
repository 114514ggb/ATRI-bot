"""流式命令执行

一条命令 = 哨兵 + 流式泵：命令尾部追加哨兵把"真实退出码 + 结束时工作目录"
以带标记的行写进输出流，由 MarkerStreamFilter 提取并从可见输出中剔除。
Windows cmd 的哨兵依赖 call echo 二次展开在执行期读取 %ERRORLEVEL% / %CD%，
EC 标记必须在前——PWD 的 call echo 成功后会把 ERRORLEVEL 清零。
"""

import asyncio
import os
import re
import shlex
import signal
import subprocess
from typing import Awaitable, Callable, List, Optional, Tuple

PWD_TAG = "__ATRI_PWD_"
EC_TAG = "__ATRI_EC_"
PWD_RX = re.compile(r"__ATRI_PWD_(.*?)__")
EC_RX = re.compile(r"__ATRI_EC_(-?\d+)__")

MAX_STREAM_OUTPUT = 4 * 1024 * 1024  # 单条命令输出上限（字节），超出截断
_PUMP_GRACE = 3.0  # 进程退出后等管道 EOF 的宽限秒数（防孤儿子进程握住管道）
_SPAWN_TIMEOUT = 15  # Shell 进程创建自身的超时秒数（防 spawn 卡死拖垮会话）


def sentinel_line(cmd: str, posix: bool) -> str:
    """给用户命令追加哨兵，posix 选择 sh 语法或 Windows cmd 语法"""
    if posix:
        return f'{cmd} ; ec=$? ; echo "{PWD_TAG}$(pwd)__" ; echo "{EC_TAG}${{ec}}__"'
    return f"{cmd} & call echo {EC_TAG}^%ERRORLEVEL^%__& call echo {PWD_TAG}^%CD^%__"


def container_sentinel_line(cmd: str, timeout: int) -> str:
    """容器内（Linux）的哨兵命令行：用户命令与哨兵同处一个内层 shell，
    保证 cd 对 pwd 标记可见；timeout 包在最外层，超时强杀时标记随 shell 一同
    消失（回退 exec_inspect 退出码，目录视为不变）"""
    return f"timeout -k 5s {timeout}s /bin/sh -c {shlex.quote(sentinel_line(cmd, True))}"


def strip_markers(text: str) -> str:
    return EC_RX.sub("", PWD_RX.sub("", text))


def partial_marker_len(text: str) -> int:
    """text 末尾若是未闭合的哨兵标记（跨块截断），返回需要扣留等待补全的长度"""
    # 标记内容已出现但尚未闭合（__ATRI_EC_12 / __ATRI_EC_9_ / __ATRI_PWD_C:\Us）
    for tag in (EC_TAG, PWD_TAG):
        idx = text.rfind(tag)
        if idx >= 0:
            rest = text[idx + len(tag):]
            # PWD 内容任意（路径）；EC 只可能是 -数字 或半截闭合下划线
            if "__" not in rest and (tag is PWD_TAG or re.fullmatch(r"-?[\d_]*", rest)):
                return len(text) - idx
    # 标记前缀本身被截断（如尾部是 __ATRI_E）
    limit = max(len(PWD_TAG), len(EC_TAG))
    for k in range(min(len(text), limit), 0, -1):
        tail = text[-k:]
        if PWD_TAG.startswith(tail) or EC_TAG.startswith(tail):
            return k
    return 0


class StreamDecoder:
    """管道字节流 → 文本：优先 UTF-8，回退 GBK（中文 Windows 控制台代码页）。

    多字节字符被管道分块截断时保留尾部字节等待后续数据，避免中文被拆成乱码。
    """

    _BUF_CAP = 4096

    def __init__(self) -> None:
        self._buf = b""

    def feed(self, data: bytes) -> str:
        self._buf += data
        if not self._buf:
            return ""
        if len(self._buf) > self._BUF_CAP:
            # 异常长的未决缓冲：放弃精确性，直接容错解码
            text, self._buf = self._buf.decode("utf-8", errors="replace"), b""
            return text
        for enc in ("utf-8", "gbk"):
            try:
                text, self._buf = self._buf.decode(enc), b""
                return text
            except UnicodeDecodeError as e:
                if e.reason == "unexpected end of data":
                    # 尾部是多字节字符的一半：等下一块，绝不能落去 GBK 回退
                    # （截断的 UTF-8 字节常能被 GBK 错误解成乱码）
                    return ""
        # 两种编码都报坏字节：容错解码，绝不阻塞输出流
        text, self._buf = self._buf.decode("utf-8", errors="replace"), b""
        return text

    def flush(self) -> str:
        if not self._buf:
            return ""
        text, self._buf = self._buf.decode("utf-8", errors="replace"), b""
        return text


class MarkerStreamFilter:
    """从输出流提取哨兵标记并从可见输出剔除（支持跨块截断扣留）"""

    def __init__(self) -> None:
        self._pending = ""

    def feed(self, text: str) -> Tuple[str, Optional[str], Optional[int]]:
        """消费一段已解码文本，返回 (可见输出, 结束目录, 退出码)——后两者仅在标记出现时非 None"""
        self._pending += text
        new_cwd: Optional[str] = None
        exit_code: Optional[int] = None
        while True:
            m = EC_RX.search(self._pending)
            if m:
                exit_code = int(m.group(1))
                self._pending = self._pending[: m.start()] + self._pending[m.end():]
                continue
            m = PWD_RX.search(self._pending)
            if m:
                new_cwd = m.group(1)
                self._pending = self._pending[: m.start()] + self._pending[m.end():]
                continue
            break
        hold = partial_marker_len(self._pending)
        if hold:
            out, self._pending = self._pending[:-hold], self._pending[-hold:]
        else:
            out, self._pending = self._pending, ""
        return out, new_cwd, exit_code

    def flush(self) -> str:
        text = strip_markers(self._pending)
        self._pending = ""
        return text


def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """强制杀死进程及其所有子进程（Windows taskkill /T，POSIX 杀进程组）"""
    if proc.returncode is not None:
        return
    try:
        if os.name == "nt":
            subprocess.Popen(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, OSError):
        try:
            proc.kill()
        except (ProcessLookupError, OSError):
            pass


class LocalCommandStream:
    """一条本地 Shell 命令的流式执行句柄（带哨兵回传 cwd/退出码与超时强杀）

    spawn_args 为 None 时经平台默认 Shell（create_subprocess_shell）执行；
    显式给出时（如 NoSandbox 的 bash/cmd）走 create_subprocess_exec——
    但 cmd.exe 的引号解析与 MSVC 转义规则冲突，会破坏重定向路径，
    因此 cmd 仍回退到 create_subprocess_shell。
    """

    def __init__(
        self,
        *,
        cwd: str,
        posix: bool,
        timeout: int = 600,
        spawn_args: Optional[List[str]] = None,
        spawn_kwargs: Optional[dict] = None,
        cwd_mapper: Optional[Callable[[str], str]] = None,
    ):
        self.cwd = cwd
        self.posix = posix
        self.timeout = timeout
        self._spawn_args = spawn_args
        self._spawn_kwargs = spawn_kwargs or {}
        self._cwd_mapper = cwd_mapper
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.exit_code: Optional[int] = None
        self.new_cwd: Optional[str] = None
        self._send: Optional[Callable[[str], Awaitable[None]]] = None
        self._task: Optional[asyncio.Task] = None

    # ---- 句柄接口 ----

    def start(self, command: str, send: Callable[[str], Awaitable[None]]) -> "LocalCommandStream":
        """开始执行命令，send 为可见输出的异步回调；立即返回，wait() 等待结束"""
        self._send = send
        self._task = asyncio.create_task(self._run(command))
        return self

    async def wait(self) -> int:
        if self._task:
            await self._task
        return self.exit_code if self.exit_code is not None else -1

    def kill(self) -> None:
        proc = self.proc
        if proc is None or proc.returncode is not None:
            return
        _kill_process_tree(proc)

    # ---- 内部 ----

    def _is_cmd_shell(self) -> bool:
        if self._spawn_args is None:
            return os.name == "nt"
        return "cmd" in os.path.basename(self._spawn_args[0]).lower()

    async def _run(self, command: str) -> None:
        try:
            command = command.replace("\r", " ").replace("\n", " ").strip()
            if not command:
                self.exit_code = 0
                return

            line = sentinel_line(command, self.posix)
            common = dict(
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=self.cwd,
                **self._spawn_kwargs,
            )
            try:
                # spawn 本身也可能卡死（如 Windows 上 MSYS/杀软拖慢进程创建）：
                # 给一个独立短超时，避免整个会话永久悬死
                if self._spawn_args and not self._is_cmd_shell():
                    proc = await asyncio.wait_for(
                        asyncio.create_subprocess_exec(*self._spawn_args, line, **common),
                        timeout=_SPAWN_TIMEOUT,
                    )
                else:
                    # cmd.exe 用 MSVC 转义会破坏哨兵里的重定向引号，走 shell 拼接路径
                    proc = await asyncio.wait_for(
                        asyncio.create_subprocess_shell(line, **common), timeout=_SPAWN_TIMEOUT
                    )
            except asyncio.TimeoutError:
                self.exit_code = -1
                await self._safe_send("[atri] Shell 进程创建超时，请重试\n")
                return
            except (OSError, NotImplementedError) as e:
                self.exit_code = -1
                await self._safe_send(f"[atri] 无法启动 Shell：{e}\n")
                return

            self.proc = proc
            pump = asyncio.create_task(self._pump_output(proc))

            timed_out = False
            try:
                await asyncio.wait_for(proc.wait(), timeout=self.timeout)
            except asyncio.TimeoutError:
                timed_out = True
                self.kill()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass
            try:
                await asyncio.wait_for(pump, timeout=_PUMP_GRACE)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pump.cancel()

            if self.exit_code is None:
                self.exit_code = proc.returncode if proc.returncode is not None else -1
            if timed_out:
                await self._safe_send(f"\n[atri] 命令超过 {self.timeout} 秒未结束，已终止\n")
        except asyncio.CancelledError:
            self.kill()
        except Exception as e:  # 任何异常都不能让 wait() 悬死
            self.exit_code = -1
            await self._safe_send(f"\n[atri] 执行出错：{e}\n")

    async def _pump_output(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        decoder = StreamDecoder()
        marker = MarkerStreamFilter()
        total = 0
        truncated = False
        while True:
            chunk = await proc.stdout.read(8192)
            if not chunk:
                break
            total += len(chunk)
            out, new_cwd, exit_code = marker.feed(decoder.feed(chunk))
            if new_cwd:
                self.new_cwd = self._cwd_mapper(new_cwd) if self._cwd_mapper else new_cwd
            if exit_code is not None:
                self.exit_code = exit_code
            if total > MAX_STREAM_OUTPUT:
                if not truncated:
                    truncated = True
                    await self._safe_send("\n[atri] 输出超过 4 MB，后续内容已截断\n")
            elif out:
                await self._safe_send(out)
        tail = marker.feed(decoder.flush())[0] + marker.flush()
        if tail:
            await self._safe_send(tail)

    async def _safe_send(self, text: str) -> None:
        if self._send is None:
            return
        try:
            await self._send(text)
        except Exception:
            pass  # 下游（WebSocket）已断开
