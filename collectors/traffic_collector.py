#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS流量费用收集器
"""

import boto3
from datetime import datetime, timedelta
from .base_collector import BaseCollector


class TrafficCollector(BaseCollector):
    def __init__(self, session=None, price_manager=None):
        super().__init__(session, price_manager)
        self.traffic_costs = []
    
    def scan_region(self, region):
        """扫描单个区域的流量费用"""
        traffic_data = []
        
        # 1. EC2 Public IP 流量费用
        ec2_traffic = self._get_ec2_traffic(region)
        traffic_data.extend(ec2_traffic)
        
        # 2. NAT Gateway 流量费用
        nat_traffic = self._get_nat_gateway_traffic(region)
        traffic_data.extend(nat_traffic)
        
        # 3. VPC 端点流量费用
        vpc_endpoint_traffic = self._get_vpc_endpoint_traffic(region)
        traffic_data.extend(vpc_endpoint_traffic)
        
        # 4. ELB 流量费用
        elb_traffic = self._get_elb_traffic(region)
        traffic_data.extend(elb_traffic)
        
        return traffic_data
    
    def scan_all_regions(self):
        """扫描所有区域的流量费用"""
        all_traffic = []
        
        for region in self.regions:
            try:
                region_traffic = self.scan_region(region)
                all_traffic.extend(region_traffic)
            except Exception as e:
                print(f"扫描区域 {region} 流量费用失败: {e}")
        
        # 添加全球服务流量费用
        global_traffic = self._get_global_traffic_costs()
        all_traffic.extend(global_traffic)
        
        self.traffic_costs = all_traffic
        return all_traffic
    
    def _get_ec2_traffic(self, region):
        """获取EC2 Public IP流量费用"""
        traffic_data = []
        
        try:
            ec2_client = self.get_client('ec2', region)
            cloudwatch = self.get_client('cloudwatch', region)
            
            # 获取有Public IP的EC2实例
            instances = ec2_client.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )['Reservations']
            
            for reservation in instances:
                for instance in reservation['Instances']:
                    # 检查是否有Public IP
                    public_ip = instance.get('PublicIpAddress')
                    if not public_ip:
                        continue
                    
                    instance_id = instance['InstanceId']
                    instance_type = instance.get('InstanceType', 'unknown')
                    
                    # 获取过去30天的网络流量数据
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=30)
                    
                    try:
                        # 获取网络输出字节数
                        network_out = cloudwatch.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName='NetworkOut',
                            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,  # 1天
                            Statistics=['Sum']
                        )
                        
                        total_bytes_out = sum([point['Sum'] for point in network_out['Datapoints']])
                        total_gb_out = total_bytes_out / (1024**3)  # 转换为GB
                        
                        # 估算数据传输出费用（简化计算）
                        # 前1GB免费，后续$0.09/GB
                        if total_gb_out > 1:
                            transfer_cost = (total_gb_out - 1) * 0.09
                        else:
                            transfer_cost = 0
                        
                        if total_gb_out > 0 or transfer_cost > 0:  # 只显示有流量的实例
                            traffic_data.append({
                                'service': 'EC2',
                                'resource_id': instance_id,
                                'region': region,
                                'hourly_cost': round(transfer_cost / 30 / 24, 6),
                                'daily_cost': round(transfer_cost / 30, 4),
                                'monthly_cost': round(transfer_cost, 4),
                                'details': {
                                    'traffic_type': 'Data Transfer Out',
                                    'volume_gb': round(total_gb_out, 2),
                                    'unit_price': 0.09,
                                    'instance_type': instance_type,
                                    'public_ip': public_ip,
                                    'free_tier_used': min(total_gb_out, 1)
                                },
                                'last_updated': datetime.now().isoformat()
                            })
                            
                    except Exception as e:
                        print(f"获取EC2 {instance_id} 流量数据失败: {e}")
                        
        except Exception as e:
            print(f"获取EC2流量费用失败 ({region}): {e}")
        
        return traffic_data
    
    def _get_nat_gateway_traffic(self, region):
        """获取NAT Gateway流量费用"""
        traffic_data = []
        
        try:
            ec2_client = self.get_client('ec2', region)
            cloudwatch = self.get_client('cloudwatch', region)
            
            # 获取NAT Gateway列表
            nat_gateways = ec2_client.describe_nat_gateways()['NatGateways']
            
            for nat in nat_gateways:
                if nat['State'] != 'available':
                    continue
                
                nat_id = nat['NatGatewayId']
                
                # 获取过去30天的流量数据
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=30)
                
                # 获取字节处理量
                bytes_response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/NATGateway',
                    MetricName='BytesOutToDestination',
                    Dimensions=[{'Name': 'NatGatewayId', 'Value': nat_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,  # 1天
                    Statistics=['Sum']
                )
                
                total_bytes = sum([point['Sum'] for point in bytes_response['Datapoints']])
                total_gb = total_bytes / (1024**3)  # 转换为GB
                
                # NAT Gateway 数据处理费用: $0.045/GB
                processing_cost = total_gb * 0.045
                
                traffic_data.append({
                    'service': 'NAT Gateway',
                    'resource_id': nat_id,
                    'region': region,
                    'hourly_cost': round(processing_cost / 30 / 24, 6),
                    'daily_cost': round(processing_cost / 30, 4),
                    'monthly_cost': round(processing_cost, 4),
                    'details': {
                        'traffic_type': 'Data Processing',
                        'volume_gb': round(total_gb, 2),
                        'unit_price': 0.045,
                        'subnet_id': nat.get('SubnetId', ''),
                        'vpc_id': nat.get('VpcId', '')
                    },
                    'last_updated': datetime.now().isoformat()
                })
                
        except Exception as e:
            print(f"获取NAT Gateway流量费用失败 ({region}): {e}")
        
        return traffic_data
    
    def _get_vpc_endpoint_traffic(self, region):
        """获取VPC端点流量费用"""
        traffic_data = []
        
        try:
            ec2_client = self.get_client('ec2', region)
            cloudwatch = self.get_client('cloudwatch', region)
            
            # 获取VPC端点列表
            vpc_endpoints = ec2_client.describe_vpc_endpoints()['VpcEndpoints']
            
            for endpoint in vpc_endpoints:
                if endpoint['State'] != 'Available':
                    continue
                
                endpoint_id = endpoint['VpcEndpointId']
                endpoint_type = endpoint['VpcEndpointType']
                
                # 只计算Interface类型的端点（Gateway类型免费）
                if endpoint_type == 'Interface':
                    # Interface端点按小时收费: $0.01/小时
                    hours_per_month = 24 * 30
                    hourly_cost = hours_per_month * 0.01
                    
                    # 数据处理费用: $0.01/GB
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=30)
                    
                    try:
                        # 尝试获取流量数据（如果可用）
                        bytes_response = cloudwatch.get_metric_statistics(
                            Namespace='AWS/VPC',
                            MetricName='BytesTransferred',
                            Dimensions=[{'Name': 'VpcEndpointId', 'Value': endpoint_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,
                            Statistics=['Sum']
                        )
                        
                        total_bytes = sum([point['Sum'] for point in bytes_response['Datapoints']])
                        total_gb = total_bytes / (1024**3)
                        data_processing_cost = total_gb * 0.01
                    except:
                        total_gb = 0
                        data_processing_cost = 0
                    
                    total_cost = hourly_cost + data_processing_cost
                    
                    traffic_data.append({
                        'service': 'VPC Endpoint',
                        'resource_id': endpoint_id,
                        'region': region,
                        'hourly_cost': round(total_cost / 30 / 24, 6),
                        'daily_cost': round(total_cost / 30, 4),
                        'monthly_cost': round(total_cost, 4),
                        'details': {
                            'traffic_type': 'Interface Endpoint',
                            'volume_gb': round(total_gb, 2),
                            'hourly_base_cost': round(hourly_cost, 4),
                            'data_processing_cost': round(data_processing_cost, 4),
                            'service_name': endpoint.get('ServiceName', ''),
                            'vpc_id': endpoint.get('VpcId', '')
                        },
                        'last_updated': datetime.now().isoformat()
                    })
                    
        except Exception as e:
            print(f"获取VPC端点流量费用失败 ({region}): {e}")
        
        return traffic_data
    
    def _get_elb_traffic(self, region):
        """获取ELB流量费用"""
        traffic_data = []
        
        try:
            elb_client = self.get_client('elbv2', region)
            cloudwatch = self.get_client('cloudwatch', region)
            
            # 获取负载均衡器列表
            load_balancers = elb_client.describe_load_balancers()['LoadBalancers']
            
            for lb in load_balancers:
                if lb['State']['Code'] != 'active':
                    continue
                
                lb_arn = lb['LoadBalancerArn']
                lb_name = lb['LoadBalancerName']
                lb_type = lb['Type']
                
                # 获取过去30天的流量数据
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=30)
                
                # 获取处理的字节数
                bytes_response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/ApplicationELB' if lb_type == 'application' else 'AWS/NetworkELB',
                    MetricName='ProcessedBytes',
                    Dimensions=[{'Name': 'LoadBalancer', 'Value': lb_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=['Sum']
                )
                
                total_bytes = sum([point['Sum'] for point in bytes_response['Datapoints']])
                total_gb = total_bytes / (1024**3)
                
                # ELB数据处理费用
                if lb_type == 'application':
                    # ALB: $0.008/GB
                    unit_price = 0.008
                elif lb_type == 'network':
                    # NLB: $0.006/GB
                    unit_price = 0.006
                else:
                    # Classic LB: $0.008/GB
                    unit_price = 0.008
                
                processing_cost = total_gb * unit_price
                
                traffic_data.append({
                    'service': 'ELB',
                    'resource_id': lb_name,
                    'region': region,
                    'hourly_cost': round(processing_cost / 30 / 24, 6),
                    'daily_cost': round(processing_cost / 30, 4),
                    'monthly_cost': round(processing_cost, 4),
                    'details': {
                        'traffic_type': f'{lb_type.upper()} Data Processing',
                        'volume_gb': round(total_gb, 2),
                        'unit_price': unit_price,
                        'load_balancer_type': lb_type,
                        'vpc_id': lb.get('VpcId', '')
                    },
                    'last_updated': datetime.now().isoformat()
                })
                
        except Exception as e:
            print(f"获取ELB流量费用失败 ({region}): {e}")
        
        return traffic_data
    
    def _get_global_traffic_costs(self):
        """获取全球服务流量费用"""
        traffic_data = []
        
        try:
            # CloudFront 流量费用
            cloudfront_traffic = self._get_cloudfront_traffic()
            traffic_data.extend(cloudfront_traffic)
            
            # Route 53 查询费用
            route53_traffic = self._get_route53_traffic()
            traffic_data.extend(route53_traffic)
            
        except Exception as e:
            print(f"获取全球流量费用失败: {e}")
        
        return traffic_data
    
    def _get_cloudfront_traffic(self):
        """获取CloudFront流量费用"""
        traffic_data = []
        
        try:
            cloudfront = self.session.client('cloudfront')
            cloudwatch = self.session.client('cloudwatch', region_name='us-east-1')
            
            # 获取CloudFront分配列表
            distributions = cloudfront.list_distributions()
            
            if 'Items' not in distributions['DistributionList']:
                return traffic_data
            
            for dist in distributions['DistributionList']['Items']:
                dist_id = dist['Id']
                domain_name = dist['DomainName']
                
                # 获取过去30天的流量数据
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=30)
                
                # 获取字节下载量
                bytes_response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/CloudFront',
                    MetricName='BytesDownloaded',
                    Dimensions=[{'Name': 'DistributionId', 'Value': dist_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=['Sum']
                )
                
                total_bytes = sum([point['Sum'] for point in bytes_response['Datapoints']])
                total_gb = total_bytes / (1024**3)
                
                # CloudFront 流量费用（简化定价）
                # 前10TB: $0.085/GB, 后续更便宜
                if total_gb <= 10240:  # 10TB
                    unit_price = 0.085
                    traffic_cost = total_gb * unit_price
                else:
                    # 简化计算，实际应该分层计算
                    unit_price = 0.070
                    traffic_cost = total_gb * unit_price
                
                traffic_data.append({
                    'service': 'CloudFront',
                    'resource_id': dist_id,
                    'region': 'Global',
                    'hourly_cost': round(traffic_cost / 30 / 24, 6),
                    'daily_cost': round(traffic_cost / 30, 4),
                    'monthly_cost': round(traffic_cost, 4),
                    'details': {
                        'traffic_type': 'Data Transfer Out',
                        'volume_gb': round(total_gb, 2),
                        'unit_price': unit_price,
                        'domain_name': domain_name,
                        'status': dist.get('Status', '')
                    },
                    'last_updated': datetime.now().isoformat()
                })
                
        except Exception as e:
            print(f"获取CloudFront流量费用失败: {e}")
        
        return traffic_data
    
    def _get_route53_traffic(self):
        """获取Route 53查询费用"""
        traffic_data = []
        
        try:
            route53 = self.session.client('route53')
            cloudwatch = self.session.client('cloudwatch', region_name='us-east-1')
            
            # 获取托管区域列表
            hosted_zones = route53.list_hosted_zones()['HostedZones']
            
            for zone in hosted_zones:
                zone_id = zone['Id'].split('/')[-1]
                zone_name = zone['Name']
                
                # 获取过去30天的查询数据
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=30)
                
                try:
                    query_response = cloudwatch.get_metric_statistics(
                        Namespace='AWS/Route53',
                        MetricName='QueryCount',
                        Dimensions=[{'Name': 'HostedZoneId', 'Value': zone_id}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=86400,
                        Statistics=['Sum']
                    )
                    
                    total_queries = sum([point['Sum'] for point in query_response['Datapoints']])
                    
                    # Route 53 查询费用: $0.40/百万次查询
                    query_cost = (total_queries / 1000000) * 0.40
                    
                    traffic_data.append({
                        'service': 'Route 53',
                        'resource_id': zone_id,
                        'region': 'Global',
                        'hourly_cost': round(query_cost / 30 / 24, 6),
                        'daily_cost': round(query_cost / 30, 4),
                        'monthly_cost': round(query_cost, 4),
                        'details': {
                            'traffic_type': 'DNS Queries',
                            'query_count': int(total_queries),
                            'unit_price': 0.40,
                            'zone_name': zone_name
                        },
                        'last_updated': datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    print(f"获取Route 53区域 {zone_name} 查询数据失败: {e}")
                    
        except Exception as e:
            print(f"获取Route 53流量费用失败: {e}")
        
        return traffic_data
    
    def get_data_transfer_out_estimate(self, region='us-east-1'):
        """估算数据传输出费用"""
        # AWS数据传输出定价（简化）
        pricing_tiers = [
            (1, 0.09),      # 前1GB免费，后续$0.09/GB
            (10240, 0.085), # 前10TB: $0.085/GB
            (51200, 0.070), # 10TB-50TB: $0.070/GB
            (153600, 0.050) # 50TB-150TB: $0.050/GB
        ]
        
        return {
            'service': 'Data Transfer Out',
            'region': region,
            'pricing_tiers': pricing_tiers,
            'note': '实际费用需要根据具体流量计算'
        }
    
    def calculate_total_traffic_cost(self):
        """计算总流量费用"""
        if not self.traffic_costs:
            return 0
        
        total_cost = sum([item.get('monthly_cost', 0) for item in self.traffic_costs])
        return round(total_cost, 2)
    
    def get_traffic_summary(self):
        """获取流量费用摘要"""
        if not self.traffic_costs:
            return {}
        
        summary = {}
        
        for item in self.traffic_costs:
            service = item['service']
            cost = item.get('monthly_cost', 0)
            
            if service not in summary:
                summary[service] = {
                    'total_cost': 0,
                    'resource_count': 0,
                    'total_volume_gb': 0
                }
            
            summary[service]['total_cost'] += cost
            summary[service]['resource_count'] += 1
            summary[service]['total_volume_gb'] += item.get('details', {}).get('volume_gb', 0)
        
        # 四舍五入
        for service in summary:
            summary[service]['total_cost'] = round(summary[service]['total_cost'], 2)
            summary[service]['total_volume_gb'] = round(summary[service]['total_volume_gb'], 2)
        
        return summary