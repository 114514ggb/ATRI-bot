"""安全日志轮转的单元测试

覆盖：文件被占用（另一进程/句柄打开）时轮转失败不抛异常、日志继续写入、
rolloverAt 顺延重试；占用解除后轮转恢复正常并生成归档文件；
ATRI_FILE_LOG=0 时不创建文件 handler。
"""

import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler

import pytest

from atribot.core.logger import Logger, SafeTimedRotatingFileHandler

win_only = pytest.mark.skipif(
    not sys.platform.startswith("win"), reason="依赖 Windows 的文件占用语义"
)


def _record(msg: str) -> logging.LogRecord:
    return logging.LogRecord("atri-bot", logging.INFO, __file__, 1, msg, None, None)


def _make_handler(tmp_path, cls=SafeTimedRotatingFileHandler):
    handler = cls(
        filename=str(tmp_path / "test_log_"),
        when="S", interval=1, backupCount=7, encoding="utf-8",
    )
    return handler


@win_only
def test_blocked_rotation_degrades_to_append(tmp_path):
    """文件被占用时：轮转失败不抛异常，日志继续写进当前文件，rolloverAt 顺延"""
    handler = _make_handler(tmp_path)
    blocker = open(handler.baseFilename, "a", encoding="utf-8")
    try:
        handler.rolloverAt = int(time.time()) - 1  # 强制下一条日志触发轮转

        handler.emit(_record("占用期间的消息"))  # 不应抛出 PermissionError

        with open(handler.baseFilename, encoding="utf-8") as f:
            assert "占用期间的消息" in f.read()  # 记录没有丢
        assert list(tmp_path.glob("test_log_.*")) == []  # 没有产生半成品归档

        # rolloverAt 顺延到 retry_delay 之后，避免每条日志都重试刷屏
        now = int(time.time())
        assert abs(handler.rolloverAt - (now + SafeTimedRotatingFileHandler.retry_delay)) <= 2

        # 顺延期间后续日志正常写入
        handler.emit(_record("第二条"))
        with open(handler.baseFilename, encoding="utf-8") as f:
            assert "第二条" in f.read()
    finally:
        blocker.close()
        handler.close()


@win_only
def test_rotation_succeeds_after_blocker_released(tmp_path):
    """占用解除后：轮转恢复正常，归档文件生成，新日志写入新的当前文件"""
    handler = _make_handler(tmp_path)
    handler.emit(_record("轮转前的消息"))

    blocker = open(handler.baseFilename, "a", encoding="utf-8")
    handler.rolloverAt = int(time.time()) - 1
    handler.emit(_record("占用期间的消息"))  # 轮转失败，顺延
    blocker.close()

    handler.rolloverAt = int(time.time()) - 1  # 再次触发轮转（重试）
    handler.emit(_record("轮转后的消息"))

    try:
        backups = list(tmp_path.glob("test_log_.*"))
        assert len(backups) == 1  # 归档文件生成
        with open(backups[0], encoding="utf-8") as f:
            content = f.read()
            assert "轮转前的消息" in content and "占用期间的消息" in content

        with open(handler.baseFilename, encoding="utf-8") as f:
            current = f.read()
        assert "轮转后的消息" in current and "轮转前的消息" not in current

        assert handler.rolloverAt > int(time.time())  # rolloverAt 已恢复正常推进
    finally:
        handler.close()


@win_only
def test_stock_handler_still_raises_for_contrast(tmp_path):
    """对照组：标准 handler 在同样场景下轮转会抛 PermissionError（即线上刷屏的来源）"""
    handler = _make_handler(tmp_path, cls=TimedRotatingFileHandler)
    blocker = open(handler.baseFilename, "a", encoding="utf-8")
    try:
        handler.rolloverAt = int(time.time()) - 1
        with pytest.raises(PermissionError):
            handler.doRollover()
    finally:
        blocker.close()
        handler.close()


@pytest.mark.parametrize("env_value,expect_file_handler", [("0", False), ("1", True)])
def test_logger_file_logging_env_switch(monkeypatch, env_value, expect_file_handler):
    """ATRI_FILE_LOG=0 时不创建文件 handler（dev_server 多进程场景）"""
    monkeypatch.setenv("ATRI_FILE_LOG", env_value)
    logger = logging.getLogger("atri-bot")
    logger.handlers.clear()

    try:
        Logger()
        file_handlers = [
            h for h in logger.handlers
            if isinstance(h, (SafeTimedRotatingFileHandler, TimedRotatingFileHandler))
        ]
        assert bool(file_handlers) is expect_file_handler
        assert logger.handlers  # 控制台 handler 始终存在
        if expect_file_handler:
            # 日志目录锚定在项目 atribot/log，而不是随 cwd 漂移
            assert file_handlers[0].baseFilename.endswith(
                os.path.join("atribot", "log", "atri_log_")
            )
    finally:
        for h in logger.handlers:
            h.close()
        logger.handlers.clear()
        monkeypatch.delenv("ATRI_FILE_LOG", raising=False)
