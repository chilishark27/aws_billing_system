#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DynamoDB资源收集器
"""

from .base_collector import BaseCollector


class DynamoDBCollector(BaseCollector):
    def scan_region(self, region):
        """扫描单个区域的DynamoDB表"""
        services = []
        try:
            dynamodb = self.get_client('dynamodb', region)
            tables = dynamodb.list_tables()
            
            for table_name in tables['TableNames']:
                try:
                    table_info = dynamodb.describe_table(TableName=table_name)
                    table = table_info['Table']
                    
                    if table['TableStatus'] == 'ACTIVE':
                        billing_mode = table.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED')
                        
                        if billing_mode == 'PAY_PER_REQUEST':
                            # 按需计费模式 - 基础成本很低
                            hourly_cost = 0.001
                            instance_type = "On-Demand"
                        else:
                            # 预置容量模式
                            read_capacity = table.get('ProvisionedThroughput', {}).get('ReadCapacityUnits', 0)
                            write_capacity = table.get('ProvisionedThroughput', {}).get('WriteCapacityUnits', 0)
                            
                            # RCU: $0.00013/小时, WCU: $0.00065/小时
                            hourly_cost = (read_capacity * 0.00013) + (write_capacity * 0.00065)
                            instance_type = f"Provisioned (R:{read_capacity}, W:{write_capacity})"
                        
                        services.append({
                            'service': 'DynamoDB',
                            'resource_id': table_name,
                            'region': region,
                            'instance_type': instance_type,
                            'hourly_cost': hourly_cost,
                            'daily_cost': hourly_cost * 24
                        })
                except Exception:
                    continue
                    
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"扫描DynamoDB失败 ({region}): {e}")
            else:
                print(f"扫描DynamoDB失败 ({region}): {e}")
        return services
    
    def scan_all_regions(self):
        """扫描所有区域的DynamoDB表"""
        all_services = []
        for region in self.regions:
            all_services.extend(self.scan_region(region))
        return all_services