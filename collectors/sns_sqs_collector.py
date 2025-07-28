#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SNS和SQS资源收集器
"""

from .base_collector import BaseCollector


class SNSSQSCollector(BaseCollector):
    def scan_region(self, region):
        """扫描单个区域的SNS和SQS资源"""
        services = []
        
        # SNS主题 - 按量付费，有免费额度
        try:
            sns = self.get_client('sns', region)
            topics = sns.list_topics()
            
            for topic in topics['Topics']:
                # SNS: 前100万次发布免费，超出部分$0.50/百万次
                # 大部分小型应用在免费额度内
                hourly_cost = 0.0  # 免费额度内
                
                services.append({
                    'service': 'SNS',
                    'resource_id': topic['TopicArn'].split(':')[-1],
                    'region': region,
                    'instance_type': 'Topic (Free Tier)',
                    'hourly_cost': hourly_cost,
                    'daily_cost': hourly_cost * 24
                })
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"扫描SNS失败 ({region}): {e}")
        
        # SQS队列 - 按量付费，有免费额度
        try:
            sqs = self.get_client('sqs', region)
            queues = sqs.list_queues()
            
            for queue_url in queues.get('QueueUrls', []):
                queue_name = queue_url.split('/')[-1]
                
                # SQS: 前100万次请求免费，超出部分$0.40/百万次
                # 大部分小型应用在免费额度内
                hourly_cost = 0.0  # 免费额度内
                
                services.append({
                    'service': 'SQS',
                    'resource_id': queue_name,
                    'region': region,
                    'instance_type': 'Queue (Free Tier)',
                    'hourly_cost': hourly_cost,
                    'daily_cost': hourly_cost * 24
                })
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"扫描SQS失败 ({region}): {e}")
        
        return services
    
    def scan_all_regions(self):
        """扫描所有区域的SNS和SQS资源"""
        all_services = []
        for region in self.regions:
            all_services.extend(self.scan_region(region))
        return all_services