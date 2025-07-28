#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志配置管理
"""

import logging
import os
from datetime import datetime


def setup_logger(name='aws_cost_monitor', log_path=None, level=logging.INFO):
    """设置日志配置"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 清除现有处理器
    logger.handlers.clear()
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    if log_path:
        # 支持绝对路径和相对路径
        if not os.path.isabs(log_path):
            log_path = os.path.abspath(log_path)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_log_config():
    """获取日志配置"""
    log_path = os.getenv('LOG_PATH')
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    level_mapping = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    return {
        'path': log_path,
        'level': level_mapping.get(log_level, logging.INFO)
    }