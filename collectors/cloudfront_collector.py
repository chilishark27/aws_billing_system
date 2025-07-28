#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CloudFront资源收集器
"""

from .base_collector import BaseCollector


class CloudFrontCollector(BaseCollector):
    def scan_region(self, region):
        """CloudFront是全球服务，只在us-east-1扫描"""
        if region != 'us-east-1':
            return []
        
        services = []
        try:
            cloudfront = self.get_client('cloudfront', 'us-east-1')
            distributions = cloudfront.list_distributions()
            
            if 'Items' in distributions['DistributionList']:
                for dist in distributions['DistributionList']['Items']:
                    if dist['Enabled']:
                        # CloudFront有免费额度: 每月前1TB流量和10万请求免费
                        # 大部分小型应用都在免费额度内
                        daily_cost = 0.0  # 设为免费
                        hourly_cost = 0.0
                        
                        services.append({
                            'service': 'CloudFront',
                            'resource_id': dist['Id'],
                            'region': 'us-east-1',
                            'instance_type': 'Distribution (Free Tier)',
                            'hourly_cost': hourly_cost,
                            'daily_cost': daily_cost
                        })
                        
        except Exception as e:
            print(f"扫描CloudFront失败: {e}")
        return services
    
    def scan_all_regions(self):
        """CloudFront只需要扫描一次"""
        return self.scan_region('us-east-1')