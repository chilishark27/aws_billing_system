#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAT Gateway费用计算示例
"""

def calculate_nat_gateway_cost(gb_processed_per_month):
    """计算NAT Gateway月费用"""
    base_cost = 0.045 * 24 * 30  # 基础费用
    processing_cost = gb_processed_per_month * 0.045  # 数据处理费用
    total_cost = base_cost + processing_cost
    
    return {
        'base_cost': base_cost,
        'processing_cost': processing_cost,
        'total_cost': total_cost,
        'gb_processed': gb_processed_per_month
    }

def show_nat_gateway_examples():
    """显示NAT Gateway费用示例"""
    print("=== NAT Gateway 费用计算示例 ===\n")
    
    # 不同流量场景
    scenarios = [
        ("轻度使用", 10),      # 10GB/月
        ("中度使用", 100),     # 100GB/月  
        ("重度使用", 1000),    # 1TB/月
        ("企业级", 5000),      # 5TB/月
        ("大型应用", 10000)    # 10TB/月
    ]
    
    print("场景分析:")
    print("-" * 60)
    print(f"{'场景':<10} {'流量':<10} {'基础费用':<10} {'处理费用':<10} {'总费用':<10}")
    print("-" * 60)
    
    for scenario_name, gb_amount in scenarios:
        result = calculate_nat_gateway_cost(gb_amount)
        print(f"{scenario_name:<10} {gb_amount:>6}GB   ${result['base_cost']:>6.2f}   ${result['processing_cost']:>7.2f}   ${result['total_cost']:>7.2f}")
    
    print("\n详细计算说明:")
    print("1. 基础费用: $0.045/小时 × 24小时 × 30天 = $32.40/月")
    print("2. 数据处理费用: 流量GB数 × $0.045/GB")
    print("3. 总费用 = 基础费用 + 数据处理费用")
    
    print("\n重要提醒:")
    print("- NAT Gateway创建后立即开始计费基础费用")
    print("- 即使没有流量也要支付$32.40/月")
    print("- 删除NAT Gateway后停止计费")
    print("- 数据处理费用按实际使用量计算")
    
    print("\n与其他方案对比:")
    print("- NAT Instance: 只需支付EC2实例费用，但需要自己管理")
    print("- Internet Gateway: 免费，但需要Public IP")
    print("- VPC Endpoint: 适合访问AWS服务，$0.01/小时 + $0.01/GB")

def simulate_monthly_usage():
    """模拟月度使用情况"""
    print("\n=== 月度使用模拟 ===")
    
    # 模拟一个典型的Web应用
    daily_scenarios = [
        ("数据库备份", 50),    # 每天50GB备份到S3
        ("API调用", 5),        # 每天5GB API流量
        ("日志传输", 2),       # 每天2GB日志
        ("软件更新", 1),       # 每天1GB更新
    ]
    
    total_daily_gb = sum([gb for _, gb in daily_scenarios])
    monthly_gb = total_daily_gb * 30
    
    print(f"典型Web应用日常流量:")
    for activity, gb in daily_scenarios:
        print(f"  {activity}: {gb}GB/天")
    
    print(f"\n每日总流量: {total_daily_gb}GB")
    print(f"每月总流量: {monthly_gb}GB")
    
    result = calculate_nat_gateway_cost(monthly_gb)
    print(f"\n月度费用计算:")
    print(f"  基础费用: ${result['base_cost']:.2f}")
    print(f"  处理费用: {monthly_gb}GB × $0.045 = ${result['processing_cost']:.2f}")
    print(f"  总费用: ${result['total_cost']:.2f}/月")

if __name__ == '__main__':
    show_nat_gateway_examples()
    simulate_monthly_usage()