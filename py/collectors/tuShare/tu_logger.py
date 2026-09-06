"""
统一日志模块 - 用于所有 tu_*.py 采集脚本
支持控制台输出和文件写入（可配置）
"""
import os
import logging
from logging import handlers

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL = os.environ.get('TUSHARE_LOG_LEVEL', 'INFO').upper()

def get_logger(name, log_to_file=True, log_to_console=True):
    """获取配置好的 logger"""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    if logger.handlers:
        return logger
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    if log_to_console:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    if log_to_file:
        log_file = os.path.join(LOG_DIR, f'{name}.log')
        fh = handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

def log_result(logger, success, message, data_count=None, elapsed=None):
    """统一输出采集结果"""
    if success:
        msg = f"✅ SUCCESS: {message}"
        if data_count is not None:
            msg += f" (rows: {data_count})"
        if elapsed is not None:
            msg += f" in {elapsed:.2f}s"
        logger.info(msg)
    else:
        logger.error(f"❌ FAILED: {message}")