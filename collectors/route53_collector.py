#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Route53资源收集器
"""

from .base_collector import BaseCollector


class Route53Collector(BaseCollector):
    def scan_region(self, region):
        """Route53是全球服务，只在us-east-1扫描"""
        if region != 'us-east-1':
            return []
        
        services = []
        try:
            route53 = self.get_client('route53', 'us-east-1')
            zones = route53.list_hosted_zones()
            
            for zone in zones['HostedZones']:
                # 托管区域: $0.50/月
                monthly_cost = 0.50
                daily_cost = monthly_cost / 30
                hourly_cost = daily_cost / 24
                
                services.append({
                    'service': 'Route53',
                    'resource_id': zone['Id'].split('/')[-1],
                    'region': 'us-east-1',
                    'instance_type': f"Hosted Zone ({zone['Name']})",
                    'hourly_cost': hourly_cost,
                    'daily_cost': daily_cost
                })
                
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"扫描Route53失败: {e}")
            else:
                print(f"扫描Route53失败: {e}")
        return services
    
    def scan_all_regions(self):
        """Route53只需要扫描一次"""
        return self.scan_region('us-east-1')