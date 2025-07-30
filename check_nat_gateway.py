#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查NAT Gateway资源和计费
"""

import boto3
from datetime import datetime, timedelta

def check_nat_gateways():
    """检查所有区域的NAT Gateway"""
    session = boto3.Session()
    regions = ['us-east-1', 'us-west-2', 'ap-southeast-1', 'ap-northeast-1', 'eu-west-1', 'ap-east-1']
    
    total_nat_gateways = 0
    total_monthly_cost = 0
    
    print("=== NAT Gateway 资源检查 ===\n")
    
    for region in regions:
        try:
            ec2_client = session.client('ec2', region_name=region)
            cloudwatch = session.client('cloudwatch', region_name=region)
            
            # 获取NAT Gateway列表
            response = ec2_client.describe_nat_gateways()
            nat_gateways = response['NatGateways']
            
            if nat_gateways:
                print(f"📍 区域: {region}")
                
                for nat in nat_gateways:
                    nat_id = nat['NatGatewayId']
                    state = nat['State']
                    subnet_id = nat.get('SubnetId', 'N/A')
                    vpc_id = nat.get('VpcId', 'N/A')
                    
                    print(f"  🔹 NAT Gateway: {nat_id}")
                    print(f"     状态: {state}")
                    print(f"     子网: {subnet_id}")
                    print(f"     VPC: {vpc_id}")
                    
                    if state == 'available':
                        total_nat_gateways += 1
                        
                        # 计算费用
                        hourly_cost = 0.045  # $0.045/小时
                        monthly_hours = 24 * 30
                        monthly_base_cost = hourly_cost * monthly_hours
                        
                        # 获取数据处理量
                        try:
                            end_time = datetime.utcnow()
                            start_time = end_time - timedelta(days=30)
                            
                            bytes_response = cloudwatch.get_metric_statistics(
                                Namespace='AWS/NATGateway',
                                MetricName='BytesOutToDestination',
                                Dimensions=[{'Name': 'NatGatewayId', 'Value': nat_id}],
                                StartTime=start_time,
                                EndTime=end_time,
                                Period=86400,
                                Statistics=['Sum']
                            )
                            
                            total_bytes = sum([point['Sum'] for point in bytes_response['Datapoints']])
                            total_gb = total_bytes / (1024**3)
                            processing_cost = total_gb * 0.045
                            
                            total_cost = monthly_base_cost + processing_cost
                            total_monthly_cost += total_cost
                            
                            print(f"     💰 费用计算:")
                            print(f"        基础费用: ${monthly_base_cost:.2f}/月 (${hourly_cost}/小时 × {monthly_hours}小时)")
                            print(f"        数据处理: {total_gb:.2f} GB × $0.045 = ${processing_cost:.2f}/月")
                            print(f"        总费用: ${total_cost:.2f}/月")
                            
                        except Exception as e:
                            print(f"     ⚠️ 无法获取流量数据: {e}")
                            total_monthly_cost += monthly_base_cost
                            print(f"     💰 基础费用: ${monthly_base_cost:.2f}/月")
                    
                    print()
            
        except Exception as e:
            print(f"❌ 检查区域 {region} 失败: {e}")
    
    print("=== 汇总信息 ===")
    print(f"总NAT Gateway数量: {total_nat_gateways}")
    print(f"预估月费用: ${total_monthly_cost:.2f}")
    
    if total_nat_gateways == 0:
        print("\nNAT Gateway 计费说明:")
        print("1. 基础费用: $0.045/小时 = $32.40/月")
        print("2. 数据处理费用: $0.045/GB")
        print("3. 总费用 = 基础费用 + 数据处理费用")
        print("\n如果你没有NAT Gateway，可以创建一个来测试:")
        print("   - 在VPC控制台创建NAT Gateway")
        print("   - 选择公有子网和弹性IP")
        print("   - 创建后立即开始计费")

if __name__ == '__main__':
    check_nat_gateways()