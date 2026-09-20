"""终端：WebSocket 在 bot 所在主机上执行 Shell 命令

命令执行/输出流/哨兵解析复用 sandbox.stream_exec 共享核心；
鉴权与日志流一致——拿到面板令牌即等于拿到主机权限，令牌务必妥善保管。
"""

import asyncio
import getpass
import os
import re
import socket
import subprocess
import sys
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket

from atribot.LLMchat.sandbox.stream_exec import LocalCommandStream

from ..deps import _ws_auth

router = APIRouter()

_IS_WINDOWS = sys.platform == "win32"

_CMD_TIMEOUT = 600  # 单条命令最长运行秒数
_COMPLETION_LIMIT = 100

_UNIX_BUILTINS = (
    "cd", "ls", "pwd", "echo", "cat", "grep", "rm", "cp", "mv", "mkdir", "rmdir", "touch",
    "chmod", "chown", "ps", "kill", "top", "df", "du", "tar", "curl", "wget", "ssh", "scp",
    "nano", "vim", "head", "tail", "wc", "find", "sed", "awk", "sort", "uniq", "man", "which",
    "env", "export", "source", "alias", "history", "clear", "exit", "sudo", "systemctl",
    "journalctl", "apt", "apt-get", "yum", "dnf", "pacman", "docker", "git", "python", "python3",
    "pip", "pip3", "node", "npm",
)

_WIN_BUILTINS = (
    "cd", "dir", "echo", "type", "copy", "del", "ren", "md", "rd", "move", "cls", "set", "ver",
    "where", "findstr", "more", "tasklist", "taskkill", "exit", "rem", "mklink", "robocopy",
    "attrib", "chcp", "color", "title", "call", "start", "pause", "shift", "for", "if", "goto",
    "pushd", "popd", "setlocal", "endlocal", "sc", "net", "reg", "schtasks", "curl", "tar",
)

_commands_cache: Optional[frozenset] = None


def _scan_path_commands() -> frozenset:
    """扫描 PATH 上的可执行文件名（不含扩展名），合并内置命令，结果进程内缓存"""
    global _commands_cache
    if _commands_cache is not None:
        return _commands_cache
    names = set(_WIN_BUILTINS if _IS_WINDOWS else _UNIX_BUILTINS)
    exts = {e.lower() for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";")} if _IS_WINDOWS else set()
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        if not path_dir:
            continue
        try:
            with os.scandir(path_dir) as it:
                for entry in it:
                    try:
                        if _IS_WINDOWS:
                            stem, ext = os.path.splitext(entry.name)
                            if ext.lower() in exts and stem:
                                names.add(stem.lower())
                        elif entry.is_file() and os.access(entry.path, os.X_OK):
                            names.add(entry.name)
                    except OSError:
                        continue
        except OSError:
            continue  # PATH 里有不存在的目录很常见
    names.discard("")
    _commands_cache = frozenset(names)
    return _commands_cache


async def _send(websocket: WebSocket, payload: dict) -> None:
    try:
        await websocket.send_json(payload)
    except Exception:
        pass  # 连接已断开：由外层循环退出清理


class _TerminalSession:
    """单个 WebSocket 连接的终端会话：维护工作目录与正在运行的命令流"""

    def __init__(self) -> None:
        self.cwd = os.path.expanduser("~")
        self.busy = False
        self.stream: Optional[LocalCommandStream] = None

    async def run(self, websocket: WebSocket, cmd: str) -> None:
        self.busy = True
        started = time.monotonic()
        code = -1
        try:
            cmd = cmd.replace("\r", " ").replace("\n", " ").strip()
            if not cmd:
                code = 0
                return

            # 裸盘符切换（如 `D:`）在一次性别名 shell 里无法持久，直接改会话目录
            if _IS_WINDOWS and (m := re.fullmatch(r"([A-Za-z]):\\?", cmd)):
                root = f"{m.group(1).upper()}:\\"
                if os.path.isdir(root):
                    self.cwd = root
                code = 0
                return

            spawn_kwargs = (
                {"creationflags": subprocess.CREATE_NO_WINDOW}
                if _IS_WINDOWS
                else {"start_new_session": True}
            )
            stream = LocalCommandStream(
                cwd=self.cwd,
                posix=not _IS_WINDOWS,
                timeout=_CMD_TIMEOUT,
                spawn_kwargs=spawn_kwargs,
            )
            stream.start(cmd, lambda text: _send(websocket, {"type": "output", "data": text}))
            self.stream = stream
            code = await stream.wait()
            if stream.new_cwd and os.path.isdir(stream.new_cwd):
                self.cwd = os.path.normpath(stream.new_cwd)
        finally:
            if self.stream is not None:
                self.stream.kill()  # 正常结束为空操作；任务被取消时防止孤儿进程
            self.stream = None
            self.busy = False
            await _send(
                websocket,
                {
                    "type": "exit",
                    "code": code,
                    "ms": round((time.monotonic() - started) * 1000),
                    "cwd": self.cwd,
                },
            )


# ---- Tab 补全 ----

def _complete_for(msg: dict, cwd: str) -> List[Dict]:
    frag = str(msg.get("frag") or "")
    frag_match = frag.lower() if _IS_WINDOWS else frag

    if msg.get("first"):
        names = sorted(_scan_path_commands())
        return [
            {"name": n, "dir": False}
            for n in names
            if (n.lower().startswith(frag_match) if _IS_WINDOWS else n.startswith(frag))
        ][:_COMPLETION_LIMIT]

    dir_part = str(msg.get("dir") or "").strip().strip('"')
    if dir_part.startswith("~"):
        base = os.path.expanduser(dir_part)
    else:
        base = dir_part if os.path.isabs(dir_part) else os.path.join(cwd, dir_part)
    base = os.path.normpath(base)
    if not os.path.isdir(base):
        return []

    items: List[Dict] = []
    try:
        with os.scandir(base) as it:
            for entry in it:
                name = entry.name
                matched = name.lower().startswith(frag_match) if _IS_WINDOWS else name.startswith(frag)
                if not matched:
                    continue
                if name.startswith(".") and not frag.startswith("."):
                    continue  # Unix 惯例：除非显式输入 . 前缀，否则不补全隐藏文件
                try:
                    is_dir = entry.is_dir()
                except OSError:
                    is_dir = False
                items.append({"name": name, "dir": is_dir})
                if len(items) >= 300:  # 超大目录扫描上限
                    break
    except OSError:
        return []
    items.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    return items[:_COMPLETION_LIMIT]


@router.websocket("/api/ws/terminal")
async def ws_terminal(websocket: WebSocket, token: str = "") -> None:
    # _ws_auth 内部已 accept（失败时带 4401/4429 关闭）
    if not await _ws_auth(websocket, token):
        return

    session = _TerminalSession()
    try:
        user = await asyncio.to_thread(getpass.getuser)
    except Exception:
        user = "?"
    commands = await asyncio.to_thread(lambda: sorted(_scan_path_commands())[:4000])
    await _send(
        websocket,
        {
            "type": "hello",
            "platform": sys.platform,
            "isWindows": _IS_WINDOWS,
            "cwd": session.cwd,
            "home": os.path.expanduser("~"),
            "user": user,
            "host": socket.gethostname(),
            "sep": os.sep,
            "commands": commands,
        },
    )

    try:
        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")
            if mtype == "exec":
                cmd = str(msg.get("cmd") or "").strip()
                if not cmd or len(cmd) > 8192:
                    continue
                if session.busy:
                    await _send(websocket, {"type": "output", "data": "[atri] 已有命令在执行，请等待完成或先终止\n"})
                    continue
                asyncio.create_task(session.run(websocket, cmd))
            elif mtype == "kill":
                if session.stream is not None:
                    session.stream.kill()
            elif mtype == "ping":
                await _send(websocket, {"type": "pong"})
            elif mtype == "complete":
                if not session.busy:
                    await _send(
                        websocket,
                        {"type": "complete", "id": msg.get("id"), "items": _complete_for(msg, session.cwd)},
                    )
    except Exception:
        pass  # WebSocket 断开或坏帧
    finally:
        if session.stream is not None:
            session.stream.kill()  # 连接关闭时终止仍在运行的命令
