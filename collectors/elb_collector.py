#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
负载均衡器资源收集器
"""

from .base_collector import BaseCollector


class ELBCollector(BaseCollector):
    def scan_region(self, region):
        """扫描单个区域的负载均衡器"""
        services = []
        try:
            # ALB/NLB
            elbv2 = self.get_client('elbv2', region)
            load_balancers = elbv2.describe_load_balancers()
            
            for lb in load_balancers['LoadBalancers']:
                if lb['State']['Code'] == 'active':
                    lb_type = lb['Type']
                    # ALB: $0.0225/小时, NLB: $0.0225/小时
                    hourly_cost = 0.0225
                    
                    # 面向互联网的负载均衡器有Public IP成本
                    if lb.get('Scheme') == 'internet-facing':
                        hourly_cost += self.price_manager.get_public_ip_price(region)
                    
                    services.append({
                        'service': 'ELB',
                        'resource_id': lb['LoadBalancerName'],
                        'region': region,
                        'instance_type': f"{lb_type.upper()} ({lb.get('Scheme', 'internal')})",
                        'hourly_cost': hourly_cost,
                        'daily_cost': hourly_cost * 24
                    })
            
            # Classic ELB
            try:
                elb = self.get_client('elb', region)
                classic_lbs = elb.describe_load_balancers()
                
                for lb in classic_lbs['LoadBalancerDescriptions']:
                    hourly_cost = 0.025  # Classic ELB价格
                    
                    if lb.get('Scheme') == 'internet-facing':
                        hourly_cost += self.price_manager.get_public_ip_price(region)
                    
                    services.append({
                        'service': 'ELB',
                        'resource_id': lb['LoadBalancerName'],
                        'region': region,
                        'instance_type': f"Classic ({lb.get('Scheme', 'internal')})",
                        'hourly_cost': hourly_cost,
                        'daily_cost': hourly_cost * 24
                    })
            except:
                pass
                
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"扫描ELB失败 ({region}): {e}")
            else:
                print(f"扫描ELB失败 ({region}): {e}")
        return services
    
    def scan_all_regions(self):
        """扫描所有区域的负载均衡器"""
        all_services = []
        for region in self.regions:
            all_services.extend(self.scan_region(region))
        return all_services