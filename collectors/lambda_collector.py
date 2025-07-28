#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lambda资源收集器
"""

from .base_collector import BaseCollector
from datetime import datetime, timedelta


class LambdaCollector(BaseCollector):
    def scan_region(self, region):
        """扫描单个区域的Lambda函数"""
        services = []
        try:
            lambda_client = self.get_client('lambda', region)
            cloudwatch = self.get_client('cloudwatch', region)
            
            response = lambda_client.list_functions()
            
            for func in response['Functions']:
                try:
                    # 获取过去24小时的调用次数
                    metrics = cloudwatch.get_metric_statistics(
                        Namespace='AWS/Lambda',
                        MetricName='Invocations',
                        Dimensions=[{'Name': 'FunctionName', 'Value': func['FunctionName']}],
                        StartTime=datetime.now() - timedelta(hours=24),
                        EndTime=datetime.now(),
                        Period=3600,
                        Statistics=['Sum']
                    )
                    
                    total_invocations = sum(point['Sum'] for point in metrics['Datapoints']) if metrics['Datapoints'] else 0
                    
                    if total_invocations > 0:
                        memory_gb = func['MemorySize'] / 1024
                        avg_duration = 1000  # 假设平均执行1秒
                        
                        hourly_invocations = total_invocations / 24
                        compute_cost = hourly_invocations * memory_gb * (avg_duration/1000) * 0.0000166667
                        request_cost = hourly_invocations * 0.0000002
                        hourly_cost = compute_cost + request_cost
                        
                        services.append({
                            'service': 'Lambda',
                            'resource_id': func['FunctionName'],
                            'region': region,
                            'instance_type': f"{func['MemorySize']}MB ({int(total_invocations)}次/24h)",
                            'hourly_cost': hourly_cost,
                            'daily_cost': hourly_cost * 24
                        })
                except Exception:
                    continue
                    
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"扫描Lambda失败 ({region}): {e}")
            else:
                print(f"扫描Lambda失败 ({region}): {e}")
        return services
    
    def scan_all_regions(self):
        """扫描所有区域的Lambda函数"""
        all_services = []
        for region in self.regions:
            all_services.extend(self.scan_region(region))
        return all_services