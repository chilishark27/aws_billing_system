#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库配置管理
"""

import os


def get_db_config():
    """获取数据库配置"""
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    if db_type == 'sqlite':
        return {
            'type': 'sqlite',
            'path': os.getenv('DB_PATH', 'data/cost_history.db')
        }
    elif db_type == 'postgresql':
        return {
            'type': 'postgresql',
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'aws_cost_monitor')
        }
    elif db_type == 'mysql':
        return {
            'type': 'mysql',
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'aws_cost_monitor')
        }
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")


# 数据库配置示例
DB_CONFIG_EXAMPLES = {
    'sqlite': {
        'type': 'sqlite',
        'path': 'data/cost_history.db'
    },
    'postgresql': {
        'type': 'postgresql',
        'host': 'localhost',
        'port': 5432,
        'user': 'postgres',
        'password': 'password',
        'database': 'aws_cost_monitor'
    },
    'mysql': {
        'type': 'mysql',
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'password',
        'database': 'aws_cost_monitor'
    }
}