#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDS资源收集器
"""

from .base_collector import BaseCollector


class RDSCollector(BaseCollector):
    def scan_region(self, region):
        """扫描单个区域的RDS实例"""
        services = []
        try:
            rds = self.get_client('rds', region)
            response = rds.describe_db_instances()
            
            for db in response['DBInstances']:
                if db['DBInstanceStatus'] == 'available':
                    hourly_cost = self.price_manager.get_rds_price(db['DBInstanceClass'], region)
                    services.append({
                        'service': 'RDS',
                        'resource_id': db['DBInstanceIdentifier'],
                        'region': region,
                        'instance_type': db['DBInstanceClass'],
                        'hourly_cost': hourly_cost,
                        'daily_cost': hourly_cost * 24
                    })
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"扫描RDS失败 ({region}): {e}")
            else:
                print(f"扫描RDS失败 ({region}): {e}")
        return services
    
    def scan_all_regions(self):
        """扫描所有区域的RDS实例"""
        all_services = []
        for region in self.regions:
            all_services.extend(self.scan_region(region))
        return all_services