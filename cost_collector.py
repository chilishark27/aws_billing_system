#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS成本数据收集器 - 每小时自动收集成本数据
"""

import boto3
import json
import sqlite3
import schedule
import time
from datetime import datetime, timedelta
import datetime as dt
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import asyncio

class CostCollector:
    def __init__(self):
        self.session = boto3.Session()
        self.regions = ['us-east-1', 'us-west-2', 'ap-southeast-1', 'ap-east-1','eu-west-1', 'ap-northeast-1']
        self.init_database()
        self.lock = threading.Lock()
        self.price_cache = {}  # 价格缓存
        self.cache_expiry = {}  # 缓存过期时间
        
    def init_database(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect('data/cost_history.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cost_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                service_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                region TEXT NOT NULL,
                hourly_cost REAL NOT NULL,
                daily_cost REAL NOT NULL,
                details TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cost_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_hourly_cost REAL NOT NULL,
                total_daily_cost REAL NOT NULL,
                service_breakdown TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lambda_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                region TEXT NOT NULL,
                hourly_cost REAL NOT NULL,
                daily_cost REAL NOT NULL,
                details TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monthly_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year_month TEXT NOT NULL,
                total_monthly_cost REAL NOT NULL,
                service_breakdown TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(year_month)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def scan_ec2_region(self, region):
        """扫描单个区域的EC2实例"""
        services = []
        try:
            ec2 = self.session.client('ec2', region_name=region)
            response = ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )
            
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    hourly_cost = self.get_ec2_price(instance['InstanceType'], region)
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
    
    def scan_rds_region(self, region):
        """扫描单个区域的RDS实例"""
        services = []
        try:
            rds = self.session.client('rds', region_name=region)
            response = rds.describe_db_instances()
            
            for db in response['DBInstances']:
                if db['DBInstanceStatus'] == 'available':
                    hourly_cost = self.get_rds_price(db['DBInstanceClass'], region)
                    services.append({
                        'service': 'RDS',
                        'resource_id': db['DBInstanceIdentifier'],
                        'region': region,
                        'instance_type': db['DBInstanceClass'],
                        'hourly_cost': hourly_cost,
                        'daily_cost': hourly_cost * 24
                    })
        except Exception as e:
            print(f"扫描RDS失败 ({region}): {e}")
        return services
    
    def scan_lambda_region(self, region):
        """扫描Lambda函数 - 只统计有调用的函数"""
        services = []
        try:
            lambda_client = self.session.client('lambda', region_name=region)
            cloudwatch = self.session.client('cloudwatch', region_name=region)
            
            response = lambda_client.list_functions()
            
            for func in response['Functions']:
                # 获取过去24小时的调用次数
                try:
                    metrics = cloudwatch.get_metric_statistics(
                        Namespace='AWS/Lambda',
                        MetricName='Invocations',
                        Dimensions=[{'Name': 'FunctionName', 'Value': func['FunctionName']}],
                        StartTime=datetime.now(datetime.timezone.utc) - timedelta(hours=24),
                        EndTime=datetime.now(datetime.timezone.utc),
                        Period=3600,  # 1小时
                        Statistics=['Sum']
                    )
                    
                    # 计算调用次数
                    total_invocations = sum(point['Sum'] for point in metrics['Datapoints']) if metrics['Datapoints'] else 0
                    
                    # 只有实际有调用的Lambda才计费
                    if total_invocations > 0:
                        # Lambda价格: $0.0000166667/GB-秒 + $0.0000002/请求
                        memory_gb = func['MemorySize'] / 1024
                        avg_duration = 1000  # 假设平均执行1秒
                        
                        # 每小时成本 = (调用次数/24) * (内存成本 + 请求成本)
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
                except Exception as metric_error:
                    # 如果无法获取指标，跳过该函数
                    continue
                    
        except Exception as e:
            print(f"扫描Lambda失败 ({region}): {e}")
        return services
    
    def get_running_services(self):
        """使用多线程获取所有运行中的服务"""
        all_services = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 提交所有扫描任务
            futures = []
            
            # 扫描任务
            for region in self.regions:
                futures.append(executor.submit(self.scan_ec2_region, region))
                futures.append(executor.submit(self.scan_rds_region, region))
                futures.append(executor.submit(self.scan_lambda_region, region))
            
            # 扫描其他服务
            futures.append(executor.submit(self.scan_s3_buckets))
            futures.append(executor.submit(self.scan_ebs_volumes))
            futures.append(executor.submit(self.scan_vpc_resources))
            futures.append(executor.submit(self.scan_cloudwatch_resources))
            futures.append(executor.submit(self.scan_waf_resources))
            futures.append(executor.submit(self.scan_amazonq_resources))
            
            # 扫描各区域的其他服务
            for region in self.regions:
                futures.append(executor.submit(self.scan_fsx_region, region))
                futures.append(executor.submit(self.scan_cloudfront_region, region))
            
            # 收集结果
            for future in as_completed(futures):
                try:
                    services = future.result()
                    all_services.extend(services)
                except Exception as e:
                    print(f"扫描任务失败: {e}")
        
        return all_services
    
    def scan_s3_buckets(self):
        """扫描S3存储桶"""
        services = []
        try:
            s3 = self.session.client('s3')
            cloudwatch = self.session.client('cloudwatch', region_name='us-east-1')
            
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
                        StartTime=datetime.now(datetime.timezone.utc) - timedelta(days=2),
                        EndTime=datetime.now(datetime.timezone.utc),
                        Period=86400,
                        Statistics=['Average']
                    )
                    
                    size_bytes = metrics['Datapoints'][-1]['Average'] if metrics['Datapoints'] else 0
                    size_gb = size_bytes / (1024**3)
                    
                    if size_gb > 0.001:  # 只统计大于1MB的存储桶
                        # 获取S3真实价格
                        price_per_gb = self.get_s3_price('Standard', 'us-east-1')
                        billable_gb = max(0, size_gb - 5)  # 前5GB免费
                        monthly_cost = billable_gb * price_per_gb
                        daily_cost = monthly_cost / 30
                        hourly_cost = daily_cost / 24
                        
                        services.append({
                            'service': 'S3',
                            'resource_id': bucket['Name'],
                            'region': 'us-east-1',  # S3使用us-east-1区域
                            'instance_type': f"{size_gb:.2f}GB",
                            'hourly_cost': hourly_cost,
                            'daily_cost': daily_cost
                        })
                except Exception as bucket_error:
                    # 跳过无法访问的存储桶
                    continue
                    
        except Exception as e:
            print(f"扫描S3失败: {e}")
        return services
    
    def scan_ebs_volumes(self):
        """扫描EBS卷"""
        services = []
        for region in self.regions:
            try:
                ec2 = self.session.client('ec2', region_name=region)
                response = ec2.describe_volumes()
                
                for volume in response['Volumes']:
                    if volume['State'] == 'in-use':
                        size_gb = volume['Size']
                        volume_type = volume['VolumeType']
                        
                        # 获取EBS真实价格
                        price_per_gb = self.get_ebs_price(volume_type, region)
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
    
    def scan_vpc_resources(self):
        """扫描VPC相关资源"""
        services = []
        for region in self.regions:
            try:
                ec2 = self.session.client('ec2', region_name=region)
                
                # NAT Gateway
                nat_gateways = ec2.describe_nat_gateways(
                    Filters=[{'Name': 'state', 'Values': ['available']}]
                )['NatGateways']
                
                for nat in nat_gateways:
                    # 获取NAT Gateway真实价格
                    hourly_cost = self.get_nat_gateway_price(region)
                    services.append({
                        'service': 'VPC',
                        'resource_id': nat['NatGatewayId'],
                        'region': region,
                        'instance_type': 'NAT Gateway',
                        'hourly_cost': hourly_cost,
                        'daily_cost': hourly_cost * 24
                    })
                
                # Elastic IP (未关联的)
                addresses = ec2.describe_addresses()['Addresses']
                for addr in addresses:
                    if 'InstanceId' not in addr:  # 未关联的EIP
                        # EIP价格相对固定
                        hourly_cost = 0.005
                        services.append({
                            'service': 'VPC',
                            'resource_id': addr['AllocationId'],
                            'region': region,
                            'instance_type': 'Unused EIP',
                            'hourly_cost': hourly_cost,
                            'daily_cost': hourly_cost * 24
                        })
                        
            except Exception as e:
                print(f"扫描VPC失败 ({region}): {e}")
        return services
    
    def scan_fsx_region(self, region):
        """扫描FSx文件系统"""
        services = []
        try:
            fsx = self.session.client('fsx', region_name=region)
            response = fsx.describe_file_systems()
            
            for fs in response['FileSystems']:
                if fs['Lifecycle'] == 'AVAILABLE':
                    storage_capacity = fs['StorageCapacity']
                    fs_type = fs['FileSystemType']
                    
                    # FSx价格 (简化)
                    if fs_type == 'WINDOWS':
                        price_per_gb = 0.13  # Windows File Server
                    else:
                        price_per_gb = 0.065  # Lustre
                    
                    monthly_cost = storage_capacity * price_per_gb
                    daily_cost = monthly_cost / 30
                    hourly_cost = daily_cost / 24
                    
                    services.append({
                        'service': 'FSx',
                        'resource_id': fs['FileSystemId'],
                        'region': region,
                        'instance_type': f"{fs_type} {storage_capacity}GB",
                        'hourly_cost': hourly_cost,
                        'daily_cost': daily_cost
                    })
        except Exception as e:
            print(f"扫描FSx失败 ({region}): {e}")
        return services
    
    def scan_cloudwatch_resources(self):
        """扫描CloudWatch资源"""
        services = []
        for region in self.regions:
            try:
                cloudwatch = self.session.client('cloudwatch', region_name=region)
                logs = self.session.client('logs', region_name=region)
                
                # CloudWatch自定义指标
                metrics = cloudwatch.list_metrics()
                custom_metrics = [m for m in metrics['Metrics'] if not m['Namespace'].startswith('AWS/')]
                
                if custom_metrics:
                    # 自定义指标: $0.30/指标/月
                    monthly_cost = len(custom_metrics) * 0.30
                    daily_cost = monthly_cost / 30
                    hourly_cost = daily_cost / 24
                    
                    services.append({
                        'service': 'CloudWatch',
                        'resource_id': f'custom-metrics-{region}',
                        'region': region,
                        'instance_type': f'{len(custom_metrics)} Custom Metrics',
                        'hourly_cost': hourly_cost,
                        'daily_cost': daily_cost
                    })
                
                # CloudWatch Logs
                log_groups = logs.describe_log_groups()['logGroups']
                for log_group in log_groups:
                    if log_group.get('storedBytes', 0) > 0:
                        stored_gb = log_group['storedBytes'] / (1024**3)
                        # Logs存储: $0.50/GB/月
                        monthly_cost = stored_gb * 0.50
                        daily_cost = monthly_cost / 30
                        hourly_cost = daily_cost / 24
                        
                        services.append({
                            'service': 'CloudWatch',
                            'resource_id': log_group['logGroupName'],
                            'region': region,
                            'instance_type': f'Logs {stored_gb:.2f}GB',
                            'hourly_cost': hourly_cost,
                            'daily_cost': daily_cost
                        })
                        
            except Exception as e:
                print(f"扫描CloudWatch失败 ({region}): {e}")
        return services
    
    def scan_waf_resources(self):
        """扫描WAF资源"""
        services = []
        try:
            # WAF v2 (CloudFront和ALB)
            wafv2 = self.session.client('wafv2', region_name='us-east-1')
            
            # CloudFront WAF
            cf_webacls = wafv2.list_web_acls(Scope='CLOUDFRONT')['WebACLs']
            for webacl in cf_webacls:
                # WAF WebACL: $1.00/月 + $0.60/100万请求
                monthly_cost = 1.00  # 基本费用
                daily_cost = monthly_cost / 30
                hourly_cost = daily_cost / 24
                
                services.append({
                    'service': 'WAF',
                    'resource_id': webacl['Id'],
                    'region': 'global',
                    'instance_type': 'CloudFront WebACL',
                    'hourly_cost': hourly_cost,
                    'daily_cost': daily_cost
                })
            
            # Regional WAF
            for region in ['us-east-1', 'us-west-2']:
                try:
                    regional_waf = self.session.client('wafv2', region_name=region)
                    regional_webacls = regional_waf.list_web_acls(Scope='REGIONAL')['WebACLs']
                    
                    for webacl in regional_webacls:
                        monthly_cost = 1.00
                        daily_cost = monthly_cost / 30
                        hourly_cost = daily_cost / 24
                        
                        services.append({
                            'service': 'WAF',
                            'resource_id': webacl['Id'],
                            'region': region,
                            'instance_type': 'Regional WebACL',
                            'hourly_cost': hourly_cost,
                            'daily_cost': daily_cost
                        })
                except:
                    continue
                    
        except Exception as e:
            print(f"扫描WAF失败: {e}")
        return services
    
    def scan_amazonq_resources(self):
        """扫描Amazon Q资源"""
        services = []
        try:
            # Amazon Q是按用户收费的服务
            # 需要通过IAM或CloudTrail获取活跃用户
            iam = self.session.client('iam')
            
            # 获取所有用户
            users = iam.list_users()['Users']
            
            # 简化假设: 检查有密码最后使用时间的用户
            active_users = len([u for u in users if u.get('PasswordLastUsed')])
            
            if active_users > 0:
                # Amazon Q: $20/用户/月
                monthly_cost = active_users * 20
                daily_cost = monthly_cost / 30
                hourly_cost = daily_cost / 24
                
                services.append({
                    'service': 'AMAZONQ',  # 使用大写保持一致性
                    'resource_id': 'amazonq-users',
                    'region': 'us-east-1',
                    'instance_type': f'{active_users} Active Users',
                    'hourly_cost': hourly_cost,
                    'daily_cost': daily_cost
                })
                
        except Exception as e:
            print(f"扫描Amazon Q失败: {e}")
        return services
    
    def scan_cloudfront_region(self, region):
        """扫描CloudFront分发"""
        services = []
        if region != 'us-east-1':  # CloudFront只在us-east-1区域
            return services
            
        try:
            cloudfront = self.session.client('cloudfront', region_name='us-east-1')
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
                            'region': 'us-east-1',  # CloudFront使用us-east-1区域
                            'instance_type': 'Distribution (Free Tier)',
                            'hourly_cost': hourly_cost,
                            'daily_cost': daily_cost
                        })
                        
        except Exception as e:
            print(f"扫描CloudFront失败: {e}")
        return services
    

    
    def get_ec2_price(self, instance_type, region='us-east-1'):
        """获取EC2实时价格"""
        cache_key = f"ec2_{instance_type}_{region}"
        
        # 检查缓存
        if cache_key in self.price_cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                cached_price = self.price_cache[cache_key]
                print(f"使用缓存EC2价格: {instance_type} ({region}) = ${cached_price:.4f}/小时")
                return cached_price
        
        # 直接获取AWS实时价格
        real_price = self.get_real_price_sync(instance_type, region, 'ec2')
        
        if real_price > 0:
            # 缓存价格 (4小时有效)
            self.price_cache[cache_key] = real_price
            self.cache_expiry[cache_key] = datetime.now() + timedelta(hours=4)
            print(f"获取EC2实时价格: {instance_type} ({region}) = ${real_price:.4f}/小时")
            
            # 立即更新数据库中的价格
            threading.Timer(5.0, self.update_database_prices, args=[instance_type, region, 'ec2', real_price]).start()
            
            return real_price
        else:
            # 如果获取失败，使用备用价格
            fallback_price = self.get_ec2_price_fallback(instance_type, region)
            print(f"使用备用EC2价格: {instance_type} ({region}) = ${fallback_price:.4f}/小时")
            return fallback_price
    

    

    
    def _get_location_name(self, region):
        """将AWS区域代码转换为价格API使用的位置名称"""
        location_mapping = {
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'us-west-1': 'US West (N. California)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)',
            'ap-east-1': 'Asia Pacific (Hong Kong)',
            'eu-west-1': 'Europe (Ireland)',
            'eu-central-1': 'Europe (Frankfurt)',
            'ap-south-1': 'Asia Pacific (Mumbai)',
            'ca-central-1': 'Canada (Central)'
        }
        mapped_location = location_mapping.get(region, 'US East (N. Virginia)')
        print(f"区域映射: {region} -> {mapped_location}")
        return mapped_location
    
    def get_rds_price(self, instance_type, region='us-east-1'):
        """获取RDS实时价格"""
        cache_key = f"rds_{instance_type}_{region}"
        
        # 检查缓存
        if cache_key in self.price_cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                cached_price = self.price_cache[cache_key]
                print(f"使用缓存RDS价格: {instance_type} ({region}) = ${cached_price:.4f}/小时")
                return cached_price
        
        # 直接获取AWS实时价格
        real_price = self.get_real_price_sync(instance_type, region, 'rds')
        
        if real_price > 0:
            # 缓存价格 (4小时有效)
            self.price_cache[cache_key] = real_price
            self.cache_expiry[cache_key] = datetime.now() + timedelta(hours=4)
            print(f"获取RDS实时价格: {instance_type} ({region}) = ${real_price:.4f}/小时")
            
            # 立即更新数据库中的价格
            threading.Timer(5.0, self.update_database_prices, args=[instance_type, region, 'rds', real_price]).start()
            
            return real_price
        else:
            # 如果获取失败，使用备用价格
            fallback_price = self.get_rds_price_fallback(instance_type)
            print(f"使用备用RDS价格: {instance_type} ({region}) = ${fallback_price:.4f}/小时")
            return fallback_price
    
    def collect_and_save(self):
        """收集并保存成本数据"""
        print(f"[{datetime.now()}] 开始收集成本数据...")
        
        # 检查是否需要重置月度计费
        self.check_monthly_reset()
        
        # 每天更新一次价格缓存
        self.refresh_price_cache_daily()
        
        services = self.get_running_services()
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect('data/cost_history.db')
        cursor = conn.cursor()
        
        total_hourly = 0
        total_daily = 0
        service_breakdown = defaultdict(float)
        
        # 保存详细记录（排除Lambda）
        for service in services:
            # 只保存非Lambda服务到数据库
            if service['service'] != 'Lambda':
                cursor.execute('''
                    INSERT INTO cost_records 
                    (timestamp, service_type, resource_id, region, hourly_cost, daily_cost, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    service['service'],
                    service['resource_id'],
                    service['region'],
                    service['hourly_cost'],
                    service['daily_cost'],
                    json.dumps(service)
                ))
                
                total_hourly += service['hourly_cost']
                total_daily += service['daily_cost']
                service_breakdown[service['service']] += service['daily_cost']
            else:
                # Lambda数据单独保存到专门的表
                cursor.execute('''
                    INSERT OR REPLACE INTO lambda_records 
                    (timestamp, resource_id, region, hourly_cost, daily_cost, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    service['resource_id'],
                    service['region'],
                    service['hourly_cost'],
                    service['daily_cost'],
                    json.dumps(service)
                ))
        
        # 保存汇总记录
        cursor.execute('''
            INSERT INTO cost_summary 
            (timestamp, total_hourly_cost, total_daily_cost, service_breakdown)
            VALUES (?, ?, ?, ?)
        ''', (
            timestamp,
            total_hourly,
            total_daily,
            json.dumps(dict(service_breakdown))
        ))
        
        conn.commit()
        conn.close()
        
        print(f"收集完成: {len(services)}个服务, 每小时${total_hourly:.2f}, 每日${total_daily:.2f}")
        
        # 更新月度统计
        self.update_monthly_summary(total_daily, service_breakdown)
        
        # 价格已在扫描过程中获取并缓存
    
    def get_ec2_price_fallback(self, instance_type, region='us-east-1'):
        """备用EC2价格表"""
        prices = {
            # t2 系列
            't2.nano': 0.0058, 't2.micro': 0.0116, 't2.small': 0.023, 't2.medium': 0.0464, 't2.large': 0.0928, 't2.xlarge': 0.1856,
            # t3 系列
            't3.nano': 0.0052, 't3.micro': 0.0104, 't3.small': 0.0208, 't3.medium': 0.0416, 't3.large': 0.0832, 't3.xlarge': 0.1664,
            # t3a 系列
            't3a.nano': 0.0047, 't3a.micro': 0.0094, 't3a.small': 0.0188, 't3a.medium': 0.0376, 't3a.large': 0.0752, 't3a.xlarge': 0.1504,
            # t4g 系列 (ARM)
            't4g.nano': 0.0042, 't4g.micro': 0.0084, 't4g.small': 0.0168, 't4g.medium': 0.0336, 't4g.large': 0.0672, 't4g.xlarge': 0.1344,
            # m5 系列
            'm5.large': 0.096, 'm5.xlarge': 0.192, 'm5.2xlarge': 0.384, 'm5.4xlarge': 0.768,
            'm5a.large': 0.086, 'm5a.xlarge': 0.172, 'm5a.2xlarge': 0.344,
            'm6i.large': 0.0864, 'm6i.xlarge': 0.1728, 'm6a.large': 0.0864, 'm6a.xlarge': 0.1728,
            # c5 系列
            'c5.large': 0.085, 'c5.xlarge': 0.17, 'c5.2xlarge': 0.34, 'c5.4xlarge': 0.68,
            'c5a.large': 0.077, 'c5a.xlarge': 0.154, 'c6i.large': 0.0765, 'c6i.xlarge': 0.153,
            # r5 系列
            'r5.large': 0.126, 'r5.xlarge': 0.252, 'r6i.large': 0.1134, 'r6i.xlarge': 0.2268
        }
        
        base_price = prices.get(instance_type, 0.1)  # 默认价格
        region_multiplier = {
            'us-east-1': 1.0, 'us-west-2': 1.0, 'ap-southeast-1': 1.15,
            'ap-northeast-1': 1.12, 'eu-west-1': 1.05, 'ap-east-1': 1.18
        }
        
        final_price = base_price * region_multiplier.get(region, 1.0)
        print(f"备用价格: {instance_type} ({region}) = ${final_price:.4f}/小时")
        return final_price
    
    def get_rds_price_fallback(self, instance_type):
        """备用RDS价格表"""
        prices = {
            'db.t3.micro': 0.017, 'db.t3.small': 0.034, 'db.m5.large': 0.192,
            'db.t2.micro': 0.017, 'db.t2.small': 0.034, 'db.m4.large': 0.175
        }
        return prices.get(instance_type, 0.05)
    
    def update_real_price(self, instance_type, region, service_type):
        """更新真实价格（在后台运行）"""
        cache_key = f"{service_type}_{instance_type}_{region}"
        
        try:
            pricing_client = self.session.client('pricing', region_name='us-east-1')
            
            if service_type == 'ec2':
                response = pricing_client.get_products(
                    ServiceCode='AmazonEC2',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)},
                        {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                        {'Type': 'TERM_MATCH', 'Field': 'operating-system', 'Value': 'Linux'}
                    ]
                )
            elif service_type == 'rds':
                response = pricing_client.get_products(
                    ServiceCode='AmazonRDS',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)},
                        {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': 'MySQL'}
                    ]
                )
            elif service_type == 'ebs':
                response = pricing_client.get_products(
                    ServiceCode='AmazonEC2',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'},
                        {'Type': 'TERM_MATCH', 'Field': 'volumeApiName', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)}
                    ]
                )
            elif service_type == 's3':
                response = pricing_client.get_products(
                    ServiceCode='AmazonS3',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'storageClass', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)}
                    ]
                )
            elif service_type == 'vpc':
                response = pricing_client.get_products(
                    ServiceCode='AmazonVPC',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'NAT Gateway'},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)}
                    ]
                )
            
            if response['PriceList']:
                price_data = json.loads(response['PriceList'][0])
                terms = price_data['terms']['OnDemand']
                for term_key in terms:
                    price_dimensions = terms[term_key]['priceDimensions']
                    for pd_key in price_dimensions:
                        price = float(price_dimensions[pd_key]['pricePerUnit']['USD'])
                        
                        # 缓存真实价格 (24小时有效)
                        self.price_cache[cache_key] = price
                        self.cache_expiry[cache_key] = datetime.now() + timedelta(hours=24)
                        
                        print(f"更新真实价格: {instance_type} ({region}) = ${price:.4f}/小时")
                        
                        # 更新数据库中的价格数据
                        self.update_database_prices(instance_type, region, service_type, price)
                        return
                        
        except Exception as e:
            print(f"更新真实价格失败 {instance_type} ({region}): {e}")
    

    
    def check_monthly_reset(self):
        """检查是否需要重置月度计费"""
        now = datetime.now()
        current_month = now.strftime('%Y-%m')
        
        conn = sqlite3.connect('data/cost_history.db')
        cursor = conn.cursor()
        
        # 检查是否已经有这个月的记录
        existing = cursor.execute('''
            SELECT year_month FROM monthly_summary 
            WHERE year_month = ?
        ''', (current_month,)).fetchone()
        
        if not existing:
            # 获取上个月的数据（如果存在）
            last_month_date = now.replace(day=1) - timedelta(days=1)
            last_month = last_month_date.strftime('%Y-%m')
            
            last_month_data = cursor.execute('''
                SELECT total_monthly_cost, service_breakdown FROM monthly_summary 
                WHERE year_month = ?
            ''', (last_month,)).fetchone()
            
            if last_month_data:
                print(f"上月({last_month})总费用: ${last_month_data[0]:.2f}")
                print(f"服务明细: {json.loads(last_month_data[1])}")
            
            # 新月份，创建初始记录
            cursor.execute('''
                INSERT INTO monthly_summary 
                (year_month, total_monthly_cost, service_breakdown, created_at)
                VALUES (?, 0.0, '{}', ?)
            ''', (current_month, now.isoformat()))
            
            print(f"新月份开始: {current_month}, 月度计费重置为$0.00")
        
        conn.commit()
        conn.close()
    
    def update_monthly_summary(self, daily_cost, service_breakdown):
        """更新月度统计"""
        now = datetime.now()
        current_month = now.strftime('%Y-%m')
        
        conn = sqlite3.connect('data/cost_history.db')
        cursor = conn.cursor()
        
        # 获取当月的现有数据
        existing = cursor.execute('''
            SELECT total_monthly_cost, service_breakdown FROM monthly_summary 
            WHERE year_month = ?
        ''', (current_month,)).fetchone()
        
        if existing:
            # 更新现有记录
            current_total = existing[0]
            current_services = json.loads(existing[1]) if existing[1] else {}
            
            # 累加每日成本
            new_total = current_total + daily_cost
            
            # 累加服务成本
            for service, cost in service_breakdown.items():
                current_services[service] = current_services.get(service, 0) + cost
            
            cursor.execute('''
                UPDATE monthly_summary 
                SET total_monthly_cost = ?, service_breakdown = ?
                WHERE year_month = ?
            ''', (new_total, json.dumps(current_services), current_month))
        
        conn.commit()
        conn.close()
    
    def refresh_price_cache_daily(self):
        """每天刷新价格缓存"""
        now = datetime.now()
        
        # 检查是否需要清理过期缓存
        expired_keys = []
        for key, expiry_time in self.cache_expiry.items():
            if now >= expiry_time:
                expired_keys.append(key)
        
        # 清理过期缓存
        for key in expired_keys:
            if key in self.price_cache:
                del self.price_cache[key]
            if key in self.cache_expiry:
                del self.cache_expiry[key]
        
        if expired_keys:
            print(f"清理了 {len(expired_keys)} 个过期价格缓存")
    
    def get_ebs_price(self, volume_type, region='us-east-1'):
        """获取EBS实时价格"""
        cache_key = f"ebs_{volume_type}_{region}"
        
        if cache_key in self.price_cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                cached_price = self.price_cache[cache_key]
                print(f"使用缓存EBS价格: {volume_type} ({region}) = ${cached_price:.4f}/GB/月")
                return cached_price
        
        # 直接获取AWS实时价格
        real_price = self.get_real_price_sync(volume_type, region, 'ebs')
        
        if real_price > 0:
            # 缓存价格 (4小时有效)
            self.price_cache[cache_key] = real_price
            self.cache_expiry[cache_key] = datetime.now() + timedelta(hours=4)
            print(f"获取EBS实时价格: {volume_type} ({region}) = ${real_price:.4f}/GB/月")
            
            # 立即更新数据库中的价格
            threading.Timer(5.0, self.update_database_prices, args=[volume_type, region, 'ebs', real_price]).start()
            
            return real_price
        else:
            # 如果获取失败，使用备用价格
            base_prices = {
                'gp3': 0.08, 'gp2': 0.10, 'io1': 0.125, 'io2': 0.125, 
                'st1': 0.045, 'sc1': 0.025, 'standard': 0.05
            }
            base_price = base_prices.get(volume_type, 0.10)
            region_multiplier = {
                'us-east-1': 1.0, 'us-west-2': 1.0, 'ap-southeast-1': 1.15,
                'ap-northeast-1': 1.12, 'eu-west-1': 1.05, 'ap-east-1': 1.25
            }
            final_price = base_price * region_multiplier.get(region, 1.0)
            print(f"使用备用EBS价格: {volume_type} ({region}) = ${final_price:.4f}/GB/月")
            return final_price
    
    def get_s3_price(self, storage_class='Standard', region='us-east-1'):
        """获取S3真实价格"""
        cache_key = f"s3_{storage_class}_{region}"
        
        if cache_key in self.price_cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                return self.price_cache[cache_key]
        
        # 备用价格
        fallback_prices = {'Standard': 0.023, 'IA': 0.0125, 'Glacier': 0.004}
        fallback_price = fallback_prices.get(storage_class, 0.023)
        
        threading.Timer(60.0, self.update_real_price, args=[storage_class, region, 's3']).start()
        return fallback_price
    
    def get_nat_gateway_price(self, region='us-east-1'):
        """获取NAT Gateway真实价格"""
        cache_key = f"nat_gateway_{region}"
        
        if cache_key in self.price_cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                return self.price_cache[cache_key]
        
        fallback_price = 0.045  # 备用价格
        threading.Timer(60.0, self.update_real_price, args=['natgateway', region, 'vpc']).start()
        return fallback_price
    
    def get_real_price_sync(self, instance_type, region, service_type):
        """同步获取AWS实时价格"""
        try:
            pricing_client = self.session.client('pricing', region_name='us-east-1')
            
            if service_type == 'ec2':
                response = pricing_client.get_products(
                    ServiceCode='AmazonEC2',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)},
                        {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                        {'Type': 'TERM_MATCH', 'Field': 'operating-system', 'Value': 'Linux'}
                    ]
                )
            elif service_type == 'rds':
                response = pricing_client.get_products(
                    ServiceCode='AmazonRDS',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)},
                        {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': 'MySQL'}
                    ]
                )
            elif service_type == 'ebs':
                response = pricing_client.get_products(
                    ServiceCode='AmazonEC2',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'},
                        {'Type': 'TERM_MATCH', 'Field': 'volumeApiName', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name(region)}
                    ]
                )
            else:
                return 0.0
            
            if response['PriceList']:
                price_data = json.loads(response['PriceList'][0])
                terms = price_data['terms']['OnDemand']
                for term_key in terms:
                    price_dimensions = terms[term_key]['priceDimensions']
                    for pd_key in price_dimensions:
                        price = float(price_dimensions[pd_key]['pricePerUnit']['USD'])
                        return price
            
            return 0.0
            
        except Exception as e:
            print(f"获取{service_type}实时价格失败 {instance_type} ({region}): {e}")
            return 0.0
    
    def update_database_prices(self, instance_type, region, service_type, real_price):
        """更新数据库中的价格数据"""
        conn = sqlite3.connect('data/cost_history.db')
        cursor = conn.cursor()
        
        try:
            # 获取最近的记录时间戳
            latest_timestamp = cursor.execute('''
                SELECT timestamp FROM cost_summary 
                ORDER BY timestamp DESC LIMIT 1
            ''').fetchone()
            
            if not latest_timestamp:
                print(f"未找到最近的数据记录")
                return
                
            timestamp = latest_timestamp[0]
            print(f"开始更新数据库价格: {service_type} {instance_type} ({region}) = ${real_price:.4f}")
            
            # 更新cost_records表中的价格
            if service_type in ['ec2', 'rds', 'ebs']:
                # 查找匹配的记录
                records = cursor.execute('''
                    SELECT id, details, hourly_cost, resource_id FROM cost_records 
                    WHERE timestamp = ? AND service_type = ? AND region = ?
                ''', (timestamp, service_type.upper(), region)).fetchall()
                
                print(f"找到 {len(records)} 条 {service_type.upper()} 记录在区域 {region}")
                
                updated_count = 0
                for record in records:
                    details = json.loads(record[1])
                    old_price = record[2]
                    
                    # 检查实例类型匹配
                    if details.get('instance_type') == instance_type or (service_type == 'ebs' and instance_type in details.get('instance_type', '')):
                        # 计算新的成本
                        if service_type == 'ebs':
                            # EBS按月计费，需要计算存储大小
                            size_gb = float(details.get('instance_type', '0GB').replace('GB', '').split()[-1]) if 'GB' in details.get('instance_type', '') else 1
                            monthly_cost = size_gb * real_price
                            new_daily_cost = monthly_cost / 30
                            new_hourly_cost = new_daily_cost / 24
                        else:
                            # EC2/RDS按小时计费
                            new_hourly_cost = real_price
                            new_daily_cost = real_price * 24
                        
                        # 更新details
                        details['hourly_cost'] = new_hourly_cost
                        details['daily_cost'] = new_daily_cost
                        
                        # 更新数据库
                        cursor.execute('''
                            UPDATE cost_records 
                            SET hourly_cost = ?, daily_cost = ?, details = ?
                            WHERE id = ?
                        ''', (new_hourly_cost, new_daily_cost, json.dumps(details), record[0]))
                        
                        print(f"✓ 更新资源 {record[3]}: ${old_price:.4f} → ${real_price:.4f}/小时")
                        updated_count += 1
                
                if updated_count > 0:
                    # 重新计算并更新cost_summary
                    self.recalculate_summary(cursor, timestamp)
                    print(f"✓ 已更新 {updated_count} 条记录并重新计算汇总")
                else:
                    print(f"⚠ 未找到匹配的 {instance_type} 记录")
                
            conn.commit()
            
        except Exception as e:
            print(f"更新数据库价格失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()
    
    def recalculate_summary(self, cursor, timestamp):
        """重新计算汇总数据"""
        # 获取该时间戳的所有记录
        records = cursor.execute('''
            SELECT hourly_cost, daily_cost, service_type FROM cost_records 
            WHERE timestamp = ?
        ''', (timestamp,)).fetchall()
        
        old_summary = cursor.execute('''
            SELECT total_hourly_cost, total_daily_cost FROM cost_summary 
            WHERE timestamp = ?
        ''', (timestamp,)).fetchone()
        
        total_hourly = sum(record[0] for record in records)
        total_daily = sum(record[1] for record in records)
        
        # 重新计算服务分解
        service_breakdown = defaultdict(float)
        for record in records:
            service_breakdown[record[2]] += record[1]
        
        # 更新cost_summary
        cursor.execute('''
            UPDATE cost_summary 
            SET total_hourly_cost = ?, total_daily_cost = ?, service_breakdown = ?
            WHERE timestamp = ?
        ''', (total_hourly, total_daily, json.dumps(dict(service_breakdown)), timestamp))
        
        if old_summary:
            print(f"✓ 汇总更新: 每小时 ${old_summary[0]:.4f} → ${total_hourly:.4f}, 每日 ${old_summary[1]:.2f} → ${total_daily:.2f}")
    
    def start_scheduler(self):
        """启动定时任务"""
        print("AWS成本监控器启动...")
        
        # 立即执行一次
        self.collect_and_save()
        
        # 每小时执行
        schedule.every().hour.do(self.collect_and_save)
        
        print("定时任务已设置 (每小时执行)")
        
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == '__main__':
    collector = CostCollector()
    collector.start_scheduler()