#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS价格管理器
"""

import boto3
import json
import threading
from datetime import datetime, timedelta


class PriceManager:
    def __init__(self):
        self.session = boto3.Session()
        self.price_cache = {}
        self.cache_expiry = {}
        
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
        return location_mapping.get(region, 'US East (N. Virginia)')
    
    def get_ec2_price(self, instance_type, region='us-east-1'):
        """获取EC2实时价格"""
        cache_key = f"ec2_{instance_type}_{region}"
        
        if cache_key in self.price_cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                return self.price_cache[cache_key]
        
        real_price = self._get_real_price_sync(instance_type, region, 'ec2')
        
        if real_price > 0:
            self.price_cache[cache_key] = real_price
            self.cache_expiry[cache_key] = datetime.now() + timedelta(hours=4)
            return real_price
        else:
            return self._get_ec2_price_fallback(instance_type, region)
    
    def get_rds_price(self, instance_type, region='us-east-1'):
        """获取RDS实时价格"""
        cache_key = f"rds_{instance_type}_{region}"
        
        if cache_key in self.price_cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                return self.price_cache[cache_key]
        
        real_price = self._get_real_price_sync(instance_type, region, 'rds')
        
        if real_price > 0:
            self.price_cache[cache_key] = real_price
            self.cache_expiry[cache_key] = datetime.now() + timedelta(hours=4)
            return real_price
        else:
            return self._get_rds_price_fallback(instance_type)
    
    def get_ebs_price(self, volume_type, region='us-east-1'):
        """获取EBS实时价格"""
        cache_key = f"ebs_{volume_type}_{region}"
        
        if cache_key in self.price_cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                return self.price_cache[cache_key]
        
        real_price = self._get_real_price_sync(volume_type, region, 'ebs')
        
        if real_price > 0:
            self.price_cache[cache_key] = real_price
            self.cache_expiry[cache_key] = datetime.now() + timedelta(hours=4)
            return real_price
        else:
            return self._get_ebs_price_fallback(volume_type, region)
    
    def get_s3_price(self, storage_class='Standard', region='us-east-1'):
        """获取S3价格"""
        fallback_prices = {'Standard': 0.023, 'IA': 0.0125, 'Glacier': 0.004}
        return fallback_prices.get(storage_class, 0.023)
    
    def get_nat_gateway_price(self, region='us-east-1'):
        """获取NAT Gateway价格"""
        return 0.045  # 基础价格
    
    def get_public_ip_price(self, region='us-east-1'):
        """获取Public IP价格 - 2024年2月1日起统一收费"""
        return 0.005  # $0.005/小时
    
    def _get_real_price_sync(self, instance_type, region, service_type):
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
                        return float(price_dimensions[pd_key]['pricePerUnit']['USD'])
            
            return 0.0
            
        except Exception as e:
            print(f"获取{service_type}实时价格失败 {instance_type} ({region}): {e}")
            return 0.0
    
    def _get_ec2_price_fallback(self, instance_type, region='us-east-1'):
        """备用EC2价格表"""
        prices = {
            't2.nano': 0.0058, 't2.micro': 0.0116, 't2.small': 0.023, 't2.medium': 0.0464,
            't3.nano': 0.0052, 't3.micro': 0.0104, 't3.small': 0.0208, 't3.medium': 0.0416,
            't4g.nano': 0.0042, 't4g.micro': 0.0084, 't4g.small': 0.0168, 't4g.medium': 0.0336,
            'm5.large': 0.096, 'm5.xlarge': 0.192, 'c5.large': 0.085, 'c5.xlarge': 0.17
        }
        
        base_price = prices.get(instance_type, 0.1)
        region_multiplier = {
            'us-east-1': 1.0, 'us-west-2': 1.0, 'ap-southeast-1': 1.15,
            'ap-northeast-1': 1.12, 'eu-west-1': 1.05, 'ap-east-1': 1.18
        }
        
        return base_price * region_multiplier.get(region, 1.0)
    
    def _get_rds_price_fallback(self, instance_type):
        """备用RDS价格表"""
        prices = {
            'db.t3.micro': 0.017, 'db.t3.small': 0.034, 'db.m5.large': 0.192,
            'db.t2.micro': 0.017, 'db.t2.small': 0.034, 'db.m4.large': 0.175
        }
        return prices.get(instance_type, 0.05)
    
    def _get_ebs_price_fallback(self, volume_type, region='us-east-1'):
        """备用EBS价格表"""
        base_prices = {
            'gp3': 0.08, 'gp2': 0.10, 'io1': 0.125, 'io2': 0.125,
            'st1': 0.045, 'sc1': 0.025, 'standard': 0.05
        }
        base_price = base_prices.get(volume_type, 0.10)
        region_multiplier = {
            'us-east-1': 1.0, 'us-west-2': 1.0, 'ap-southeast-1': 1.15,
            'ap-northeast-1': 1.12, 'eu-west-1': 1.05, 'ap-east-1': 1.25
        }
        return base_price * region_multiplier.get(region, 1.0)
    
    def refresh_cache(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = [key for key, expiry_time in self.cache_expiry.items() if now >= expiry_time]
        
        for key in expired_keys:
            self.price_cache.pop(key, None)
            self.cache_expiry.pop(key, None)
        
        if expired_keys:
            print(f"清理了 {len(expired_keys)} 个过期价格缓存")