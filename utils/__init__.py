# -*- coding: utf-8 -*-
"""
日志工具模块
提供统一的日志记录功能
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from functools import wraps
import time
from config import LOG_CONFIG


def setup_logger(name: str = 'nba_prediction') -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的Logger对象
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_CONFIG['level']))
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 确保日志目录存在
    log_file = LOG_CONFIG['file']
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 文件处理器 - 支持日志轮转
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_CONFIG['max_bytes'],
        backupCount=LOG_CONFIG['backup_count'],
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter(LOG_CONFIG['format'])
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# 全局日志记录器
logger = setup_logger()


def log_function_call(func):
    """
    装饰器：记录函数调用日志
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"调用函数: {func.__name__}")
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.debug(f"函数 {func.__name__} 执行成功，耗时: {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"函数 {func.__name__} 执行失败，耗时: {elapsed:.2f}s，错误: {str(e)}")
            raise
    return wrapper


def log_crawler_progress(func):
    """
    装饰器：记录爬虫进度
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(f"开始爬虫任务: {func.__name__}")
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(f"爬虫任务 {func.__name__} 完成，耗时: {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"爬虫任务 {func.__name__} 失败，耗时: {elapsed:.2f}s，错误: {str(e)}")
            raise
    return wrapper
