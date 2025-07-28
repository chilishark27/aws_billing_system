#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EBS资源收集器
"""

from .base_collector import BaseCollector


class EBSCollector(BaseCollector):
    def scan_region(self, region):
        """扫描单个区域的EBS卷"""
        services = []
        try:
            ec2 = self.get_client('ec2', region)
            response = ec2.describe_volumes()
            
            for volume in response['Volumes']:
                if volume['State'] == 'in-use':
                    size_gb = volume['Size']
                    volume_type = volume['VolumeType']
                    
                    price_per_gb = self.price_manager.get_ebs_price(volume_type, region)
                    monthly_cost = size_gb * price_per_gb
                    daily_cost = monthly_cost / 30
                    hourly_cost = daily_cost / 24
                    
                    services.append({
                        'service': 'EBS',
                        'resource_id': volume['VolumeId'],
                        'region': region,
                        'instance_type': f"{volume_type} {size_gb}GB",
                        'hourly_cost': hourly_cost,
                        'daily_cost': daily_cost
                    })
        except Exception as e:
            print(f"扫描EBS失败 ({region}): {e}")
        return services
    
    def scan_all_regions(self):
        """扫描所有区域的EBS卷"""
        all_services = []
        for region in self.regions:
            all_services.extend(self.scan_region(region))
        return all_services