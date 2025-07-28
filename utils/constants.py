#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
常量定义
"""

# AWS区域列表
AWS_REGIONS = [
    'us-east-1', 'us-west-2', 'ap-southeast-1', 
    'ap-east-1', 'eu-west-1', 'ap-northeast-1'
]

# Public IP价格 (2024年2月1日起)
PUBLIC_IP_HOURLY_RATE = 0.005  # $0.005/小时

# 缓存过期时间 (小时)
PRICE_CACHE_EXPIRY_HOURS = 4

# 数据库路径
DEFAULT_DB_PATH = 'data/cost_history.db'