#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志系统模块
提供统一的日志记录功能，替代直接使用print
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from lude.config.paths import LOGS_DIR

# 确保日志目录存在
os.makedirs(LOGS_DIR, exist_ok=True)

# 日志格式
FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 日志级别映射
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL
}

# 创建一个字典来跟踪已经初始化的logger
_loggers = {}

def setup_logger(name, log_file=None, level="info"):
    """设置并返回一个命名的logger实例
    
    Args:
        name: logger的名称，通常为模块名
        log_file: 日志文件名，如不指定则只输出到控制台
        level: 日志级别，默认为"info"
        
    Returns:
        logger: 配置好的logger实例
    """
    global _loggers

    # 检查是否已经创建过此logger
    if name in _loggers:
        return _loggers[name]
    
    # 创建新的logger
    logger = logging.getLogger(name)
    
    # 设置日志级别
    log_level = LOG_LEVELS.get(level.lower(), logging.INFO)
    logger.setLevel(log_level)
    
    # 🚨 修复：允许传播到父级logger，确保异常能到达stderr
    # 注意：这可能导致重复日志，但异常处理更重要
    logger.propagate = True
    
    # 移除所有已有的处理器，确保不会重复添加
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(FORMATTER)
    logger.addHandler(console_handler)
    
    # 如果指定了日志文件，添加文件处理器
    if log_file:
        file_path = os.path.join(LOGS_DIR, log_file)
        file_handler = RotatingFileHandler(
            file_path, maxBytes=10485760, backupCount=5, encoding='utf-8'
        )
        file_handler.setFormatter(FORMATTER)
        logger.addHandler(file_handler)
    
    # 将logger添加到跟踪字典中
    _loggers[name] = logger
    
    return logger

# 创建默认的应用级logger
app_logger = setup_logger("lude", "lude.log")

# 创建一个专门用于优化过程的logger
optimization_logger = setup_logger("lude.optimization", "optimization.log")

# 创建一个专门用于钉钉通知的logger
dingtalk_logger = setup_logger("lude.dingtalk", "dingtalk.log")
