#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础资源收集器
"""

import boto3
from abc import ABC, abstractmethod


class BaseCollector(ABC):
    def __init__(self, session=None, price_manager=None):
        self.session = session or boto3.Session()
        self.price_manager = price_manager
        self.regions = ['us-east-1', 'us-west-2', 'ap-southeast-1', 'ap-east-1', 'eu-west-1', 'ap-northeast-1']
    
    @abstractmethod
    def scan_region(self, region):
        """扫描单个区域的资源"""
        pass
    
    @abstractmethod
    def scan_all_regions(self):
        """扫描所有区域的资源"""
        pass
    
    def get_client(self, service, region):
        """获取AWS客户端"""
        return self.session.client(service, region_name=region)