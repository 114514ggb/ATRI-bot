from logging.handlers import TimedRotatingFileHandler
import logging
import sys
import os

class ColoredFormatter(logging.Formatter):
    """自定义带颜色的日志格式化器"""

    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
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

class Logger:
    def __init__(self, name='atri-bot', log_level=logging.DEBUG):

        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        
        if not self.logger.handlers:

            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(ColoredFormatter())
            self.logger.addHandler(console_handler)

            log_dir = "atribot/log"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            file_handler = TimedRotatingFileHandler(
                filename=f"{log_dir}/atri_log_",
                when="midnight", 
                interval=1,
                backupCount=14, 
                encoding='utf-8'
            )
            file_handler.suffix = "%Y-%m-%d.log"
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s | %(message)s (%(filename)s:%(lineno)d)",
                datefmt="%m-%d %H:%M:%S"
            ))
            self.logger.addHandler(file_handler)
    
    def get_logger(self):
        return self.logger


if __name__ == "__main__":
    logger = Logger().get_logger()
    
    logger.debug("这是一条debug信息")
    logger.info("这是一条info信息")
    logger.warning("这是一条warning信息")
    logger.error("这是一条error信息")
    logger.critical("这是一条critical信息")
    