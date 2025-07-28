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
from collectors.ec2_collector import EC2Collector
from collectors.vpc_collector import VPCCollector
from collectors.rds_collector import RDSCollector


class CostCollectorV2:
    def __init__(self):
        self.session = boto3.Session()
        self.price_manager = PriceManager()
        self.db_manager = DatabaseManager(get_db_config())
        
        # 初始化各种收集器
        self.ec2_collector = EC2Collector(self.session, self.price_manager)
        self.vpc_collector = VPCCollector(self.session, self.price_manager)
        self.rds_collector = RDSCollector(self.session, self.price_manager)
    
    def get_running_services(self):
        """使用多线程获取所有运行中的服务"""
        all_services = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            # 提交收集任务
            futures.append(executor.submit(self.ec2_collector.scan_all_regions))
            futures.append(executor.submit(self.vpc_collector.scan_all_regions))
            futures.append(executor.submit(self.rds_collector.scan_all_regions))
            
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
        print(f"[{datetime.now()}] 开始收集成本数据...")
        
        # 检查月度重置
        self.db_manager.check_monthly_reset()
        
        # 刷新价格缓存
        self.price_manager.refresh_cache()
        
        # 获取服务数据
        services = self.get_running_services()
        
        # 保存到数据库
        total_hourly, total_daily, service_breakdown = self.db_manager.save_cost_data(services)
        
        print(f"收集完成: {len(services)}个服务, 每小时${total_hourly:.2f}, 每日${total_daily:.2f}")
        
        # 更新月度统计
        self.db_manager.update_monthly_summary(total_daily, service_breakdown)
    
    def start_scheduler(self):
        """启动定时任务"""
        print("AWS成本监控器V2启动...")
        
        # 立即执行一次
        self.collect_and_save()
        
        # 每小时执行
        schedule.every().hour.do(self.collect_and_save)
        
        print("定时任务已设置 (每小时执行)")
        
        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == '__main__':
    collector = CostCollectorV2()
    collector.start_scheduler()