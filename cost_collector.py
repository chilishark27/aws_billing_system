#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS成本数据收集器 V2 - 模块化版本
"""

import boto3
import schedule
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from pricing.price_manager import PriceManager
from database.db_manager import DatabaseManager
from utils.db_config import get_db_config
from utils.logger import setup_logger, get_log_config
from collectors.ec2_collector import EC2Collector
from collectors.vpc_collector import VPCCollector
from collectors.rds_collector import RDSCollector
from collectors.ebs_collector import EBSCollector
from collectors.s3_collector import S3Collector
from collectors.cloudfront_collector import CloudFrontCollector
from collectors.lambda_collector import LambdaCollector
from collectors.elb_collector import ELBCollector
from collectors.route53_collector import Route53Collector
from collectors.dynamodb_collector import DynamoDBCollector
from collectors.sns_sqs_collector import SNSSQSCollector


class CostCollectorV2:
    def __init__(self):
        self.session = boto3.Session()
        self.price_manager = PriceManager()
        # 设置日志
        log_config = get_log_config()
        self.logger = setup_logger('aws_cost_collector', log_config['path'], log_config['level'])
        
        self.db_manager = DatabaseManager(get_db_config())
        
        # 初始化各种收集器
        collectors = [
            EC2Collector(self.session, self.price_manager),
            VPCCollector(self.session, self.price_manager),
            RDSCollector(self.session, self.price_manager),
            EBSCollector(self.session, self.price_manager),
            S3Collector(self.session, self.price_manager),
            CloudFrontCollector(self.session, self.price_manager),
            LambdaCollector(self.session, self.price_manager),
            ELBCollector(self.session, self.price_manager),
            Route53Collector(self.session, self.price_manager),
            DynamoDBCollector(self.session, self.price_manager),
            SNSSQSCollector(self.session, self.price_manager)
        ]
        
        # 传递logger给收集器
        for collector in collectors:
            collector.logger = self.logger
        
        self.collectors = collectors
    
    def get_running_services(self):
        """使用多线程获取所有运行中的服务"""
        all_services = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            # 提交收集任务
            for collector in self.collectors:
                futures.append(executor.submit(collector.scan_all_regions))
            
            # 收集结果
            for future in as_completed(futures):
                try:
                    services = future.result()
                    all_services.extend(services)
                except Exception as e:
                    print(f"扫描任务失败: {e}")
        
        return all_services
    
    def collect_and_save(self):
        """收集并保存成本数据"""
        self.logger.info("开始收集成本数据...")
        
        # 检查月度重置
        self.db_manager.check_monthly_reset()
        
        # 刷新价格缓存
        self.price_manager.refresh_cache()
        
        # 获取服务数据
        services = self.get_running_services()
        
        # 保存到数据库
        total_hourly, total_daily, service_breakdown = self.db_manager.save_cost_data(services)
        
        self.logger.info(f"收集完成: {len(services)}个服务, 每小时${total_hourly:.2f}, 每日${total_daily:.2f}")
        
        # 更新月度统计
        self.db_manager.update_monthly_summary(total_daily, service_breakdown)
    
    def start_scheduler(self):
        """启动定时任务"""
        self.logger.info("AWS成本监控器V2启动...")
        
        # 立即执行一次
        self.collect_and_save()
        
        # 每小时执行
        schedule.every().hour.do(self.collect_and_save)
        
        self.logger.info("定时任务已设置 (每小时执行)")
        
        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == '__main__':
    collector = CostCollectorV2()
    collector.start_scheduler()