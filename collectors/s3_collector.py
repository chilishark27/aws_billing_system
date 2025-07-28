#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S3资源收集器
"""

from .base_collector import BaseCollector
from datetime import datetime, timedelta


class S3Collector(BaseCollector):
    def scan_region(self, region):
        """S3是全球服务，只在us-east-1扫描"""
        if region != 'us-east-1':
            return []
        
        services = []
        try:
            s3 = self.get_client('s3', 'us-east-1')
            cloudwatch = self.get_client('cloudwatch', 'us-east-1')
            
            response = s3.list_buckets()
            
            for bucket in response['Buckets']:
                try:
                    # 获取存储桶大小
                    metrics = cloudwatch.get_metric_statistics(
                        Namespace='AWS/S3',
                        MetricName='BucketSizeBytes',
                        Dimensions=[
                            {'Name': 'BucketName', 'Value': bucket['Name']},
                            {'Name': 'StorageType', 'Value': 'StandardStorage'}
                        ],
                        StartTime=datetime.now() - timedelta(days=2),
                        EndTime=datetime.now(),
                        Period=86400,
                        Statistics=['Average']
                    )
                    
                    size_bytes = metrics['Datapoints'][-1]['Average'] if metrics['Datapoints'] else 0
                    size_gb = size_bytes / (1024**3)
                    
                    if size_gb > 0.001:  # 只统计大于1MB的存储桶
                        price_per_gb = self.price_manager.get_s3_price('Standard', 'us-east-1')
                        billable_gb = max(0, size_gb - 5)  # 前5GB免费
                        monthly_cost = billable_gb * price_per_gb
                        daily_cost = monthly_cost / 30
                        hourly_cost = daily_cost / 24
                        
                        services.append({
                            'service': 'S3',
                            'resource_id': bucket['Name'],
                            'region': 'us-east-1',
                            'instance_type': f"{size_gb:.2f}GB",
                            'hourly_cost': hourly_cost,
                            'daily_cost': daily_cost
                        })
                except Exception as bucket_error:
                    continue
                    
        except Exception as e:
            print(f"扫描S3失败: {e}")
        return services
    
    def scan_all_regions(self):
        """S3只需要扫描一次"""
        return self.scan_region('us-east-1')