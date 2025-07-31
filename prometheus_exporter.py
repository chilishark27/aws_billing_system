#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS成本监控 Prometheus 指标暴露器
"""

from prometheus_client import start_http_server, Gauge, Info
from database.db_manager import DatabaseManager
from utils.db_config import get_db_config
import json
import time
import logging

# 定义Prometheus指标
aws_cost_daily_total = Gauge('aws_cost_daily_total_usd', 'AWS每日总成本(美元)')
aws_cost_hourly_total = Gauge('aws_cost_hourly_total_usd', 'AWS每小时总成本(美元)')
aws_cost_monthly_total = Gauge('aws_cost_monthly_total_usd', 'AWS当月总成本(美元)')

aws_cost_by_service = Gauge('aws_cost_daily_by_service_usd', 'AWS每日服务成本(美元)', ['service'])
aws_cost_by_resource = Gauge('aws_cost_daily_by_resource_usd', 'AWS每日资源成本(美元)', ['service', 'resource_id', 'region'])

aws_cost_info = Info('aws_cost_collection_info', 'AWS成本收集信息')

class PrometheusExporter:
    def __init__(self, port=9090):
        self.port = port
        self.db_manager = DatabaseManager(get_db_config())
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def update_metrics(self):
        """更新Prometheus指标"""
        try:
            # 获取最新汇总数据
            summary = self.db_manager.get_latest_summary()
            if not summary:
                self.logger.warning("没有找到成本数据")
                return
            
            # 更新总成本指标
            aws_cost_daily_total.set(summary['total_daily_cost'])
            aws_cost_hourly_total.set(summary['total_hourly_cost'])
            
            # 更新服务成本指标
            if summary.get('service_breakdown'):
                try:
                    service_breakdown = json.loads(summary['service_breakdown'])
                    for service, cost in service_breakdown.items():
                        aws_cost_by_service.labels(service=service).set(cost)
                except:
                    pass
            
            # 获取当月总成本
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            from datetime import datetime
            current_month = datetime.now().strftime('%Y-%m')
            cursor.execute('SELECT total_monthly_cost FROM monthly_summary WHERE year_month = ?', (current_month,))
            monthly_result = cursor.fetchone()
            
            if monthly_result:
                aws_cost_monthly_total.set(monthly_result[0])
            
            # 获取详细资源成本
            cursor.execute('''
                SELECT service_type, resource_id, region, daily_cost 
                FROM cost_records 
                WHERE timestamp = ?
            ''', (summary['timestamp'],))
            
            resources = cursor.fetchall()
            for resource in resources:
                service_type, resource_id, region, daily_cost = resource
                aws_cost_by_resource.labels(
                    service=service_type,
                    resource_id=resource_id,
                    region=region
                ).set(daily_cost)
            
            conn.close()
            
            # 更新信息指标
            aws_cost_info.info({
                'last_update': summary['timestamp'],
                'total_resources': str(len(resources)),
                'collection_status': 'success'
            })
            
            self.logger.info(f"指标更新成功 - 每日成本: ${summary['total_daily_cost']:.4f}")
            
        except Exception as e:
            self.logger.error(f"更新指标失败: {e}")
            aws_cost_info.info({
                'collection_status': 'error',
                'error_message': str(e)
            })
    
    def start_server(self):
        """启动Prometheus指标服务器"""
        start_http_server(self.port)
        self.logger.info(f"Prometheus指标服务器启动在端口 {self.port}")
        self.logger.info(f"指标访问地址: http://localhost:{self.port}/metrics")
        
        while True:
            self.update_metrics()
            time.sleep(60)  # 每分钟更新一次指标

if __name__ == '__main__':
    exporter = PrometheusExporter(port=9090)
    exporter.start_server()