#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPC资源收集器 (包含Public IP收费)
"""

from .base_collector import BaseCollector


class VPCCollector(BaseCollector):
    def scan_region(self, region):
        """扫描单个区域的VPC资源"""
        services = []
        try:
            ec2 = self.get_client('ec2', region)
            
            # Elastic IP 和 Public IP (2024年2月1日起所有Public IP都收费)
            addresses = ec2.describe_addresses()['Addresses']
            for addr in addresses:
                # 所有Public IP都收费: $0.005/小时
                hourly_cost = self.price_manager.get_public_ip_price(region)
                if 'InstanceId' not in addr:
                    # 未关联的EIP
                    services.append({
                        'service': 'VPC',
                        'resource_id': addr['AllocationId'],
                        'region': region,
                        'instance_type': 'Unused EIP',
                        'hourly_cost': hourly_cost,
                        'daily_cost': hourly_cost * 24
                    })
                else:
                    # 已关联的EIP (现在也收费)
                    services.append({
                        'service': 'VPC',
                        'resource_id': addr['AllocationId'],
                        'region': region,
                        'instance_type': f'EIP (attached to {addr["InstanceId"]})',
                        'hourly_cost': hourly_cost,
                        'daily_cost': hourly_cost * 24
                    })
            
            # EC2实例的Public IP (非EIP)
            instances = ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )['Reservations']
            
            for reservation in instances:
                for instance in reservation['Instances']:
                    # 检查是否有Public IP但不是EIP
                    if instance.get('PublicIpAddress'):
                        # 检查是否不是EIP (EIP会在上面处理)
                        is_eip = any(addr.get('InstanceId') == instance['InstanceId'] for addr in addresses)
                        if not is_eip:
                            # 实例的临时Public IP也收费
                            hourly_cost = self.price_manager.get_public_ip_price(region)
                            services.append({
                                'service': 'VPC',
                                'resource_id': f"public-ip-{instance['InstanceId']}",
                                'region': region,
                                'instance_type': f'Public IP ({instance["InstanceId"]})',
                                'hourly_cost': hourly_cost,
                                'daily_cost': hourly_cost * 24
                            })
            
            # NAT Gateway (包含其Public IP成本)
            nat_gateways = ec2.describe_nat_gateways(
                Filters=[{'Name': 'state', 'Values': ['available']}]
            )['NatGateways']
            
            for nat in nat_gateways:
                # NAT Gateway基础价格
                nat_hourly_cost = self.price_manager.get_nat_gateway_price(region)
                # NAT Gateway的Public IP也要收费
                public_ip_cost = self.price_manager.get_public_ip_price(region)
                total_hourly_cost = nat_hourly_cost + public_ip_cost
                
                services.append({
                    'service': 'VPC',
                    'resource_id': nat['NatGatewayId'],
                    'region': region,
                    'instance_type': 'NAT Gateway (含Public IP)',
                    'hourly_cost': total_hourly_cost,
                    'daily_cost': total_hourly_cost * 24
                })
                
        except Exception as e:
            print(f"扫描VPC失败 ({region}): {e}")
        return services
    
    def scan_all_regions(self):
        """扫描所有区域的VPC资源"""
        all_services = []
        for region in self.regions:
            all_services.extend(self.scan_region(region))
        return all_services