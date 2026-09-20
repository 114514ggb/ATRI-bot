import logging
import os
import re
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """自定义带颜色的日志格式化器"""

    grey = "\x1b[38;20m"      # 灰色 (浅黑色)
    green = "\x1b[32;20m"     # 绿色
    yellow = "\x1b[33;20m"    # 黄色
    red = "\x1b[31;20m"       # 红色
    bold_red = "\x1b[31;1m"   # 粗体红色
    reset = "\x1b[0m"         # 重置颜色和样式
    
    format_str = "%(asctime)s [%(levelname)s] %(name)s | %(message)s"
    
    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%m-%d %H:%M:%S")
        return formatter.format(record)

class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """轮转失败时降级为继续写当前文件的 TimedRotatingFileHandler

    Windows 上若日志文件同时被其他进程打开（第二个实例、dev_server、编辑器等），
    标准实现的 os.rename 会抛 PermissionError，且 rolloverAt 不前进，
    导致之后每条日志都重试轮转、失败并刷 "--- Logging error ---"。
    这里捕获失败：重开当前文件继续写，并把 rolloverAt 顺延一小段时间后重试。
    """

    retry_delay = 300
    """轮转失败后到下次重试的间隔（秒）"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.shouldRollover(record):
                self.doRollover()
        except OSError:
            # 多为文件被其他进程占用而无法改名：继续写当前文件，稍后重试
            if self.stream is None:
                self.stream = self._open()
            self.rolloverAt = int(time.time()) + self.retry_delay
        logging.FileHandler.emit(self, record)


class Logger:
    def __init__(self, name='atri-bot', log_level=logging.DEBUG):

        self.logger: logging.Logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        
        if not self.logger.handlers:

            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(ColoredFormatter())
            self.logger.addHandler(console_handler)

            log_dir = Path(__file__).resolve().parents[1] / "log"
            os.makedirs(log_dir, exist_ok=True)

            # ATRI_FILE_LOG=0 时只输出到控制台
            if os.environ.get("ATRI_FILE_LOG", "1") != "0":
                file_handler = SafeTimedRotatingFileHandler(
                    filename=str(log_dir / "atri_log_"),
                    when="midnight",  # 时间单位天
                    interval=1,       # 每1天
                    backupCount=7,    # 保留的文件数量
                    encoding='utf-8'
                )
                file_handler.suffix = "%Y-%m-%d.log"
                file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}.log$")
                file_handler.setFormatter(logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s | %(message)s (%(filename)s:%(lineno)d)",
                    datefmt="%m-%d %H:%M:%S"
                ))
                self.logger.addHandler(file_handler)
    
    def get_logger(self) -> logging.Logger:
        return self.logger

    def get_child(self, name: str) -> logging.Logger:
        """获取一个继承当前日志器 handler 的子日志器(atri-bot.<name>)

        子日志器自动将日志传播到父日志器，无需重复配置 handler
        """
        return self.logger.getChild(name)


def get_named_logger(name: str) -> logging.Logger:
    """快捷函数：获取一个名为 atri-bot.<name> 的日志器

    用于不想通过容器获取日志器的场景
    """
    return logging.getLogger(f"atri-bot.{name}")


if __name__ == "__main__":
    logger = Logger().get_logger()

    logger.debug("这是一条debug信息")
    logger.info("这是一条info信息")
    logger.warning("这是一条warning信息")
    logger.error("这是一条error信息")
    logger.critical("这是一条critical信息")

    child = logger.getChild("Test")
    child.info("这是一条来自子日志器 atri-bot.Test 的测试信息")
    child.error("子日志器错误测试")
    