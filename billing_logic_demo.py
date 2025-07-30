#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS流量费用计费逻辑演示
"""

def calculate_ec2_data_transfer_cost(gb_transferred):
    """计算EC2数据传输出费用"""
    if gb_transferred <= 1:
        return 0  # 前1GB免费
    elif gb_transferred <= 10240:  # 10TB
        return (gb_transferred - 1) * 0.09
    elif gb_transferred <= 51200:  # 50TB
        return 10239 * 0.09 + (gb_transferred - 10240) * 0.085
    elif gb_transferred <= 153600:  # 150TB
        return 10239 * 0.09 + 40960 * 0.085 + (gb_transferred - 51200) * 0.070
    else:
        return 10239 * 0.09 + 40960 * 0.085 + 102400 * 0.070 + (gb_transferred - 153600) * 0.050

def calculate_nat_gateway_cost(hours_running, gb_processed):
    """计算NAT Gateway费用"""
    hourly_cost = hours_running * 0.045
    processing_cost = gb_processed * 0.045
    return hourly_cost + processing_cost

def calculate_vpc_endpoint_cost(hours_running, gb_processed, endpoint_type='Interface'):
    """计算VPC端点费用"""
    if endpoint_type == 'Gateway':
        return 0  # Gateway端点免费
    
    hourly_cost = hours_running * 0.01
    processing_cost = gb_processed * 0.01
    return hourly_cost + processing_cost

def calculate_elb_cost(gb_processed, lb_type='application'):
    """计算ELB数据处理费用"""
    rates = {
        'application': 0.008,
        'network': 0.006,
        'classic': 0.008
    }
    return gb_processed * rates.get(lb_type, 0.008)

def calculate_cloudfront_cost(gb_transferred):
    """计算CloudFront流量费用"""
    if gb_transferred <= 10240:  # 10TB
        return gb_transferred * 0.085
    elif gb_transferred <= 51200:  # 50TB
        return 10240 * 0.085 + (gb_transferred - 10240) * 0.070
    else:
        return 10240 * 0.085 + 40960 * 0.070 + (gb_transferred - 51200) * 0.060

def calculate_route53_cost(query_count, hosted_zones=1):
    """计算Route 53费用"""
    query_cost = (query_count / 1000000) * 0.40  # 每百万次查询$0.40
    zone_cost = hosted_zones * 0.50  # 每个托管区域$0.50/月
    return query_cost + zone_cost

def demo_billing_calculations():
    """演示计费计算"""
    print("=== AWS流量费用计费逻辑演示 ===\n")
    
    # EC2数据传输示例
    print("1. EC2数据传输出费用:")
    test_volumes = [0.5, 1.5, 10, 100, 1000, 15000]
    for volume in test_volumes:
        cost = calculate_ec2_data_transfer_cost(volume)
        print(f"   {volume:8.1f} GB -> ${cost:8.2f}")
    
    # NAT Gateway示例
    print("\n2. NAT Gateway费用 (运行30天):")
    hours_per_month = 24 * 30
    test_data = [10, 100, 1000, 5000]
    for gb in test_data:
        cost = calculate_nat_gateway_cost(hours_per_month, gb)
        hourly = hours_per_month * 0.045
        processing = gb * 0.045
        print(f"   处理{gb:4d}GB -> 小时费:${hourly:.2f} + 处理费:${processing:.2f} = ${cost:.2f}")
    
    # VPC端点示例
    print("\n3. VPC Interface端点费用 (运行30天):")
    for gb in test_data:
        cost = calculate_vpc_endpoint_cost(hours_per_month, gb)
        hourly = hours_per_month * 0.01
        processing = gb * 0.01
        print(f"   处理{gb:4d}GB -> 小时费:${hourly:.2f} + 处理费:${processing:.2f} = ${cost:.2f}")
    
    # ELB示例
    print("\n4. ELB数据处理费用:")
    lb_types = ['application', 'network', 'classic']
    for lb_type in lb_types:
        cost = calculate_elb_cost(1000, lb_type)  # 1TB数据
        print(f"   {lb_type.upper():11} 1TB -> ${cost:.2f}")
    
    # CloudFront示例
    print("\n5. CloudFront流量费用:")
    cf_volumes = [100, 1000, 15000, 60000]
    for volume in cf_volumes:
        cost = calculate_cloudfront_cost(volume)
        print(f"   {volume:5d} GB -> ${cost:8.2f}")
    
    # Route 53示例
    print("\n6. Route 53费用:")
    query_counts = [100000, 1000000, 10000000, 100000000]
    for queries in query_counts:
        cost = calculate_route53_cost(queries)
        print(f"   {queries:9,}次查询 + 1个区域 -> ${cost:.2f}")
    
    print("\n=== 实际案例分析 ===")
    
    # 基于测试结果的实际案例
    print("\n从测试结果看到的实际费用:")
    print("- EC2实例 i-0e7806926475abfb9 (r6a.large):")
    print("  * 传输量: 8.89 GB")
    print("  * 免费额度: 1 GB")
    print("  * 付费部分: 7.89 GB")
    print("  * 费用计算: 7.89 × $0.09 = $0.71/月")
    
    actual_cost = calculate_ec2_data_transfer_cost(8.89)
    print(f"  * 系统计算结果: ${actual_cost:.2f}/月")
    
    print("\n- EC2实例 i-0c920bace4404ae2b (t4g.small):")
    print("  * 传输量: 0.17 GB (在免费额度内)")
    print("  * 费用: $0.00/月")
    
    actual_cost2 = calculate_ec2_data_transfer_cost(0.17)
    print(f"  * 系统计算结果: ${actual_cost2:.2f}/月")

if __name__ == '__main__':
    demo_billing_calculations()