#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EC2资源收集器
"""

from .base_collector import BaseCollector


class EC2Collector(BaseCollector):
    def scan_region(self, region):
        """扫描单个区域的EC2实例"""
        services = []
        try:
            ec2 = self.get_client('ec2', region)
            response = ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )
            
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    hourly_cost = self.price_manager.get_ec2_price(instance['InstanceType'], region)
                    services.append({
                        'service': 'EC2',
                        'resource_id': instance['InstanceId'],
                        'region': region,
                        'instance_type': instance['InstanceType'],
                        'hourly_cost': hourly_cost,
                        'daily_cost': hourly_cost * 24
                    })
        except Exception as e:
            print(f"扫描EC2失败 ({region}): {e}")
        return services
    
    def scan_all_regions(self):
        """扫描所有区域的EC2实例"""
        all_services = []
        for region in self.regions:
            all_services.extend(self.scan_region(region))
        return all_services