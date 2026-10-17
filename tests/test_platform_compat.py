"""跨平台兼容性测试

覆盖各模块中针对 Windows / POSIX 分支处理的纯函数逻辑，防止改动时回归：

- `atribot.common_utils.net_utils`：端口探测（Windows 下不设 SO_REUSEADDR）
- `atribot.core.atri_config.FilePathConfig.apply_path_mapping`：盘符/大小写不敏感的路径前缀映射
- `atribot.core.type.chat_message_types.File`：本地路径 → `file://` 前缀构造
- `atribot.LLMchat.sandbox.factory`：沙盒后端类型归一化
- `atribot.LLMchat.sandbox.no_sandbox`：本地后端的 shell 解析（Windows 分支不依赖 Unix 工具）

运行：uv run python -m pytest tests/test_platform_compat.py -q
"""

import os
import socket
import sys
from pathlib import Path

import pytest

from atribot.common_utils.net_utils import is_port_in_use, try_bind_port
from atribot.core.atri_config import FilePathConfig
from atribot.core.type.chat_message_types import File
from atribot.LLMchat.sandbox.factory import normalize_sandbox_type
from atribot.LLMchat.sandbox.no_sandbox import NoSandbox


class TestNetUtils:
    """端口探测"""

    def test_try_bind_port_returns_bound_socket(self):
        """成功绑定时返回已绑定但未监听的 socket，端口与请求一致"""
        sock = try_bind_port("127.0.0.1", 0)
        assert sock is not None
        try:
            assert sock.getsockname()[1] > 0
        finally:
            sock.close()

    def test_try_bind_port_failure_modes(self):
        """端口被占用 / 端口越界时返回 None"""
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        try:
            assert is_port_in_use("127.0.0.1", port) is True
            assert try_bind_port("127.0.0.1", port) is None
        finally:
            occupied.close()
        # 越界端口: socket 抛 OverflowError, 应被吞掉并返回 None
        assert try_bind_port("127.0.0.1", 70000) is None


class TestApplyPathMapping:
    """路径前缀映射（大小写不敏感、最长前缀优先、分隔符归一）"""

    def test_maps_windows_drive_to_wsl_prefix(self):
        """Windows 盘符路径映射为 WSL 挂载路径"""
        mapping = {"E:/程序文件/python/ATRI-main": "/mnt/e/程序文件/python/ATRI-main"}
        assert (
            FilePathConfig.apply_path_mapping("E:/程序文件/python/ATRI-main/document/a.png", mapping)
            == "/mnt/e/程序文件/python/ATRI-main/document/a.png"
        )

    def test_mapping_is_case_insensitive(self):
        """前缀匹配不区分大小写"""
        mapping = {"E:/Data": "/mnt/e/data"}
        assert FilePathConfig.apply_path_mapping("e:/data/file.txt", mapping) == "/mnt/e/data/file.txt"

    def test_backslashes_are_normalized(self):
        """反斜杠路径先归一为正斜杠再匹配"""
        mapping = {"E:/Data": "/mnt/e/data"}
        assert FilePathConfig.apply_path_mapping(r"E:\Data\sub\file.txt", mapping) == "/mnt/e/data/sub/file.txt"

    def test_longest_prefix_wins(self):
        """多条映射时最长前缀优先"""
        mapping = {
            "E:/a": "/mnt/e/a",
            "E:/a/b": "/mnt/e/ab",
        }
        assert FilePathConfig.apply_path_mapping("E:/a/b/c.txt", mapping) == "/mnt/e/ab/c.txt"

    def test_unmatched_or_empty_mapping_is_noop(self):
        """未命中前缀 / 空映射时原样返回"""
        mapping = {"E:/a": "/mnt/e/a"}
        assert FilePathConfig.apply_path_mapping("D:/other/x.txt", mapping) == "D:/other/x.txt"
        assert FilePathConfig.apply_path_mapping("E:/a/b.txt", {}) == "E:/a/b.txt"


class TestFileUrlConstruction:
    """File 封装类的协议前缀（Windows 盘符不再被破坏）"""

    def test_factory_prefixes(self):
        """本地路径加 file://（反斜杠原样保留）, URL 不加前缀, base64 加 base64://"""
        assert File.from_local_path("D:/x/y.png").file == "file://D:/x/y.png"
        assert File.from_local_path(r"D:\x\y.png").file == r"file://D:\x\y.png"
        assert File.from_url("https://example.com/a.png").file == "https://example.com/a.png"
        assert File.from_base64("aGVsbG8=").file == "base64://aGVsbG8="

    def test_detect_type_by_scheme(self):
        """按前缀识别来源类型"""
        assert File.detect_type("file://D:/x.png") == "local"
        assert File.detect_type("http://a/b") == "http"
        assert File.detect_type("https://a/b") == "https"
        assert File.detect_type("base64://abc") == "base64"
        assert File.detect_type("D:/x.png") == "unknown"


class TestSandboxTypeNormalization:
    """沙盒后端类型归一化"""

    @pytest.mark.parametrize("value", ["none", "no_sandbox", "nosandbox", "local", "NONE", " Local "])
    def test_local_aliases(self, value):
        assert normalize_sandbox_type(value) == "local"

    def test_e2b(self):
        assert normalize_sandbox_type("e2b") == "e2b"

    @pytest.mark.parametrize("value", ["docker", "", None, "unknown-backend"])
    def test_defaults_to_docker(self, value):
        assert normalize_sandbox_type(value) == "docker"


class TestNoSandboxShellResolution:
    """本地直执行后端的 shell 解析与工作区路径"""

    def test_work_dir_is_posix_style(self, tmp_path):
        """工作区路径统一转成正斜杠（工具层按 posix 路径拼接）"""
        sandbox = NoSandbox(config={"work_dir": str(tmp_path)})
        assert "\\" not in sandbox.work_dir
        assert Path(sandbox.work_dir).resolve() == Path(tmp_path).resolve()

    @pytest.mark.skipif(sys.platform != "win32", reason="仅 Windows 分支")
    def test_windows_shell_is_not_wsl_bash(self, tmp_path):
        """Windows 上必须排除 System32 下的 WSL bash 存根"""
        bash = NoSandbox._find_windows_bash()
        if bash:
            system32 = os.path.join(os.environ.get("SystemRoot", "C:/Windows"), "System32").lower()
            assert system32 not in bash.lower()